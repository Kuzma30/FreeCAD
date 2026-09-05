// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2026 FreeCAD Project Association                        *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 ***************************************************************************/

#include "PreCompiled.h"

#ifdef HAVE_QT_PDF_WIDGETS

#ifndef _PreComp_
#include <QAction>
#include <QApplication>
#include <QClipboard>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPainter>
#include <QPagedPaintDevice>
#include <QScrollBar>
#include <QTimer>
#include <QToolButton>
#include <QVBoxLayout>
#endif

#include <QDir>
#include <QFileDialog>
#include <QFileInfo>
#include <QProcess>
#include <QPushButton>
#include <QStandardPaths>
#include <QMouseEvent>
#include <QScrollBar>

#include <QPdfDocument>
#include <QPdfPageNavigator>
#include <QPdfSearchModel>
#include <QPdfSelection>
#include <QPdfView>

#include <cmath>

#include <Base/Console.h>
#include <Base/Interpreter.h>
#include <App/Application.h>
#include <App/Document.h>
#include <Base/Tools.h>

#include "PdfView.h"
#include "BitmapFactory.h"
#include "Command.h"
#include "CommandT.h"
#include "Document.h"

using namespace Gui;

namespace
{
// QPdfView zoom is a plain factor; keep it inside sane bounds.
constexpr qreal ZoomStep = 1.25;
constexpr qreal ZoomMin = 0.1;
constexpr qreal ZoomMax = 10.0;
}  // namespace

// ----------------------------------------------------------------------------
// PdfSelectionView
// ----------------------------------------------------------------------------

PdfSelectionView::PdfSelectionView(QWidget* parent)
    : QPdfView(parent)
{
    // Without mouse tracking we would only get move events while a button is
    // held, which is in fact all we need, but tracking keeps the cursor shape
    // responsive over text.
    viewport()->setCursor(Qt::IBeamCursor);
}

qreal PdfSelectionView::renderScale() const
{
    // QPdfView works in points and converts with the screen resolution.
    const qreal screenResolution = logicalDpiX() / 72.0;

    if (zoomMode() == QPdfView::ZoomMode::Custom) {
        return zoomFactor() * screenResolution;
    }

    QPdfDocument* doc = document();
    if (!doc || doc->pageCount() < 1) {
        return screenResolution;
    }

    const int page = pageNavigator() ? pageNavigator()->currentPage() : 0;
    const QSizeF pageSize = doc->pagePointSize(page);
    if (pageSize.isEmpty()) {
        return screenResolution;
    }

    const QMargins margins = documentMargins();
    const qreal usableWidth = viewport()->width() - margins.left() - margins.right();

    if (zoomMode() == QPdfView::ZoomMode::FitToWidth) {
        return usableWidth / pageSize.width();
    }

    // FitInView: whichever axis is the tighter constraint.
    const qreal usableHeight = viewport()->height() - margins.top() - margins.bottom();
    return qMin(usableWidth / pageSize.width(), usableHeight / pageSize.height());
}

void PdfSelectionView::visiblePageRange(int& first, int& last) const
{
    QPdfDocument* doc = document();
    const int count = doc ? doc->pageCount() : 0;

    if (count < 1) {
        first = last = -1;
        return;
    }

    if (pageMode() == QPdfView::PageMode::SinglePage) {
        first = last = pageNavigator() ? pageNavigator()->currentPage() : 0;
    }
    else {
        first = 0;
        last = count - 1;
    }
}

void PdfSelectionView::ensureLayout() const
{
    QPdfDocument* doc = document();
    if (!doc) {
        layoutCache.clear();
        cachedScale = -1.0;
        return;
    }

    const qreal scale = renderScale();
    int first = -1;
    int last = -1;
    visiblePageRange(first, last);

    const bool stillValid = !layoutCache.isEmpty() && qFuzzyCompare(cachedScale, scale)
        && cachedFirst == first && cachedLast == last;
    if (stillValid) {
        return;
    }

    layoutCache.clear();
    cachedScale = scale;
    cachedFirst = first;
    cachedLast = last;

    if (first < 0 || scale <= 0.0) {
        return;
    }

    const QMargins margins = documentMargins();

    qreal widest = 0.0;
    for (int i = first; i <= last; ++i) {
        widest = qMax(widest, doc->pagePointSize(i).width() * scale);
    }

    layoutCache.reserve(last - first + 1);
    qreal y = margins.top();
    for (int i = first; i <= last; ++i) {
        const QSizeF size = doc->pagePointSize(i) * scale;
        const qreal x = margins.left() + (widest - size.width()) / 2.0;
        layoutCache.append(QRectF(x, y, size.width(), size.height()));
        y += size.height() + pageSpacing();
    }
}

QRectF PdfSelectionView::pageRect(int page) const
{
    ensureLayout();

    if (page < cachedFirst || page > cachedLast) {
        return {};
    }

    const int index = page - cachedFirst;
    if (index < 0 || index >= layoutCache.size()) {
        return {};
    }

    QRectF rect = layoutCache.at(index);
    rect.translate(-horizontalScrollBar()->value(), -verticalScrollBar()->value());
    return rect;
}

bool PdfSelectionView::mapToPage(const QPointF& pos, int& page, QPointF& pagePos) const
{
    ensureLayout();

    if (cachedFirst < 0 || cachedScale <= 0.0) {
        return false;
    }

    for (int i = cachedFirst; i <= cachedLast; ++i) {
        const QRectF rect = pageRect(i);
        if (rect.isNull() || !rect.contains(pos)) {
            continue;
        }
        page = i;
        pagePos = (pos - rect.topLeft()) / cachedScale;
        return true;
    }

    return false;
}

void PdfSelectionView::updateSelection(const QPointF& to)
{
    QPdfDocument* doc = document();
    if (!doc || anchorPage < 0) {
        return;
    }

    int page = -1;
    QPointF pagePos;
    if (!mapToPage(to, page, pagePos) || page != anchorPage) {
        // Dragging off the anchor page: keep what we have. A selection cannot
        // span pages, and neither can a crop region.
        return;
    }

    if (mode == DragMode::SelectText) {
        selection = doc->getSelection(anchorPage, anchorPos, pagePos);
        Q_EMIT selectionChanged(selectedText());
    }
    else {
        region = QRectF(anchorPos, pagePos).normalized();
        Q_EMIT regionChanged(!region.isEmpty());
    }

    viewport()->update();
}

QString PdfSelectionView::selectedText() const
{
    return selection.has_value() && selection->isValid() ? selection->text() : QString();
}

void PdfSelectionView::selectAllOnCurrentPage()
{
    QPdfDocument* doc = document();
    if (!doc || doc->pageCount() < 1) {
        return;
    }

    anchorPage = pageNavigator() ? pageNavigator()->currentPage() : 0;
    selection = doc->getAllText(anchorPage);
    viewport()->update();
    Q_EMIT selectionChanged(selectedText());
}

void PdfSelectionView::clearSelection()
{
    selection.reset();
    anchorPage = -1;
    viewport()->update();
    Q_EMIT selectionChanged(QString());
}

void PdfSelectionView::setDragMode(DragMode newMode)
{
    if (mode == newMode) {
        return;
    }

    mode = newMode;
    viewport()->setCursor(mode == DragMode::SelectText ? Qt::IBeamCursor
                                                       : Qt::CrossCursor);
    clearSelection();
    clearRegion();
}

void PdfSelectionView::invalidateLayout()
{
    layoutCache.clear();
    cachedScale = -1.0;
    cachedFirst = -1;
    cachedLast = -1;
}

void PdfSelectionView::clearRegion()
{
    region = {};
    regionPageIndex = -1;
    viewport()->update();
    Q_EMIT regionChanged(false);
}

void PdfSelectionView::mousePressEvent(QMouseEvent* event)
{
    if (event->button() != Qt::LeftButton) {
        QPdfView::mousePressEvent(event);
        return;
    }

    int page = -1;
    QPointF pagePos;
    if (mapToPage(event->position(), page, pagePos)) {
        anchorPage = page;
        anchorPos = pagePos;
        dragging = true;

        if (mode == DragMode::SelectText) {
            selection.reset();
            Q_EMIT selectionChanged(QString());
        }
        else {
            region = {};
            regionPageIndex = page;
            Q_EMIT regionChanged(false);
        }

        viewport()->update();
        event->accept();
        return;
    }

    QPdfView::mousePressEvent(event);
}

void PdfSelectionView::mouseMoveEvent(QMouseEvent* event)
{
    if (dragging) {
        updateSelection(event->position());
        event->accept();
        return;
    }

    QPdfView::mouseMoveEvent(event);
}

void PdfSelectionView::mouseReleaseEvent(QMouseEvent* event)
{
    if (dragging && event->button() == Qt::LeftButton) {
        updateSelection(event->position());
        dragging = false;
        event->accept();
        return;
    }

    QPdfView::mouseReleaseEvent(event);
}

void PdfSelectionView::paintEvent(QPaintEvent* event)
{
    QPdfView::paintEvent(event);

    if (mode == DragMode::SelectRegion) {
        paintRegion();
        return;
    }

    if (!selection.has_value() || !selection->isValid()) {
        return;
    }

    const QRectF rect = pageRect(anchorPage);
    if (rect.isNull()) {
        return;
    }

    const qreal scale = renderScale();
    if (scale <= 0.0) {
        return;
    }

    QPainter painter(viewport());
    painter.setRenderHint(QPainter::Antialiasing);

    QColor highlight = palette().highlight().color();
    highlight.setAlpha(90);
    painter.setPen(Qt::NoPen);
    painter.setBrush(highlight);

    // QPdfSelection reports its geometry in page points, so scale and shift
    // it into the viewport the same way the page itself was placed.
    for (const QPolygonF& bound : selection->bounds()) {
        QPolygonF mapped;
        mapped.reserve(bound.size());
        for (const QPointF& point : bound) {
            mapped.append(rect.topLeft() + point * scale);
        }
        painter.drawPolygon(mapped);
    }
}

void PdfSelectionView::paintRegion()
{
    if (region.isEmpty() || regionPageIndex < 0) {
        return;
    }

    const QRectF page = pageRect(regionPageIndex);
    if (page.isNull()) {
        return;
    }

    const qreal scale = renderScale();
    if (scale <= 0.0) {
        return;
    }

    const QRectF onScreen(page.topLeft() + region.topLeft() * scale,
                          region.size() * scale);

    QPainter painter(viewport());
    QColor accent = palette().highlight().color();

    painter.setPen(QPen(accent, 1, Qt::DashLine));
    QColor fill = accent;
    fill.setAlpha(50);
    painter.setBrush(fill);
    painter.drawRect(onScreen);
}


// ----------------------------------------------------------------------------
// PdfView
// ----------------------------------------------------------------------------

PdfView::PdfView(QWidget* parent)
    : MDIView(nullptr, parent)
    , pdfDocument(new QPdfDocument(this))
    , searchModel(new QPdfSearchModel(this))
    , pdfView(new PdfSelectionView(this))
{
    setupUi();
    setupActions();

    searchModel->setDocument(pdfDocument);
    pdfView->setDocument(pdfDocument);
    pdfView->invalidateLayout();
    pdfView->setSearchModel(searchModel);
    pdfView->setPageMode(QPdfView::PageMode::MultiPage);

    connect(pdfView->pageNavigator(), &QPdfPageNavigator::currentPageChanged,
            this, &PdfView::onPageChanged);

    setWindowIcon(Gui::BitmapFactory().pixmap("document-open"));
}

PdfView::~PdfView() = default;

void PdfView::setupUi()
{
    auto* toolBar = new QHBoxLayout();

    searchEdit = new QLineEdit(this);
    searchEdit->setPlaceholderText(tr("Find in document"));
    searchEdit->setClearButtonEnabled(true);
    searchEdit->setMaximumWidth(300);

    prevButton = new QToolButton(this);
    prevButton->setText(QStringLiteral("\u25c0"));
    prevButton->setToolTip(tr("Previous match"));
    prevButton->setEnabled(false);

    nextButton = new QToolButton(this);
    nextButton->setText(QStringLiteral("\u25b6"));
    nextButton->setToolTip(tr("Next match"));
    nextButton->setEnabled(false);

    resultLabel = new QLabel(this);

    // Page navigation
    prevPageButton = new QToolButton(this);
    prevPageButton->setText(QStringLiteral("\u25c0"));
    prevPageButton->setToolTip(tr("Previous page"));

    nextPageButton = new QToolButton(this);
    nextPageButton->setText(QStringLiteral("\u25b6"));
    nextPageButton->setToolTip(tr("Next page"));

    pageLabel = new QLabel(this);
    selectionLabel = new QLabel(this);

    regionButton = new QToolButton(this);
    regionButton->setText(tr("Region"));
    regionButton->setCheckable(true);
    regionButton->setToolTip(tr("Drag a rectangle to crop part of the page"));

    auto* zoomOut = new QToolButton(this);
    zoomOut->setText(QStringLiteral("\u2212"));
    zoomOut->setToolTip(tr("Zoom out"));

    auto* zoomIn = new QToolButton(this);
    zoomIn->setText(QStringLiteral("+"));
    zoomIn->setToolTip(tr("Zoom in"));

    auto* zoomReset = new QToolButton(this);
    zoomReset->setText(QStringLiteral("1:1"));
    zoomReset->setToolTip(tr("Fit width"));

    toolBar->addWidget(searchEdit);
    toolBar->addWidget(prevButton);
    toolBar->addWidget(nextButton);
    toolBar->addWidget(resultLabel);
    toolBar->addSpacing(16);
    toolBar->addWidget(prevPageButton);
    toolBar->addWidget(pageLabel);
    toolBar->addWidget(nextPageButton);
    toolBar->addStretch(1);
    toolBar->addWidget(selectionLabel);
    toolBar->addWidget(regionButton);
    toolBar->addWidget(zoomOut);
    toolBar->addWidget(zoomIn);
    toolBar->addWidget(zoomReset);

    auto* central = new QWidget(this);
    auto* layout = new QVBoxLayout(central);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addLayout(toolBar);
    layout->addWidget(pdfView);
    setCentralWidget(central);

    connect(zoomIn, &QToolButton::clicked, this, &PdfView::onZoomIn);
    connect(zoomOut, &QToolButton::clicked, this, &PdfView::onZoomOut);
    connect(zoomReset, &QToolButton::clicked, this, &PdfView::onZoomReset);
    connect(prevPageButton, &QToolButton::clicked, this, &PdfView::onPrevPage);
    connect(nextPageButton, &QToolButton::clicked, this, &PdfView::onNextPage);
}

void PdfView::setupActions()
{
    connect(searchEdit, &QLineEdit::textChanged, this, &PdfView::onSearchTextChanged);
    connect(searchEdit, &QLineEdit::returnPressed, this, &PdfView::onFindNext);
    connect(nextButton, &QToolButton::clicked, this, &PdfView::onFindNext);
    connect(prevButton, &QToolButton::clicked, this, &PdfView::onFindPrevious);

    auto* copySelection = new QAction(tr("Copy"), this);
    copySelection->setShortcut(QKeySequence::Copy);
    copySelection->setShortcutContext(Qt::WidgetWithChildrenShortcut);
    connect(copySelection, &QAction::triggered, this, &PdfView::onCopySelection);
    addAction(copySelection);

    auto* selectPage = new QAction(tr("Select all on page"), this);
    selectPage->setShortcut(QKeySequence::SelectAll);
    selectPage->setShortcutContext(Qt::WidgetWithChildrenShortcut);
    connect(selectPage, &QAction::triggered, pdfView,
            &PdfSelectionView::selectAllOnCurrentPage);
    addAction(selectPage);

    auto* copyPage = new QAction(tr("Copy page text"), this);
    connect(copyPage, &QAction::triggered, this, &PdfView::onCopyPageText);
    addAction(copyPage);

    auto* copyAll = new QAction(tr("Copy all text"), this);
    connect(copyAll, &QAction::triggered, this, &PdfView::onCopyAllText);
    addAction(copyAll);

    insertRegionAction = new QAction(tr("Insert region as image plane"), this);
    insertRegionAction->setEnabled(false);
    connect(insertRegionAction, &QAction::triggered,
            this, &PdfView::onInsertRegionAsImagePlane);
    addAction(insertRegionAction);

    importSketchAction = new QAction(tr("Import region as sketch (vector)"), this);
    importSketchAction->setEnabled(false);
    importSketchAction->setToolTip(
        tr("Extract vector paths from the region via pdftocairo and import into a Sketch.\n"
           "Requires poppler-utils (pdftocairo) installed on the system."));
    connect(importSketchAction, &QAction::triggered,
            this, &PdfView::onImportRegionToSketch);
    addAction(importSketchAction);

    connect(pdfView, &PdfSelectionView::selectionChanged,
            this, &PdfView::onSelectionChanged);
    connect(pdfView, &PdfSelectionView::regionChanged,
            this, &PdfView::onRegionChanged);
    connect(regionButton, &QToolButton::toggled,
            this, &PdfView::onDragModeToggled);

    setContextMenuPolicy(Qt::ActionsContextMenu);

    auto* findAction = new QAction(this);
    findAction->setShortcut(QKeySequence::Find);
    findAction->setShortcutContext(Qt::WidgetWithChildrenShortcut);
    connect(findAction, &QAction::triggered, this, [this] {
        searchEdit->setFocus();
        searchEdit->selectAll();
    });
    addAction(findAction);
}

bool PdfView::loadFile(const QString& fileName)
{
    const QPdfDocument::Error error = pdfDocument->load(fileName);

    if (error != QPdfDocument::Error::None) {
        QString reason;
        switch (error) {
            case QPdfDocument::Error::FileNotFound:
                reason = tr("The file was not found.");
                break;
            case QPdfDocument::Error::InvalidFileFormat:
                reason = tr("The file is not a valid PDF document.");
                break;
            case QPdfDocument::Error::IncorrectPassword:
                reason = tr("The document is password protected.");
                break;
            case QPdfDocument::Error::UnsupportedSecurityScheme:
                reason = tr("The document uses an unsupported security scheme.");
                break;
            default:
                reason = tr("The document could not be read.");
                break;
        }

        QMessageBox::information(this, tr("Failed to load PDF"), reason);
        return false;
    }

    setWindowFilePath(fileName);
    updateResultLabel();
    updatePageLabel();
    return true;
}

int PdfView::pageCount() const
{
    return pdfDocument ? pdfDocument->pageCount() : 0;
}

QString PdfView::allText() const
{
    QStringList pages;
    const int count = pageCount();
    pages.reserve(count);

    for (int page = 0; page < count; ++page) {
        const QPdfSelection selection = pdfDocument->getAllText(page);
        if (selection.isValid()) {
            pages.append(selection.text());
        }
    }

    return pages.join(QLatin1Char('\n'));
}

void PdfView::onPrevPage()
{
    auto* nav = pdfView->pageNavigator();
    if (nav->currentPage() > 0) {
        nav->jump(nav->currentPage() - 1, {});
    }
}

void PdfView::onNextPage()
{
    auto* nav = pdfView->pageNavigator();
    if (nav->currentPage() < pageCount() - 1) {
        nav->jump(nav->currentPage() + 1, {});
    }
}

void PdfView::onPageChanged(int page)
{
    Q_UNUSED(page);
    updatePageLabel();
}

void PdfView::updatePageLabel()
{
    const int count = pageCount();
    if (count < 1) {
        pageLabel->clear();
        prevPageButton->setEnabled(false);
        nextPageButton->setEnabled(false);
        return;
    }

    const int current = pdfView->pageNavigator()->currentPage();
    pageLabel->setText(tr(" %1 / %2 ").arg(current + 1).arg(count));
    prevPageButton->setEnabled(current > 0);
    nextPageButton->setEnabled(current < count - 1);
}

void PdfView::onSearchTextChanged(const QString& text)
{
    searchModel->setSearchString(text);
    currentResult = text.isEmpty() ? -1 : 0;

    if (!text.isEmpty() && searchModel->rowCount({}) > 0) {
        showResult(0);
    }

    updateResultLabel();
}

void PdfView::onFindNext()
{
    const int total = searchModel->rowCount({});
    if (total == 0) {
        return;
    }

    currentResult = (currentResult + 1) % total;
    showResult(currentResult);
    updateResultLabel();
}

void PdfView::onFindPrevious()
{
    const int total = searchModel->rowCount({});
    if (total == 0) {
        return;
    }

    currentResult = currentResult <= 0 ? total - 1 : currentResult - 1;
    showResult(currentResult);
    updateResultLabel();
}

void PdfView::showResult(int index)
{
    const QPdfLink link = searchModel->resultAtIndex(index);
    if (!link.isValid()) {
        return;
    }

    pdfView->pageNavigator()->jump(link.page(), link.location());
    pdfView->setCurrentSearchResultIndex(index);
}

void PdfView::updateResultLabel()
{
    const int total = searchModel->rowCount({});

    if (searchEdit->text().isEmpty()) {
        resultLabel->clear();
    }
    else if (total == 0) {
        resultLabel->setText(tr("No matches"));
    }
    else {
        resultLabel->setText(tr("%1 of %2").arg(currentResult + 1).arg(total));
    }

    prevButton->setEnabled(total > 0);
    nextButton->setEnabled(total > 0);
}

QString PdfView::pageText(int page) const
{
    if (page < 0 || page >= pageCount()) {
        return {};
    }

    const QPdfSelection sel = pdfDocument->getAllText(page);
    return sel.isValid() ? sel.text() : QString();
}

void PdfView::onCopySelection()
{
    // Fall back to the whole page when nothing is highlighted, so Ctrl+C
    // still does something useful.
    const QString text =
        pdfView->selectedText().isEmpty()
            ? pageText(pdfView->pageNavigator()->currentPage())
            : pdfView->selectedText();

    if (!text.isEmpty()) {
        QApplication::clipboard()->setText(text);
    }
}

void PdfView::onSelectionChanged(const QString& text)
{
    if (regionButton->isChecked()) {
        return;
    }
    if (text.isEmpty()) {
        selectionLabel->clear();
    }
    else {
        selectionLabel->setText(tr("%n character(s) selected", "", text.size()));
    }
}

void PdfView::onDragModeToggled(bool regionMode)
{
    pdfView->setDragMode(regionMode ? PdfSelectionView::DragMode::SelectRegion
                                    : PdfSelectionView::DragMode::SelectText);
}

void PdfView::onRegionChanged(bool hasRegion)
{
    insertRegionAction->setEnabled(hasRegion);
    importSketchAction->setEnabled(hasRegion);
    if (hasRegion) {
        const QRectF r = pdfView->regionRect();
        selectionLabel->setText(tr("Region %1 x %2 pt")
                                    .arg(qRound(r.width()))
                                    .arg(qRound(r.height())));
    }
    else {
        selectionLabel->clear();
    }
}

void PdfView::onInsertRegionAsImagePlane()
{
    const int page = pdfView->regionPage();
    const QRectF region = pdfView->regionRect();

    if (page < 0 || region.isEmpty() || pageCount() < 1) {
        return;
    }

    // Render the full page and cut the piece out ourselves.
    // setScaledClipRect() looks like the right tool but returns a rectangle
    // that drifts further off the further it is from the page origin, which
    // left crops offset and stretched. An A4 page at 300 DPI costs about
    // 35 MB, fine for a one-off.
    const qreal dpi = 300.0;
    const qreal scale = dpi / 72.0;
    const QSizeF pagePoints = pdfDocument->pagePointSize(page);
    const QSize pagePixels = (pagePoints * scale).toSize();

    const QImage pageImage = pdfDocument->render(page, pagePixels);
    if (pageImage.isNull()) {
        QMessageBox::warning(this,
                             tr("Could not crop"),
                             tr("Rendering page %1 failed.").arg(page + 1));
        return;
    }

    QRect clip(qRound(region.x() * scale),
               qRound(region.y() * scale),
               qRound(region.width() * scale),
               qRound(region.height() * scale));
    clip = clip.intersected(pageImage.rect());

    if (clip.isEmpty()) {
        return;
    }

    QImage image = pageImage.copy(clip);
    if (image.isNull()) {
        QMessageBox::warning(this,
                             tr("Could not crop"),
                             tr("Cropping the selected region failed."));
        return;
    }

    // Pages come back with premultiplied alpha over a transparent
    // background, which turns black if the alpha is simply dropped. White is
    // the safe default, but a transparent crop is handy as an overlay.
    QMessageBox background(this);
    background.setIcon(QMessageBox::Question);
    background.setWindowTitle(tr("Background"));
    background.setText(tr("Keep the page background transparent?"));
    background.setInformativeText(
        tr("A transparent background lets the underlay blend with what is\n"
           "behind it. An opaque one renders the crop on white, which is\n"
           "what a printed page looks like."));
    QAbstractButton* keepAlpha =
        background.addButton(tr("Transparent"), QMessageBox::AcceptRole);
    QAbstractButton* onWhite =
        background.addButton(tr("Opaque (white)"), QMessageBox::RejectRole);
    background.setDefaultButton(qobject_cast<QPushButton*>(onWhite));
    background.exec();

    if (background.clickedButton() != keepAlpha && image.hasAlphaChannel()) {
        QImage opaque(image.size(), QImage::Format_RGB32);
        opaque.fill(Qt::white);
        QPainter painter(&opaque);
        painter.drawImage(0, 0, image);
        painter.end();
        image = opaque;
    }

    // Record the resolution, or ImagePlane guesses one and the plane comes
    // out the wrong physical size.
    const int dotsPerMeter = qRound(dpi / 25.4 * 1000.0);
    image.setDotsPerMeterX(dotsPerMeter);
    image.setDotsPerMeterY(dotsPerMeter);

    // The crop has to live on disk: Image::ImagePlane keeps a path, not the
    // pixels. Offer to put it next to the document by default.
    QString suggested = QFileInfo(windowFilePath()).completeBaseName();
    if (suggested.isEmpty()) {
        suggested = QStringLiteral("region");
    }
    suggested += QStringLiteral("_p%1.png").arg(page + 1);

    App::Document* appDoc = App::GetApplication().getActiveDocument();
    QString startDir;
    if (appDoc && appDoc->FileName.getStrValue().length() > 0) {
        startDir = QFileInfo(QString::fromUtf8(appDoc->FileName.getValue())).absolutePath();
    }
    else {
        startDir = QFileInfo(windowFilePath()).absolutePath();
    }

    const QString target = QFileDialog::getSaveFileName(
        this,
        tr("Save cropped region"),
        QDir(startDir).filePath(suggested),
        tr("PNG image (*.png)")
    );

    if (target.isEmpty()) {
        return;
    }

    if (!image.save(target, "PNG")) {
        QMessageBox::warning(this,
                             tr("Could not save"),
                             tr("Cannot write %1.").arg(target));
        return;
    }

    if (!appDoc) {
        appDoc = App::GetApplication().newDocument();
    }

    const QFileInfo info(target);
    const std::string base =
        Base::Tools::escapeEncodeString(info.completeBaseName().toUtf8().constData());
    const std::string path =
        Base::Tools::escapeEncodeString(info.absoluteFilePath().toUtf8().constData());

    Gui::cmdAppDocumentArgs(appDoc, "addObject('Image::ImagePlane', '%s')", base);
    Gui::cmdAppDocumentArgs(appDoc, "ActiveObject.ImageFile = '%s'", path);
    Gui::cmdAppDocumentArgs(appDoc, "ActiveObject.Label = '%s'", base);
    Gui::cmdAppDocumentArgs(appDoc,
                            "ActiveObject.ViewObject.OpaqueBackground = %s",
                            background.clickedButton() == keepAlpha ? "False" : "True");
    Gui::cmdAppDocument(appDoc, "recompute()");
}

void PdfView::onImportRegionToSketch()
{
    const int page = pdfView->regionPage();
    const QRectF region = pdfView->regionRect();

    if (page < 0 || region.isEmpty() || pageCount() < 1) {
        return;
    }

    // Locate pdftocairo
    const QString pdftocairo =
        QStandardPaths::findExecutable(QStringLiteral("pdftocairo"));
    if (pdftocairo.isEmpty()) {
        QMessageBox::warning(
            this, tr("pdftocairo not found"),
            tr("The 'pdftocairo' tool (part of poppler-utils) is required\n"
               "to extract vector paths from a PDF.\n\n"
               "Install it with:\n"
               "  Ubuntu/Debian:  sudo apt install poppler-utils\n"
               "  Fedora:         sudo dnf install poppler-utils\n"
               "  Arch:           sudo pacman -S poppler"));
        return;
    }

    // Crop first, convert second. pdftocairo ignores -x/-y/-W/-H when writing
    // SVG, so cropping straight to SVG gives the whole page back. Cropping to
    // PDF does work, so we go through an intermediate file.
    const int cropX = static_cast<int>(region.x());
    const int cropY = static_cast<int>(region.y());
    const int cropW = static_cast<int>(std::ceil(region.width()));
    const int cropH = static_cast<int>(std::ceil(region.height()));

    const QString tmpPdf =
        QDir::tempPath() + QStringLiteral("/freecad_pdf_region.pdf");
    const QString tmpSvg =
        QDir::tempPath() + QStringLiteral("/freecad_pdf_region.svg");

    QStringList cropArgs;
    cropArgs << QStringLiteral("-pdf")
             << QStringLiteral("-f") << QString::number(page + 1)
             << QStringLiteral("-l") << QString::number(page + 1)
             << QStringLiteral("-x") << QString::number(cropX)
             << QStringLiteral("-y") << QString::number(cropY)
             << QStringLiteral("-W") << QString::number(cropW)
             << QStringLiteral("-H") << QString::number(cropH)
             << windowFilePath()
             << tmpPdf;

    QProcess crop;
    crop.start(pdftocairo, cropArgs);
    if (!crop.waitForFinished(30000) || crop.exitCode() != 0) {
        QMessageBox::warning(
            this, tr("pdftocairo failed"),
            tr("Could not crop the region into a PDF.\n\n%1")
                .arg(QString::fromUtf8(crop.readAllStandardError())));
        return;
    }

    QStringList svgArgs;
    svgArgs << QStringLiteral("-svg") << tmpPdf << tmpSvg;

    QProcess convert;
    convert.start(pdftocairo, svgArgs);
    if (!convert.waitForFinished(30000) || convert.exitCode() != 0) {
        QMessageBox::warning(
            this, tr("pdftocairo failed"),
            tr("Could not convert the cropped PDF to SVG.\n\n%1")
                .arg(QString::fromUtf8(convert.readAllStandardError())));
        return;
    }

    Base::Console().message("PdfView: crop %d x %d pt at %d,%d\n",
                            cropW, cropH, cropX, cropY);
    Base::Console().message("PdfView: intermediate PDF %s\n",
                            tmpPdf.toUtf8().constData());
    Base::Console().message("PdfView: intermediate SVG %s\n",
                            tmpSvg.toUtf8().constData());

    App::Document* appDoc = App::GetApplication().getActiveDocument();
    if (!appDoc) {
        appDoc = App::GetApplication().newDocument();
    }

    // The SVG came from the cropped PDF, so it holds only the selection.
    const QString script = QStringLiteral(
        "import importSVG, FreeCAD\n"
        "importSVG.insert('%1', FreeCAD.getDocument('%2').Name)\n")
        .arg(tmpSvg)
        .arg(QString::fromUtf8(appDoc->getName()));

    Base::Interpreter().runString(script.toUtf8().constData());

    // Temporaries are kept on purpose while the two-pass crop is being
    // checked; opening them is the quickest way to see what went wrong.
}

void PdfView::onCopyPageText()
{
    // QPdfView (the widget) exposes no selection API even in Qt 6.11, so
    // the closest useful action is copying the text of the visible page.
    const QString text = pageText(pdfView->pageNavigator()->currentPage());
    if (!text.isEmpty()) {
        QApplication::clipboard()->setText(text);
    }
}

void PdfView::onCopyAllText()
{
    const QString text = allText();
    if (!text.isEmpty()) {
        QApplication::clipboard()->setText(text);
    }
}

void PdfView::applyZoom(qreal factor)
{
    // currentPage is derived from the scroll position, so the way to keep the
    // page stable across a zoom is to move the scrollbars by the same ratio
    // the document just grew or shrank by. Jumping with the page navigator
    // does not work: QPdfView recomputes the scroll afterwards and overwrites
    // it.
    const qreal oldZoom = pdfView->zoomFactor();
    const qreal newZoom = qBound(ZoomMin, oldZoom * factor, ZoomMax);
    if (qFuzzyCompare(oldZoom, newZoom)) {
        return;
    }

    const int oldV = pdfView->verticalScrollBar()->value();
    const int oldH = pdfView->horizontalScrollBar()->value();

    pdfView->setZoomMode(QPdfView::ZoomMode::Custom);
    pdfView->setZoomFactor(newZoom);

    const qreal ratio = newZoom / oldZoom;
    QTimer::singleShot(0, this, [this, oldV, oldH, ratio] {
        pdfView->verticalScrollBar()->setValue(qRound(oldV * ratio));
        pdfView->horizontalScrollBar()->setValue(qRound(oldH * ratio));
        updatePageLabel();
    });
}

void PdfView::applyZoomMode(QPdfView::ZoomMode mode)
{
    // The resulting scale is not known in advance here, so hold the relative
    // position in the document instead of an absolute pixel offset.
    QScrollBar* vbar = pdfView->verticalScrollBar();
    const int oldMax = vbar->maximum();
    const qreal fraction = oldMax > 0 ? qreal(vbar->value()) / oldMax : 0.0;

    pdfView->setZoomMode(mode);

    QTimer::singleShot(0, this, [this, fraction] {
        QScrollBar* bar = pdfView->verticalScrollBar();
        bar->setValue(qRound(fraction * bar->maximum()));
        updatePageLabel();
    });
}

void PdfView::onZoomIn()
{
    applyZoom(ZoomStep);
}

void PdfView::onZoomOut()
{
    applyZoom(1.0 / ZoomStep);
}

void PdfView::onZoomReset()
{
    applyZoomMode(QPdfView::ZoomMode::FitToWidth);
}

void PdfView::print(QPrinter* printer)
{
    printTo(printer);
}

void PdfView::printTo(QPagedPaintDevice* device)
{
    const int count = pageCount();
    if (count < 1) {
        return;
    }

    QPainter painter(device);
    if (!painter.isActive()) {
        return;
    }

    const QRect target = device->pageLayout().paintRectPixels(device->logicalDpiX());

    for (int page = 0; page < count; ++page) {
        if (page > 0 && !device->newPage()) {
            break;
        }

        const QImage image = pdfDocument->render(page, target.size());
        if (image.isNull()) {
            continue;
        }

        // QPdfDocument renders with premultiplied alpha over a transparent
        // background; drawing on white keeps the page from turning black.
        painter.fillRect(target, Qt::white);
        painter.drawImage(target.topLeft(), image);
    }
}

bool PdfView::onMsg(const char* pMsg)
{
    if (strcmp("Save", pMsg) == 0 || strcmp("SaveAs", pMsg) == 0) {
        return false;
    }
    if (strcmp("Print", pMsg) == 0) {
        print();
        return true;
    }
    if (strcmp("PrintPdf", pMsg) == 0) {
        printPdf();
        return true;
    }
    if (strcmp("PrintPreview", pMsg) == 0) {
        printPreview();
        return true;
    }
    if (strcmp("Copy", pMsg) == 0) {
        onCopySelection();
        return true;
    }
    return false;
}

bool PdfView::onHasMsg(const char* pMsg) const
{
    if (strcmp("Print", pMsg) == 0 || strcmp("PrintPdf", pMsg) == 0
        || strcmp("PrintPreview", pMsg) == 0) {
        return pageCount() > 0;
    }
    if (strcmp("Copy", pMsg) == 0) {
        return pageCount() > 0;
    }
    return false;
}

#include "moc_PdfView.cpp"

#endif  // HAVE_QT_PDF_WIDGETS
