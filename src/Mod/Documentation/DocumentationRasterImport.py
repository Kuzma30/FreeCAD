# SPDX-License-Identifier: LGPL-2.1-or-later
"""File > Import handler that rasterises PDF pages onto ImagePlanes.

The counterpart to DocumentationImport: rather than attaching the document,
the chosen pages are rendered and placed in the 3D view as underlays.
"""

import FreeCAD


def insert(filename, docname=None):
    """Rasterise *filename* into the document named *docname*."""
    import DocumentationRaster

    if docname:
        try:
            FreeCAD.setActiveDocument(docname)
        except NameError:
            FreeCAD.newDocument(docname)
            FreeCAD.setActiveDocument(docname)
    elif FreeCAD.ActiveDocument is None:
        FreeCAD.newDocument()

    return DocumentationRaster.rasterToImagePlanes(filename, FreeCAD.ActiveDocument)


def open(filename):
    """Rasterise *filename* into a new document."""
    doc = FreeCAD.newDocument()
    insert(filename, doc.Name)
    return doc
