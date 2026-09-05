# SPDX-License-Identifier: LGPL-2.1-or-later
"""Console-mode initialisation for the Documentation workbench.

Two ways to bring a PDF in, offered side by side in File > Import:
attaching it as a document, or rasterising pages onto image planes.
"""

FreeCAD.addImportType(
    "Attachable document (*.pdf *.rtf *.doc *.docx *.odt *.md *.html *.htm)",
    "DocumentationImport",
)

FreeCAD.addImportType(
    "PDF page as image plane (*.pdf)",
    "DocumentationRasterImport",
)
