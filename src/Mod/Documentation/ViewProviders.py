# SPDX-License-Identifier: LGPL-2.1-or-later
"""View providers for the Documentation workbench."""

import os

import FreeCAD

translate = FreeCAD.Qt.translate

from DocumentationObjects import (
    VIEWER_EXTERNAL,
    VIEWER_PDF,
    VIEWER_PLAINTEXT,
    VIEWER_RICHTEXT,
    viewer_for,
)



def _find_icon_dir():
    """Locate the icons directory.

    They are installed under the resource directory rather than next to this
    file, because InitGui resolves the workbench icon through
    getResourceDir() and both should read from the same place.
    """
    return os.path.join(
        FreeCAD.getResourceDir(), "Mod", "Documentation", "Resources", "icons"
    )


ICON_DIR = _find_icon_dir()

ICON_BY_VIEWER = {
    VIEWER_PDF: "Documentation_Pdf.svg",
    VIEWER_RICHTEXT: "Documentation_Text.svg",
    VIEWER_PLAINTEXT: "Documentation_Text.svg",
    VIEWER_EXTERNAL: "Documentation_File.svg",
}


def icon_path(name):
    return os.path.join(ICON_DIR, name)


# These only mean something for an object drawn in the 3D view. An attachment
# opens in its own window, so hide the controls instead of showing ones that
# do nothing.
_UNUSED_DISPLAY_PROPERTIES = (
    "Visibility",
    "DisplayMode",
    "ShowInTree",
    "OnTopWhenSelected",
    "SelectionStyle",
)


def hideDisplayProperties(vobj):
    """Strip the 3D display controls from an object that is never rendered.

    Removes the eye toggle from the tree, hides the properties behind it and
    forces Visibility on, since that flag is what greys out a tree label.
    """
    # Same mechanism VarSet and Spreadsheet use: these objects are not drawn,
    # so the tree should not offer a visibility toggle for them.
    try:
        vobj.ToggleVisibility = "NoToggleVisibility"
    except (AttributeError, ValueError):
        pass  # older FreeCAD without the property

    for name in _UNUSED_DISPLAY_PROPERTIES:
        if name in vobj.PropertiesList:
            try:
                vobj.setEditorMode(name, 2)  # hidden
            except Exception:
                pass

    # Visibility drives the greyed-out look in the tree, so force it on.
    if "Visibility" in vobj.PropertiesList and not vobj.Visibility:
        vobj.Visibility = True


class _BaseViewProvider:
    """Shared plumbing so both view providers survive save/restore."""

    def attach(self, vobj):
        self.ViewObject = vobj
        self.Object = vobj.Object
        hideDisplayProperties(vobj)

    def onDocumentRestored(self, vobj):
        hideDisplayProperties(vobj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class ViewProviderDocumentationGroup(_BaseViewProvider):
    def __init__(self, vobj):
        vobj.Proxy = self
        vobj.addExtension("Gui::ViewProviderGroupExtensionPython")
        hideDisplayProperties(vobj)

    def isShow(self):
        return True

    def getIcon(self):
        return icon_path("Documentation_Group.svg")


class ViewProviderAttachedDocument(_BaseViewProvider):
    def __init__(self, vobj):
        vobj.Proxy = self
        hideDisplayProperties(vobj)

    def isShow(self):
        # These objects have nothing to draw, but the tree greys out anything
        # reporting itself as hidden, which made every attachment look
        # disabled.  Claim visibility so the label renders normally.
        return True

    def canDragObjects(self):
        return False

    def canDropObjects(self):
        return False

    def getIcon(self):
        obj = getattr(self, "Object", None)
        name = obj.FileName if obj is not None else ""
        return icon_path(ICON_BY_VIEWER[viewer_for(name)])

    def doubleClicked(self, vobj):
        from DocumentationViewers import open_document

        open_document(vobj.Object)
        return True

    def setupContextMenu(self, vobj, menu):
        from PySide import QtGui

        obj = vobj.Object

        action = menu.addAction(translate("Documentation", "Open"))
        action.triggered.connect(lambda: self.doubleClicked(vobj))

        # Show Edit only for text-based documents
        from DocumentationObjects import viewer_for, VIEWER_RICHTEXT, VIEWER_PLAINTEXT
        kind = viewer_for(getattr(obj, "FileName", ""))
        if kind in (VIEWER_RICHTEXT, VIEWER_PLAINTEXT):
            action = menu.addAction(translate("Documentation", "Edit"))
            action.triggered.connect(lambda: self._edit(obj))

        action = menu.addAction(translate("Documentation", "Save a copy..."))
        action.triggered.connect(lambda: self._export(obj))

        action = menu.addAction(translate("Documentation", "Replace file..."))
        action.triggered.connect(lambda: self._replace(obj))

        return True

    def _export(self, obj):
        from DocumentationCommands import export_document

        export_document(obj)

    def _replace(self, obj):
        from DocumentationCommands import replace_document

        replace_document(obj)

    def _edit(self, obj):
        from DocumentationCommands import edit_note
        edit_note(obj)

    def claimChildren(self):
        return []
