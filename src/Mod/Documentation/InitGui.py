# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI initialisation for the Documentation workbench."""

import os

import FreeCAD
import FreeCADGui


class DocumentationWorkbench(FreeCADGui.Workbench):
    """Attach datasheets, drawings and notes to a model."""

    def __init__(self):
        def QT_TRANSLATE_NOOP(context, text):
            return text

        __dirname__ = os.path.join(FreeCAD.getResourceDir(), "Mod", "Documentation")

        self.__class__.Icon = os.path.join(
            __dirname__, "Resources", "icons", "DocumentationWorkbench.svg"
        )
        self.__class__.MenuText = QT_TRANSLATE_NOOP("Documentation", "Documentation")
        self.__class__.ToolTip = QT_TRANSLATE_NOOP(
            "Documentation",
            "Attach datasheets, drawings and notes to the model and open them "
            "inside FreeCAD",
        )

    _tools = [
        "Documentation_AddDocument",
        "Documentation_AddNote",
        "Documentation_AddGroup",
        "Separator",
        "Documentation_Open",
        "Documentation_EditNote",
        "Documentation_Export",
        "Documentation_Replace",
    ]

    def Initialize(self):
        def QT_TRANSLATE_NOOP(context, text):
            return text

        import DocumentationCommands

        DocumentationCommands.register()
        self.appendToolbar(QT_TRANSLATE_NOOP("Documentation", "Documentation"), self._tools)
        self.appendMenu(QT_TRANSLATE_NOOP("Documentation", "Documentation"), self._tools)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(DocumentationWorkbench())
