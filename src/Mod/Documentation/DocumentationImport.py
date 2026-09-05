# SPDX-License-Identifier: LGPL-2.1-or-later
"""File > Import handler for attachable documents.

Attaches the file to the document as a Documentation object.  FreeCAD calls
insert() for an import and open() for a plain open; both embed the payload
so the model stays self-contained, matching the toolbar command.
"""

import FreeCAD


def _prepare(docname):
    if docname:
        try:
            FreeCAD.setActiveDocument(docname)
        except NameError:
            FreeCAD.newDocument(docname)
            FreeCAD.setActiveDocument(docname)
    elif FreeCAD.ActiveDocument is None:
        FreeCAD.newDocument()
    return FreeCAD.ActiveDocument


def insert(filename, docname=None):
    """Attach *filename* to the document named *docname* and show it.

    Importing a document is a request to look at it, so the viewer opens
    straight away rather than leaving the user to find the new tree item
    and double-click it.
    """
    import DocumentationObjects

    doc = _prepare(docname)
    obj = DocumentationObjects.make_document(filename, embed=True)
    doc.recompute()

    if FreeCAD.GuiUp:
        try:
            from DocumentationViewers import open_document

            open_document(obj)
        except Exception as exc:  # viewing must not undo a good import
            FreeCAD.Console.PrintWarning(
                "Documentation: attached '%s' but could not open it: %s\n"
                % (obj.Label, exc)
            )

    return obj


def open(filename):
    """Open *filename* in a new document."""
    doc = FreeCAD.newDocument()
    insert(filename, doc.Name)
    return doc
