# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opening attached documents.

PDFs are handed to FreeCAD's own Gui::PdfView, which gives text selection,
full-text search, region cropping to an ImagePlane and vector import into
the document.  Rich text and plain text use a small read-only viewer here,
since the core has nothing equivalent.  Everything else goes to the desktop.
"""

import os
import shutil
import tempfile

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

from DocumentationObjects import (
    VIEWER_EXTERNAL,
    VIEWER_PDF,
    VIEWER_PLAINTEXT,
    VIEWER_RICHTEXT,
    viewer_for,
)

translate = FreeCAD.Qt.translate

# Viewers opened for an attachment belong to the document that holds it, but
# FreeCAD only closes views it knows about.  Ours are opened through
# FreeCADGui.open() and carry no document, so track them and close them when
# the owning document goes away.
_openViewers = {}  # (document name, object name) -> file path shown
_observer = None


def open_document(obj):
    """Open *obj* in the most capable viewer available."""
    path = obj.Proxy.resolvePath(obj)

    if not path or not os.path.exists(path):
        QtWidgets.QMessageBox.warning(
            FreeCADGui.getMainWindow(),
            translate("Documentation", "Document unavailable"),
            translate(
                "Documentation",
                "The file for '%s' could not be found.\n"
                "For linked documents, check that the path still exists.",
            )
            % obj.Label,
        )
        return

    name = getattr(obj, "FileName", "") or path
    kind = viewer_for(name)

    docname = obj.Document.Name if getattr(obj, "Document", None) else None
    objname = getattr(obj, "Name", None)

    if kind == VIEWER_PDF:
        _open_pdf(path, name, docname, objname)
    elif kind in (VIEWER_RICHTEXT, VIEWER_PLAINTEXT):
        if _activateExisting(path):
            return
        viewer = TextViewer(path, obj.Label, original_name=name)
        viewer.setWindowFilePath(path)
        _show(viewer)
        _register(docname, objname, path)
    else:
        open_externally(path)


def _activateExisting(path):
    """Raise the window already showing *path*, if there is one.

    Clicking the same attachment twice should return to its window rather
    than stack up duplicates.
    """
    main = FreeCADGui.getMainWindow()
    mdi = main.findChild(QtWidgets.QMdiArea) if main else None
    if mdi is None:
        return False

    wanted = os.path.abspath(path)
    for sub in mdi.subWindowList():
        widget = sub.widget()
        if widget is None:
            continue
        shown = widget.windowFilePath()
        if shown and os.path.abspath(shown) == wanted:
            if sub.isMinimized():
                sub.showNormal()
            mdi.setActiveSubWindow(sub)
            sub.raise_()
            return True
    return False


def _register(docname, objname, path):
    """Remember which window belongs to which attachment."""
    if not docname or not objname:
        return
    _openViewers[(docname, objname)] = path
    _installObserver()


def _installObserver():
    global _observer
    if _observer is not None:
        return
    _observer = _DocumentCloseObserver()
    FreeCADGui.addDocumentObserver(_observer)


def closeViewersFor(docname, objname=None):
    """Close the windows opened for a document, or for one attachment of it."""
    if objname is None:
        keys = [k for k in _openViewers if k[0] == docname]
    else:
        keys = [k for k in _openViewers if k == (docname, objname)]

    paths = [_openViewers.pop(k) for k in keys]
    if not paths:
        return

    main = FreeCADGui.getMainWindow()
    mdi = main.findChild(QtWidgets.QMdiArea) if main else None
    if mdi is None:
        return

    wanted = {os.path.abspath(p) for p in paths}
    for sub in list(mdi.subWindowList()):
        widget = sub.widget()
        if widget is None:
            continue
        shown = widget.windowFilePath()
        if shown and os.path.abspath(shown) in wanted:
            sub.close()

    for path in paths:
        # Embedded payloads are shown from a temporary copy; clean it up.
        if os.path.dirname(os.path.abspath(path)) == tempfile.gettempdir():
            try:
                os.remove(path)
            except OSError:
                pass


class _DocumentCloseObserver:
    """Closes attachment viewers when the document or the object goes away."""

    def slotDeletedObject(self, vobj):
        # A view provider arrives here, so the object is one step further in.
        obj = getattr(vobj, "Object", None)
        doc = getattr(obj, "Document", None)
        if obj is None or doc is None:
            return
        try:
            closeViewersFor(doc.Name, obj.Name)
        except Exception as exc:
            FreeCAD.Console.PrintLog(
                "Documentation: could not close the viewer for %s: %s\n"
                % (getattr(obj, "Name", "?"), exc)
            )

    def slotDeletedDocument(self, doc):
        # A Gui document is handed over here, and it has no Name of its own -
        # the name lives on the App document it wraps.
        name = getattr(getattr(doc, "Document", None), "Name", None)
        if not name:
            return
        try:
            closeViewersFor(name)
        except Exception as exc:  # never let an observer break closing
            FreeCAD.Console.PrintLog(
                "Documentation: could not close viewers for %s: %s\n" % (name, exc)
            )


def _open_pdf(path, original_name, docname=None, objname=None):
    """Open a PDF in FreeCAD's native PDF view.

    FreeCADGui.open() routes .pdf to Gui::PdfView.  Embedded payloads are
    stored by PropertyFileIncluded under a generated name with no suffix,
    so give the file a .pdf extension first or the routing will not fire.
    """
    target = path
    if os.path.splitext(path)[1].lower() != ".pdf":
        base = os.path.splitext(os.path.basename(original_name))[0] or "document"
        target = os.path.join(tempfile.gettempdir(), base + ".pdf")
        try:
            shutil.copyfile(path, target)
        except OSError:
            target = path

    if _activateExisting(target):
        return

    try:
        FreeCADGui.open(target)
        _register(docname, objname, target)
    except Exception:
        # No Qt PDF support compiled in, or the file could not be opened.
        open_externally(target)


def open_externally(path):
    """Hand the file to the desktop's default application."""
    url = QtCore.QUrl.fromLocalFile(os.path.abspath(path))
    if not QtGui.QDesktopServices.openUrl(url):
        QtWidgets.QMessageBox.warning(
            FreeCADGui.getMainWindow(),
            translate("Documentation", "Cannot open document"),
            translate(
                "Documentation", "No application is registered for this file type."
            ),
        )


def _show(widget):
    """Dock *widget* into the MDI area."""
    main = FreeCADGui.getMainWindow()
    mdi = main.findChild(QtWidgets.QMdiArea)
    if mdi is None:
        widget.setParent(main)
        widget.setWindowFlags(QtCore.Qt.Window)
        widget.show()
        return
    sub = mdi.addSubWindow(widget)
    sub.setWindowTitle(widget.windowTitle())
    sub.setStyleSheet("QMdiSubWindow { border: none; }")
    widget.layout().setContentsMargins(0, 0, 0, 0)
    sub.showMaximized()


class TextViewer(QtWidgets.QWidget):
    """Read-only viewer for RTF, HTML, Markdown and plain text."""

    def __init__(self, path, title, original_name=""):
        super().__init__()
        self.setWindowTitle(title)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        data = read_text(path)
        edit = QtWidgets.QTextEdit(readOnly=True)
        edit.setFrameShape(QtWidgets.QFrame.NoFrame)

        # PropertyFileIncluded renames files internally, so the stored path
        # may have lost its suffix; judge the format by the original name.
        suffix = os.path.splitext(original_name or path)[1].lstrip(".").lower()
        is_rtf = suffix == "rtf" or data.lstrip().startswith("{\\rtf")
        is_html = suffix in ("html", "htm")

        if is_rtf:
            edit.setPlainText(rtf_to_text(data))
        elif is_html or "<html" in data[:512].lower():
            edit.setHtml(data)
        else:
            edit.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
            edit.setPlainText(data)

        note = QtWidgets.QLabel()
        note.setVisible(False)
        if is_rtf:
            note.setText(
                translate(
                    "Documentation",
                    "RTF formatting is not rendered here. Use "
                    '"Open externally" for the fully formatted document.',
                )
            )
            note.setWordWrap(True)
            note.setVisible(True)

        external = QtWidgets.QPushButton(translate("Documentation", "Open externally"))
        external.clicked.connect(lambda: open_externally(path))

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(note, 1)
        bar.addWidget(external)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(edit)
        layout.addLayout(bar)


def read_text(path):
    """Read a text file, trying the encodings we are most likely to meet."""
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as handle:
                return handle.read()
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def rtf_to_text(data):
    """Strip RTF markup down to its plain text.

    Small on purpose: it handles the control words, escapes and groups that
    ordinary documents use, and drops the binary groups that carry no
    readable text.  Formatting is lost.
    """
    skip_groups = (
        "fonttbl", "colortbl", "stylesheet", "info", "pict",
        "object", "themedata", "datastore", "latentstyles", "listtable",
        "generator", "filetbl", "revtbl",
    )

    out = []
    depth = 0
    ignore_until = None
    index = 0
    length = len(data)

    while index < length:
        char = data[index]

        if char == "{":
            depth += 1
            index += 1
            continue

        if char == "}":
            if ignore_until is not None and depth <= ignore_until:
                ignore_until = None
            depth -= 1
            index += 1
            continue

        if char == "\\":
            if index + 1 < length and data[index + 1] in "\\{}":
                if ignore_until is None:
                    out.append(data[index + 1])
                index += 2
                continue

            if data[index + 1 : index + 2] == "'":
                hex_digits = data[index + 2 : index + 4]
                try:
                    if ignore_until is None:
                        out.append(bytes([int(hex_digits, 16)]).decode("cp1251"))
                except (ValueError, UnicodeDecodeError):
                    pass
                index += 4
                continue

            cursor = index + 1
            while cursor < length and data[cursor].isalpha():
                cursor += 1
            word = data[index + 1 : cursor]

            if cursor < length and (data[cursor] == "-" or data[cursor].isdigit()):
                cursor += 1
                while cursor < length and data[cursor].isdigit():
                    cursor += 1

            if cursor < length and data[cursor] == " ":
                cursor += 1

            if word in skip_groups:
                ignore_until = depth
            elif word in ("par", "line", "sect"):
                if ignore_until is None:
                    out.append("\n")
            elif word == "tab":
                if ignore_until is None:
                    out.append("\t")

            index = cursor
            continue

        if ignore_until is None and char not in "\r\n":
            out.append(char)
        index += 1

    text = "".join(out)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()
