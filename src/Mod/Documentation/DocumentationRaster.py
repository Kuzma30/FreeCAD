# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rasterising PDF pages into Image::ImagePlane objects.

This is the "Image formats" side of importing a PDF: instead of opening a
viewer, each chosen page is rendered to a PNG and placed in the document as
an ImagePlane, so it can be used as a drawing underlay.
"""

import os
import tempfile

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

translate = FreeCAD.Qt.translate

DEFAULT_DPI = 300
PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Documentation"


def _params():
    return FreeCAD.ParamGet(PARAM_PATH)


def defaultDpi():
    """Rasterisation resolution, from preferences."""
    return _params().GetInt("RasterDpi", DEFAULT_DPI)


def setDefaultDpi(dpi):
    _params().SetInt("RasterDpi", int(dpi))


def defaultOpaqueBackground():
    """Whether rasterised pages get a white background instead of alpha."""
    return _params().GetBool("OpaqueBackground", True)


def setDefaultOpaqueBackground(value):
    _params().SetBool("OpaqueBackground", bool(value))


def pageCount(path):
    """Number of pages in *path*, or 0 when it cannot be read."""
    reader = QtGui.QImageReader(path)
    count = reader.imageCount()
    return count if count > 0 else (1 if reader.canRead() else 0)


def renderPage(path, page, dpi):
    """Render one page of a PDF to a QImage, alpha intact.

    The background is deliberately left transparent: flattening here would
    bake the choice into the PNG, and ImagePlane's OpaqueBackground toggle
    could never undo it.

    QImageReader drives the Qt PDF image plugin, which reports the page in
    points; scaling the requested size gives the resolution asked for.
    """
    reader = QtGui.QImageReader(path)
    reader.setAutoTransform(True)
    if page > 0:
        reader.jumpToImage(page)

    natural = reader.size()
    if natural.isValid() and natural.width() > 0:
        # The plugin reports pages at 72 dpi; ask for the size we actually want.
        scale = float(dpi) / 72.0
        reader.setScaledSize(
            QtCore.QSize(round(natural.width() * scale), round(natural.height() * scale))
        )

    image = reader.read()
    if image.isNull():
        return image

    dots = round(dpi / 25.4 * 1000.0)
    image.setDotsPerMeterX(dots)
    image.setDotsPerMeterY(dots)
    return image


def parsePages(text, total):
    """Parse "1,3,5-8" into zero-based page indices; empty list on error."""
    pages = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, _, last = part.partition("-")
            try:
                first, last = int(first), int(last)
            except ValueError:
                return []
            if not (1 <= first <= last <= total):
                return []
            pages.extend(i - 1 for i in range(first, last + 1) if i - 1 not in pages)
        else:
            try:
                page = int(part)
            except ValueError:
                return []
            if not 1 <= page <= total:
                return []
            if page - 1 not in pages:
                pages.append(page - 1)
    return sorted(pages)


class RasterOptionsDialog(QtWidgets.QDialog):
    """Ask which pages to rasterise, at what resolution."""

    def __init__(self, filename, total, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate("Documentation", "Import PDF as image"))
        self.setMinimumWidth(420)
        self._total = total

        info = QtWidgets.QLabel(
            translate("Documentation", "\u201c%s\u201d has %s page(s).")
            % (os.path.basename(filename), total)
        )
        info.setWordWrap(True)

        self._pages = QtWidgets.QLineEdit("1")
        self._pages.setPlaceholderText(translate("Documentation", "e.g. 1,3,5-8 or all"))
        self._pages.setEnabled(total > 1)
        if total == 1:
            self._pages.setText("1")

        self._dpi = QtWidgets.QSpinBox()
        self._dpi.setRange(30, 1200)
        self._dpi.setSingleStep(50)
        self._dpi.setSuffix(" dpi")
        self._dpi.setValue(defaultDpi())
        self._dpi.setToolTip(
            translate(
                "Documentation",
                "Rasterisation resolution. Higher values give a sharper "
                "underlay at the cost of memory.",
            )
        )

        self._opaque = QtWidgets.QCheckBox(
            translate("Documentation", "Opaque (white) background")
        )
        self._opaque.setChecked(defaultOpaqueBackground())
        self._opaque.setToolTip(
            translate(
                "Documentation",
                "Uncheck to keep the page background transparent.",
            )
        )

        form = QtWidgets.QFormLayout()
        form.addRow(translate("Documentation", "Pages:"), self._pages)
        form.addRow(translate("Documentation", "Resolution:"), self._dpi)
        form.addRow("", self._opaque)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._pages.setFocus()
        self._pages.selectAll()
        self._result = []

    def _accept(self):
        text = self._pages.text().strip()
        if text.lower() == "all":
            self._result = list(range(self._total))
        else:
            self._result = parsePages(text, self._total)

        if not self._result:
            QtWidgets.QMessageBox.warning(
                self,
                translate("Documentation", "Invalid page selection"),
                translate(
                    "Documentation",
                    "Use page numbers between 1 and %s, commas and dashes.\n"
                    "Example: 1,3,5-8",
                )
                % self._total,
            )
            return

        setDefaultDpi(self._dpi.value())
        setDefaultOpaqueBackground(self._opaque.isChecked())
        self.accept()

    def pages(self):
        return self._result

    def dpi(self):
        return self._dpi.value()

    def opaqueBackground(self):
        return self._opaque.isChecked()


def rasterToImagePlanes(filename, doc=None, pages=None, dpi=None, opaque=None):
    """Render pages of *filename* into ImagePlane objects.

    With no explicit *pages* and a GUI available, the user is asked. Returns
    the created objects.
    """
    if doc is None:
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()

    total = pageCount(filename)
    if total < 1:
        if FreeCAD.GuiUp:
            QtWidgets.QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                translate("Documentation", "Cannot read document"),
                translate("Documentation", "No pages could be read from %s.") % filename,
            )
        return []

    if pages is None:
        if FreeCAD.GuiUp:
            dialog = RasterOptionsDialog(filename, total, FreeCADGui.getMainWindow())
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return []
            pages, dpi, opaque = dialog.pages(), dialog.dpi(), dialog.opaqueBackground()
        else:
            pages = [0]

    if dpi is None:
        dpi = defaultDpi()
    if opaque is None:
        opaque = defaultOpaqueBackground()

    base = os.path.splitext(os.path.basename(filename))[0] or "page"
    outdir = os.path.dirname(os.path.abspath(filename))
    if not os.access(outdir, os.W_OK):
        outdir = tempfile.gettempdir()

    created = []
    doc.openTransaction("Import PDF as image")
    try:
        for page in pages:
            image = renderPage(filename, page, dpi)
            if image.isNull():
                FreeCAD.Console.PrintWarning(
                    "Documentation: page %d of %s could not be rendered.\n"
                    % (page + 1, filename)
                )
                continue

            suffix = "_p%d" % (page + 1) if total > 1 else ""
            target = os.path.join(outdir, "%s%s.png" % (base, suffix))
            if not image.save(target, "PNG"):
                FreeCAD.Console.PrintWarning(
                    "Documentation: could not write %s.\n" % target
                )
                continue

            obj = doc.addObject("Image::ImagePlane", base + suffix)
            obj.ImageFile = target
            obj.Label = base + suffix
            # Match the pixel size at the requested resolution so the plane
            # comes out at the page's real dimensions.
            obj.XSize = image.width() / dpi * 25.4
            obj.YSize = image.height() / dpi * 25.4
            _applyTransparency(obj, opaque)
            created.append(obj)
    finally:
        doc.commitTransaction()

    doc.recompute()
    return created


def _applyTransparency(obj, opaque):
    """Set the ImagePlane background option when the build provides it."""
    vobj = getattr(obj, "ViewObject", None)
    if vobj is None:
        return
    if "OpaqueBackground" in vobj.PropertiesList:
        vobj.OpaqueBackground = bool(opaque)
