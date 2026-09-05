# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scripted objects for the Documentation workbench.

Two object types are provided:

``DocumentationGroup``
    A plain container that groups attached documents in the tree.

``AttachedDocument``
    A single document.  It can either embed the file inside the .FCStd
    (via ``App::PropertyFileIncluded``, which stores the payload in the
    document's zip container) or keep a path to an external file.
"""

import os

import FreeCAD

translate = FreeCAD.Qt.translate
QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP


# Extensions we can display inside FreeCAD, mapped to a viewer kind.
VIEWER_PDF = "pdf"
VIEWER_RICHTEXT = "richtext"
VIEWER_PLAINTEXT = "plaintext"
VIEWER_EXTERNAL = "external"

VIEWER_BY_SUFFIX = {
    "pdf": VIEWER_PDF,
    "rtf": VIEWER_RICHTEXT,
    "html": VIEWER_RICHTEXT,
    "htm": VIEWER_RICHTEXT,
    "md": VIEWER_PLAINTEXT,
    "txt": VIEWER_PLAINTEXT,
    "csv": VIEWER_PLAINTEXT,
    "log": VIEWER_PLAINTEXT,
}


def viewer_for(filename):
    """Return the viewer kind able to display *filename*."""
    suffix = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return VIEWER_BY_SUFFIX.get(suffix, VIEWER_EXTERNAL)


def human_size(num_bytes):
    """Format a byte count the way a file manager would."""
    if num_bytes is None:
        return ""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return ""


class DocumentationGroup:
    """Container object; behaves like a folder in the tree."""

    Type = "Documentation::Group"

    def __init__(self, obj):
        obj.Proxy = self
        self.Type = self.Type
        obj.addExtension("App::GroupExtensionPython")

    def dumps(self):
        return self.Type

    def loads(self, state):
        self.Type = state if isinstance(state, str) else self.Type
        return None

    def execute(self, obj):
        pass

    # Older FreeCAD releases call these instead of dumps/loads.
    __getstate__ = dumps
    __setstate__ = loads


class AttachedDocument:
    """A single attached document, embedded or linked."""

    Type = "Documentation::AttachedDocument"

    def __init__(self, obj):
        obj.Proxy = self
        self.Type = self.Type
        self.setProperties(obj)

    def setProperties(self, obj):
        """Add any property that is not present yet.

        Called both on creation and on restore, so that documents saved
        by an older version of the workbench gain new properties.
        """
        props = obj.PropertiesList

        if "Embedded" not in props:
            obj.addProperty(
                "App::PropertyBool",
                "Embedded",
                "Storage",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Store the file inside the FCStd container.\n"
                    "When disabled only the path in ExternalFile is kept.",
                ),
            )
            obj.Embedded = True

        if "EmbeddedFile" not in props:
            obj.addProperty(
                "App::PropertyFileIncluded",
                "EmbeddedFile",
                "Storage",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Payload stored inside the FCStd container"
                ),
            )

        if "ExternalFile" not in props:
            obj.addProperty(
                "App::PropertyFile",
                "ExternalFile",
                "Storage",
                QT_TRANSLATE_NOOP("App::Property", "Path to the file on disk"),
            )

        if "FileName" not in props:
            obj.addProperty(
                "App::PropertyString",
                "FileName",
                "Document",
                QT_TRANSLATE_NOOP("App::Property", "Original file name"),
            )
            obj.setEditorMode("FileName", 1)  # read-only

        if "FileSize" not in props:
            obj.addProperty(
                "App::PropertyString",
                "FileSize",
                "Document",
                QT_TRANSLATE_NOOP("App::Property", "Size of the document"),
            )
            obj.setEditorMode("FileSize", 1)

        if "Description" not in props:
            obj.addProperty(
                "App::PropertyString",
                "Description",
                "Document",
                QT_TRANSLATE_NOOP("App::Property", "What this document contains"),
            )

        if "Author" not in props:
            obj.addProperty(
                "App::PropertyString",
                "Author",
                "Revision",
                QT_TRANSLATE_NOOP("App::Property", "Who produced the document"),
            )

        if "Revision" not in props:
            obj.addProperty(
                "App::PropertyString",
                "Revision",
                "Revision",
                QT_TRANSLATE_NOOP("App::Property", "Revision identifier, e.g. Rev. B"),
            )

        if "Date" not in props:
            obj.addProperty(
                "App::PropertyString",
                "Date",
                "Revision",
                QT_TRANSLATE_NOOP("App::Property", "Date of this revision"),
            )

        if "Status" not in props:
            obj.addProperty(
                "App::PropertyEnumeration",
                "Status",
                "Revision",
                QT_TRANSLATE_NOOP("App::Property", "Approval state"),
            )
            obj.Status = ["Draft", "In review", "Approved", "Obsolete"]
            obj.Status = "Draft"

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def dumps(self):
        return self.Type

    def loads(self, state):
        self.Type = state if isinstance(state, str) else self.Type
        return None

    __getstate__ = dumps
    __setstate__ = loads

    def execute(self, obj):
        pass

    def onChanged(self, obj, prop):
        # Keep the read-only metadata in step with whichever source is active.
        # During object creation properties are added one by one, so the
        # others may not exist yet — bail out if the set is incomplete.
        if prop in ("EmbeddedFile", "ExternalFile", "Embedded"):
            if "EmbeddedFile" in obj.PropertiesList and "FileName" in obj.PropertiesList:
                self.refreshMetadata(obj)

    def refreshMetadata(self, obj):
        path = self.resolvePath(obj)
        if not path:
            return
        try:
            basename = os.path.basename(path)
            if obj.FileName != basename:
                obj.FileName = basename
            size = human_size(os.path.getsize(path))
            if obj.FileSize != size:
                obj.FileSize = size
        except (OSError, AttributeError):
            pass

    def resolvePath(self, obj):
        """Return a readable path for the payload, or an empty string."""
        if getattr(obj, "Embedded", True):
            return getattr(obj, "EmbeddedFile", "") or ""
        external = getattr(obj, "ExternalFile", "") or ""
        if external and not os.path.isabs(external):
            # Relative paths resolve against the FCStd location.
            base = os.path.dirname(obj.Document.FileName or "")
            if base:
                external = os.path.join(base, external)
        return external


def _add_child(parent, child):
    """Add *child* under the best container near *parent*.

    Placement, in order of preference:
    1. a Documentation group or an App::Part -> addObject directly
    2. a PartDesign::Body -> its enclosing App::Part, because Body::isAllowed
       in C++ rejects anything that is not a PartDesign feature
    3. anything else exposing addObject -> try it
    4. nothing suitable -> the object stays at document root
    """
    if parent is None:
        return

    parent_type = getattr(parent, "TypeId", "")
    proxy_type = getattr(getattr(parent, "Proxy", None), "Type", "")

    if proxy_type == DocumentationGroup.Type or parent_type == "App::Part":
        if _try_add(parent, child):
            return

    elif parent_type == "PartDesign::Body":
        for candidate in parent.InList:
            if getattr(candidate, "TypeId", "") == "App::Part" and _try_add(candidate, child):
                return
        FreeCAD.Console.PrintLog(
            "Documentation: '%s' cannot hold documentation objects and is not "
            "inside an App::Part, so '%s' was left at document root.\n"
            % (parent.Label, child.Label)
        )
        return

    elif _try_add(parent, child):
        return

    FreeCAD.Console.PrintWarning(
        "Documentation: could not place '%s' under '%s'; it stays at document root.\n"
        % (child.Label, parent.Label)
    )


def _try_add(parent, child):
    """addObject() that reports why it failed instead of staying silent."""
    if not hasattr(parent, "addObject"):
        return False
    try:
        parent.addObject(child)
        return True
    except Exception as exc:  # the container decides what it accepts
        FreeCAD.Console.PrintLog(
            "Documentation: '%s' refused '%s': %s\n" % (parent.Label, child.Label, exc)
        )
        return False


def make_group(label=None, parent=None):
    """Create a documentation container in the active document."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument()
    obj = doc.addObject("App::FeaturePython", "Documentation")
    DocumentationGroup(obj)
    obj.Label = label or translate("Documentation", "Documentation")
    if FreeCAD.GuiUp:
        from ViewProviders import ViewProviderDocumentationGroup, hideDisplayProperties

        ViewProviderDocumentationGroup(obj.ViewObject)
        hideDisplayProperties(obj.ViewObject)
    _add_child(parent, obj)
    return obj


def make_document(path, embed=True, parent=None, label=None):
    """Attach *path* to the active document.

    With *embed* the payload is copied into the FCStd container, so the
    file travels with the model.  Otherwise only the path is stored.
    """
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument()

    obj = doc.addObject("App::FeaturePython", "Document")
    AttachedDocument(obj)

    obj.Embedded = bool(embed)
    if embed:
        obj.EmbeddedFile = path
    else:
        obj.ExternalFile = path

    obj.Label = label or os.path.basename(path)
    obj.Proxy.refreshMetadata(obj)

    if FreeCAD.GuiUp:
        from ViewProviders import ViewProviderAttachedDocument, hideDisplayProperties

        ViewProviderAttachedDocument(obj.ViewObject)
        hideDisplayProperties(obj.ViewObject)
    _add_child(parent, obj)
    return obj
