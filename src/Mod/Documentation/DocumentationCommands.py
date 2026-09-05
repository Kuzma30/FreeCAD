# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commands for the Documentation workbench."""

import os
import shutil
import tempfile

import FreeCAD

translate = FreeCAD.Qt.translate
QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

import DocumentationObjects as DocObjects
from ViewProviders import icon_path


FILE_FILTER = (
    "Documents (*.pdf *.rtf *.doc *.docx *.odt *.txt *.md *.html *.csv);;"
    "PDF (*.pdf);;"
    "Text (*.rtf *.txt *.md *.html);;"
    "All files (*)"
)


def _main_window():
    return FreeCADGui.getMainWindow()


def _selected_group():
    """Return a documentation group from the selection, if any."""
    for obj in FreeCADGui.Selection.getSelection():
        if getattr(obj, "Proxy", None) is None:
            continue
        if getattr(obj.Proxy, "Type", "") == DocObjects.DocumentationGroup.Type:
            return obj
    return None


def _selected_parent():
    """Return a suitable parent for a new documentation folder.

    Returns one of:
    - A Documentation group (to nest folders)
    - A Body, Part or any object with Group extension (to attach docs to a part)
    - None (will create at document root level)
    """
    for obj in FreeCADGui.Selection.getSelection():
        proxy = getattr(obj, "Proxy", None)
        # Our own documentation group
        if proxy is not None and getattr(proxy, "Type", "") == DocObjects.DocumentationGroup.Type:
            return obj
        # FreeCAD Body, Part, or anything that can hold children
        if hasattr(obj, "addObject"):
            return obj
    return None


def _ensure_document():
    if FreeCAD.ActiveDocument is None:
        FreeCAD.newDocument()
    return FreeCAD.ActiveDocument


class _Command:
    """Base class supplying the bits every command repeats."""

    icon = ""
    menu = ""
    tip = ""

    def GetResources(self):
        return {
            "Pixmap": icon_path(self.icon),
            "MenuText": self.menu,
            "ToolTip": self.tip,
        }

    def IsActive(self):
        return True


class AddDocument(_Command):
    icon = "Documentation_AddDocument.svg"
    menu = QT_TRANSLATE_NOOP("Documentation_AddDocument", "Attach document")
    tip = QT_TRANSLATE_NOOP(
        "Documentation_AddDocument",
        "Attach a PDF, RTF or other file to the model.\n"
        "Embedded files are stored inside the FCStd.",
    )

    def Activated(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            _main_window(),
            translate("Documentation", "Select documents to attach"),
            "",
            FILE_FILTER,
        )
        if not paths:
            return

        embed = self._askEmbed(paths)
        if embed is None:
            return

        doc = _ensure_document()
        parent = _selected_parent()

        doc.openTransaction("Attach document")
        created = []
        try:
            for path in paths:
                created.append(DocObjects.make_document(path, embed=embed, parent=parent))
        finally:
            doc.commitTransaction()
        doc.recompute()

        # Attaching a single document usually means the user wants to see it.
        if len(created) == 1:
            from DocumentationViewers import open_document

            open_document(created[0])

    def _askEmbed(self, paths):
        """Ask how the files should be stored; None means cancelled."""
        total = 0
        for path in paths:
            try:
                total += os.path.getsize(path)
            except OSError:
                pass

        box = QtWidgets.QMessageBox(_main_window())
        box.setWindowTitle(translate("Documentation", "How should this be stored?"))
        box.setText(
            translate(
                "Documentation",
                "Embedding copies the file into the FCStd, so the model stays "
                "self-contained. Linking keeps only the path, leaving the FCStd small.",
            )
        )
        box.setInformativeText(
            translate("Documentation", "Selected: %s file(s), %s")
            % (len(paths), DocObjects.human_size(total))
        )
        embed_btn = box.addButton(
            translate("Documentation", "Embed in FCStd"), QtWidgets.QMessageBox.AcceptRole
        )
        link_btn = box.addButton(
            translate("Documentation", "Link to file"), QtWidgets.QMessageBox.AcceptRole
        )
        box.addButton(QtWidgets.QMessageBox.Cancel)
        box.setDefaultButton(embed_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is embed_btn:
            return True
        if clicked is link_btn:
            return False
        return None


class AddNote(_Command):
    icon = "Documentation_AddNote.svg"
    menu = QT_TRANSLATE_NOOP("Documentation_AddNote", "Add note")
    tip = QT_TRANSLATE_NOOP(
        "Documentation_AddNote",
        "Write a rich-text note and store it inside the model",
    )

    def Activated(self):
        dialog = _RichNoteDialog(_main_window())
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        label = dialog.titleText() or translate("Documentation", "Note")
        html = dialog.bodyHtml()

        doc = _ensure_document()
        temp = _write_temp_html(label, html)

        doc.openTransaction("Add note")
        try:
            obj = DocObjects.make_document(
                temp, embed=True, parent=_selected_parent(), label=label
            )
            obj.Description = translate("Documentation", "Note written in FreeCAD")
        finally:
            doc.commitTransaction()
        doc.recompute()

        try:
            os.remove(temp)
        except OSError:
            pass


class _RichNoteDialog(QtWidgets.QDialog):
    """Dialog with a title field, a formatting toolbar and a rich-text body."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate("Documentation", "New note"))
        self.resize(620, 500)

        self._title = QtWidgets.QLineEdit()
        self._title.setPlaceholderText(translate("Documentation", "Title"))

        self._body = QtWidgets.QTextEdit()
        self._body.setAcceptRichText(True)

        toolbar = self._makeToolbar()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addLayout(toolbar)
        layout.addWidget(self._body)
        layout.addWidget(buttons)

    def titleText(self):
        return self._title.text().strip()

    def bodyHtml(self):
        return self._body.toHtml()

    def _makeToolbar(self):
        bar = QtWidgets.QHBoxLayout()

        bold = QtWidgets.QToolButton(text="B")
        bold.setCheckable(True)
        bold.setStyleSheet("font-weight: bold;")
        bold.toggled.connect(lambda on: self._body.setFontWeight(
            QtGui.QFont.Bold if on else QtGui.QFont.Normal
        ))

        italic = QtWidgets.QToolButton(text="I")
        italic.setCheckable(True)
        italic.setStyleSheet("font-style: italic;")
        italic.toggled.connect(lambda on: self._body.setFontItalic(on))

        underline = QtWidgets.QToolButton(text="U")
        underline.setCheckable(True)
        underline.setStyleSheet("text-decoration: underline;")
        underline.toggled.connect(lambda on: self._body.setFontUnderline(on))

        sep1 = QtWidgets.QFrame(frameShape=QtWidgets.QFrame.VLine)

        bullet = QtWidgets.QToolButton(text="\u2022 List")
        bullet.clicked.connect(self._toggleBulletList)

        sep2 = QtWidgets.QFrame(frameShape=QtWidgets.QFrame.VLine)

        link = QtWidgets.QToolButton(text="\U0001F517 Link")
        link.clicked.connect(self._insertLink)

        size_box = QtWidgets.QComboBox()
        for s in (8, 10, 12, 14, 18, 24):
            size_box.addItem(str(s), s)
        size_box.setCurrentIndex(2)  # 12
        size_box.currentIndexChanged.connect(
            lambda: self._body.setFontPointSize(
                float(size_box.currentData())
            )
        )

        for w in (bold, italic, underline, sep1, bullet, sep2, link):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(QtWidgets.QLabel(translate("Documentation", "Size:")))
        bar.addWidget(size_box)

        # Keep toggle buttons in sync when the cursor moves into styled text
        self._bold_btn = bold
        self._italic_btn = italic
        self._underline_btn = underline
        self._body.cursorPositionChanged.connect(self._syncToolbar)

        return bar

    def _syncToolbar(self):
        fmt = self._body.currentCharFormat()
        self._bold_btn.blockSignals(True)
        self._bold_btn.setChecked(fmt.fontWeight() >= QtGui.QFont.Bold)
        self._bold_btn.blockSignals(False)
        self._italic_btn.blockSignals(True)
        self._italic_btn.setChecked(fmt.fontItalic())
        self._italic_btn.blockSignals(False)
        self._underline_btn.blockSignals(True)
        self._underline_btn.setChecked(fmt.fontUnderline())
        self._underline_btn.blockSignals(False)

    def _toggleBulletList(self):
        cursor = self._body.textCursor()
        lst = cursor.currentList()
        if lst:
            # Remove list formatting
            block_fmt = QtGui.QTextBlockFormat()
            cursor.setBlockFormat(block_fmt)
        else:
            lst_fmt = QtGui.QTextListFormat()
            lst_fmt.setStyle(QtGui.QTextListFormat.ListDisc)
            cursor.createList(lst_fmt)

    def _insertLink(self):
        url, ok = QtWidgets.QInputDialog.getText(
            self,
            translate("Documentation", "Insert link"),
            translate("Documentation", "URL:"),
        )
        if not ok or not url.strip():
            return
        text = self._body.textCursor().selectedText() or url
        self._body.insertHtml(
            '<a href="%s">%s</a> ' % (url.strip(), text)
        )


class AddGroup(_Command):
    icon = "Documentation_Group.svg"
    menu = QT_TRANSLATE_NOOP("Documentation_AddGroup", "Add folder")
    tip = QT_TRANSLATE_NOOP(
        "Documentation_AddGroup",
        "Create a documentation folder.\n"
        "Select a Body, Part or folder first to nest it there.",
    )

    def Activated(self):
        doc = _ensure_document()
        doc.openTransaction("Add documentation folder")
        try:
            DocObjects.make_group(parent=_selected_parent())
        finally:
            doc.commitTransaction()
        doc.recompute()


class OpenDocument(_Command):
    icon = "Documentation_Open.svg"
    menu = QT_TRANSLATE_NOOP("Documentation_Open", "Open")
    tip = QT_TRANSLATE_NOOP("Documentation_Open", "Open the selected document")

    def Activated(self):
        from DocumentationViewers import open_document

        for obj in _selected_documents():
            open_document(obj)

    def IsActive(self):
        return bool(_selected_documents())


class ExportDocument(_Command):
    icon = "Documentation_Export.svg"
    menu = QT_TRANSLATE_NOOP("Documentation_Export", "Save a copy")
    tip = QT_TRANSLATE_NOOP(
        "Documentation_Export", "Write the selected document back out to disk"
    )

    def Activated(self):
        for obj in _selected_documents():
            export_document(obj)

    def IsActive(self):
        return bool(_selected_documents())


class ReplaceDocument(_Command):
    icon = "Documentation_Replace.svg"
    menu = QT_TRANSLATE_NOOP("Documentation_Replace", "Replace file")
    tip = QT_TRANSLATE_NOOP(
        "Documentation_Replace", "Swap in a new revision, keeping the metadata"
    )

    def Activated(self):
        selection = _selected_documents()
        if selection:
            replace_document(selection[0])

    def IsActive(self):
        return len(_selected_documents()) == 1


def _selected_documents():
    result = []
    for obj in FreeCADGui.Selection.getSelection():
        proxy = getattr(obj, "Proxy", None)
        if proxy is not None and getattr(proxy, "Type", "") == DocObjects.AttachedDocument.Type:
            result.append(obj)
    return result


def _write_temp_html(label, html):
    """Write *html* to a temporary file named after *label*.

    The payload only has to survive until PropertyFileIncluded has copied it
    into the document, so the system temp directory is the right place for
    it - not the user config directory.
    """
    handle, path = tempfile.mkstemp(prefix=_slug(label) + "_", suffix=".html")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(html)
    return path


def _slug(text):
    keep = "-_. "
    cleaned = "".join(c for c in text if c.isalnum() or c in keep).strip()
    return cleaned.replace(" ", "_") or "note"


def export_document(obj):
    """Write the payload of *obj* to a location the user picks."""
    source = obj.Proxy.resolvePath(obj)
    if not source or not os.path.exists(source):
        QtWidgets.QMessageBox.warning(
            _main_window(),
            translate("Documentation", "Document unavailable"),
            translate("Documentation", "There is no file to save for '%s'.") % obj.Label,
        )
        return

    target, _ = QtWidgets.QFileDialog.getSaveFileName(
        _main_window(),
        translate("Documentation", "Save a copy"),
        obj.FileName or obj.Label,
    )
    if not target:
        return

    try:
        shutil.copyfile(source, target)
    except OSError as exc:
        QtWidgets.QMessageBox.critical(
            _main_window(),
            translate("Documentation", "Could not save"),
            str(exc),
        )


def replace_document(obj):
    """Point *obj* at a new file, leaving its metadata alone."""
    path, _ = QtWidgets.QFileDialog.getOpenFileName(
        _main_window(),
        translate("Documentation", "Select the new revision"),
        "",
        FILE_FILTER,
    )
    if not path:
        return

    doc = obj.Document
    doc.openTransaction("Replace document")
    try:
        if obj.Embedded:
            obj.EmbeddedFile = path
        else:
            obj.ExternalFile = path
        obj.Proxy.refreshMetadata(obj)
    finally:
        doc.commitTransaction()
    doc.recompute()


def edit_note(obj):
    """Open the rich-text editor for an existing note."""
    path = obj.Proxy.resolvePath(obj)
    if not path or not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
    except OSError:
        return

    dialog = _RichNoteDialog(_main_window())
    dialog.setWindowTitle(
        translate("Documentation", "Edit: %s") % obj.Label
    )
    dialog._title.setText(obj.Label)
    dialog._body.setHtml(html)

    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return

    label = dialog.titleText() or obj.Label
    new_html = dialog.bodyHtml()

    doc = obj.Document
    temp = _write_temp_html(label, new_html)

    doc.openTransaction("Edit note")
    try:
        obj.Label = label
        if obj.Embedded:
            obj.EmbeddedFile = temp
        else:
            obj.ExternalFile = temp
        obj.Proxy.refreshMetadata(obj)
    finally:
        doc.commitTransaction()
    doc.recompute()

    try:
        os.remove(temp)
    except OSError:
        pass


class EditNote(_Command):
    icon = "Documentation_EditNote.svg"
    menu = QT_TRANSLATE_NOOP("Documentation_EditNote", "Edit note")
    tip = QT_TRANSLATE_NOOP(
        "Documentation_EditNote",
        "Edit the selected HTML/text note in the rich-text editor",
    )

    def Activated(self):
        selection = _selected_documents()
        if selection:
            edit_note(selection[0])

    def IsActive(self):
        docs = _selected_documents()
        if len(docs) != 1:
            return False
        from DocumentationObjects import viewer_for, VIEWER_RICHTEXT, VIEWER_PLAINTEXT
        kind = viewer_for(docs[0].FileName)
        return kind in (VIEWER_RICHTEXT, VIEWER_PLAINTEXT)


COMMANDS = {
    "Documentation_AddDocument": AddDocument,
    "Documentation_AddNote": AddNote,
    "Documentation_AddGroup": AddGroup,
    "Documentation_Open": OpenDocument,
    "Documentation_EditNote": EditNote,
    "Documentation_Export": ExportDocument,
    "Documentation_Replace": ReplaceDocument,
}


def register():
    for name, cls in COMMANDS.items():
        FreeCADGui.addCommand(name, cls())


# ---------------------------------------------------------------------------
# Offering to keep an exported PDF with the model
# ---------------------------------------------------------------------------

_OFFER_PARAM = "User parameter:BaseApp/Preferences/Mod/Documentation"


def offerToAttachExport(path, parent=None):
    """Ask whether a freshly exported PDF should be attached to the model.

    Called after an export finishes.  Users who never want this can turn it
    off from the dialog itself, which is why the prompt carries a checkbox
    rather than only Yes/No.
    """
    params = FreeCAD.ParamGet(_OFFER_PARAM)
    if not params.GetBool("OfferToAttachExports", True):
        return None

    if not path or not os.path.exists(path):
        return None

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None

    box = QtWidgets.QMessageBox(parent or _main_window())
    box.setIcon(QtWidgets.QMessageBox.Question)
    box.setWindowTitle(translate("Documentation", "Keep this export with the model?"))
    box.setText(
        translate(
            "Documentation",
            "Attach \u201c%s\u201d to the document so it travels with the model?",
        )
        % os.path.basename(path)
    )
    box.setInformativeText(
        translate(
            "Documentation",
            "The file is embedded in the FCStd and appears under Documentation.",
        )
    )
    box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    box.setDefaultButton(QtWidgets.QMessageBox.Yes)

    remember = QtWidgets.QCheckBox(translate("Documentation", "Do not ask again"))
    box.setCheckBox(remember)

    answer = box.exec()

    if remember.isChecked():
        params.SetBool("OfferToAttachExports", False)

    if answer != QtWidgets.QMessageBox.Yes:
        return None

    group = None
    for candidate in doc.Objects:
        proxy = getattr(candidate, "Proxy", None)
        if proxy is not None and getattr(proxy, "Type", "") == DocObjects.DocumentationGroup.Type:
            group = candidate
            break
    if group is None:
        group = DocObjects.make_group()

    doc.openTransaction("Attach exported document")
    try:
        obj = DocObjects.make_document(path, embed=True, parent=group)
        obj.Description = translate("Documentation", "Exported from this model")
    finally:
        doc.commitTransaction()
    doc.recompute()
    return obj
