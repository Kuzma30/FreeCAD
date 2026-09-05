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

#ifndef GUI_PDFVIEW_H
#define GUI_PDFVIEW_H

#ifdef HAVE_QT_PDF_WIDGETS

#include <QString>

#include <Gui/MDIView.h>

#include <QPdfSelection>
#include <QPdfView>

#include <optional>

class QAction;
class QLabel;
class QLineEdit;
class QPagedPaintDevice;
class QToolButton;
class QPdfDocument;
class QPdfSearchModel;

namespace Gui
{

/**
 * QPdfView with mouse text selection.
 *
 * QPdfView has no selection API, not even in Qt 6.11, and does not say where
 * it put each page. This subclass works the layout out again from the
 * properties it does expose - zoomMode, zoomFactor, pageMode, documentMargins
 * and pageSpacing - and uses it to turn mouse positions into the page
 * coordinates getSelection() expects.
 *
 * That duplicates QPdfViewPrivate::calculateDocumentLayout(), so a change
 * upstream would silently move the selection. pageRect() returns a null rect
 * when it cannot be sure, and callers must check.
 */
class GuiExport PdfSelectionView: public QPdfView
{
    Q_OBJECT

public:
    /// What a mouse drag does on the page.
    enum class DragMode
    {
        SelectText,   //!< highlight words, backed by QPdfDocument::getSelection()
        SelectRegion  //!< rubber-band a rectangle, for cropping to an image
    };

    explicit PdfSelectionView(QWidget* parent = nullptr);

    void setDragMode(DragMode mode);
    DragMode dragMode() const
    {
        return mode;
    }

    /// Page the region was drawn on, -1 when there is no region.
    int regionPage() const
    {
        return regionPageIndex;
    }
    /// The marked region in page points, empty when there is none.
    QRectF regionRect() const
    {
        return region;
    }
    void clearRegion();
    /// Drop the cached page layout, e.g. after loading a document.
    void invalidateLayout();

    /// Text currently highlighted, empty when there is no selection.
    QString selectedText() const;

    /// Select every word on the page that is currently in view.
    void selectAllOnCurrentPage();

    void clearSelection();

Q_SIGNALS:
    void selectionChanged(const QString& text);
    void regionChanged(bool hasRegion);

protected:
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void paintEvent(QPaintEvent* event) override;

private:
    /// Points-to-pixels factor currently used to render pages.
    qreal renderScale() const;
    /// Geometry of *page* in viewport coordinates; null rect when unknown.
    QRectF pageRect(int page) const;
    /// Rebuild layoutCache when the scale or the document changed.
    void ensureLayout() const;
    /// First and last page that the current page mode puts on screen.
    void visiblePageRange(int& first, int& last) const;
    /// Translate a viewport position into a page index plus page points.
    bool mapToPage(const QPointF& pos, int& page, QPointF& pagePos) const;
    void updateSelection(const QPointF& to);
    void paintRegion();

    int anchorPage {-1};
    QPointF anchorPos;
    std::optional<QPdfSelection> selection;
    bool dragging {false};

    // Page rectangles in document coordinates, i.e. before the scroll offset
    // is applied.  Recomputing these per mouse event was quadratic in the
    // page count and made dragging unusable on long documents.
    mutable QList<QRectF> layoutCache;
    mutable qreal cachedScale {-1.0};
    mutable int cachedFirst {-1};
    mutable int cachedLast {-1};

    DragMode mode {DragMode::SelectText};
    int regionPageIndex {-1};
    QRectF region;
};


/**
 * A viewer for PDF documents backed by the Qt PDF module.
 *
 * Unlike ImageView, which rasterises a page into a QImage, this view keeps
 * the document itself, so the text stays live: it can be searched with
 * QPdfSearchModel and extracted with QPdfDocument::getSelection().
 *
 * The class is only compiled when Qt6::PdfWidgets was found at configure
 * time (HAVE_QT_PDF_WIDGETS).
 */
class GuiExport PdfView: public MDIView
{
    Q_OBJECT

public:
    explicit PdfView(QWidget* parent = nullptr);
    ~PdfView() override;

    /// Load a PDF file. Returns false and shows a message on failure.
    bool loadFile(const QString& fileName);

    const char* getName() const override
    {
        return "PdfView";
    }

    bool onMsg(const char* pMsg) override;
    bool onHasMsg(const char* pMsg) const override;

    /** @name Printing */
    //@{
    using MDIView::print;
    void print(QPrinter* printer) override;
    void printTo(QPagedPaintDevice* device);
    //@}

    /// Text of the whole document, page by page, joined with newlines.
    QString allText() const;

    /// Text of a single page, empty when the page has no extractable text.
    QString pageText(int page) const;

    /// Number of pages, or 0 when nothing is loaded.
    int pageCount() const;

private Q_SLOTS:
    void onSearchTextChanged(const QString& text);
    void onFindNext();
    void onFindPrevious();
    void onCopyPageText();
    void onCopyAllText();
    void onCopySelection();
    void onSelectionChanged(const QString& text);
    void onDragModeToggled(bool regionMode);
    void onRegionChanged(bool hasRegion);
    void onInsertRegionAsImagePlane();
    void onImportRegionToSketch();
    void onZoomIn();
    void onZoomOut();
    void onZoomReset();
    void onPrevPage();
    void onNextPage();
    void onPageChanged(int page);
    void updatePageLabel();

private:
    /// Change zoom while keeping the same content under the viewport.
    void applyZoom(qreal factor);
    /// Switch to a zoom mode, preserving the scroll fraction.
    void applyZoomMode(QPdfView::ZoomMode mode);

    void setupUi();
    void setupActions();
    /// Move the view to search result *index* and update the counter label.
    void showResult(int index);
    void updateResultLabel();

    QPdfDocument* pdfDocument {nullptr};
    QPdfSearchModel* searchModel {nullptr};
    PdfSelectionView* pdfView {nullptr};

    QLineEdit* searchEdit {nullptr};
    QToolButton* prevPageButton {nullptr};
    QToolButton* nextPageButton {nullptr};
    QLabel* pageLabel {nullptr};
    QLabel* resultLabel {nullptr};
    QLabel* selectionLabel {nullptr};
    QToolButton* regionButton {nullptr};
    QAction* insertRegionAction {nullptr};
    QAction* importSketchAction {nullptr};
    QToolButton* prevButton {nullptr};
    QToolButton* nextButton {nullptr};

    int currentResult {-1};
};

}  // namespace Gui

#endif  // HAVE_QT_PDF_WIDGETS

#endif  // GUI_PDFVIEW_H
