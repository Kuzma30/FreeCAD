# ***************************************************************************
# *   Copyright (c) 2009, 2010 Yorik van Havre <yorik@uncreated.net>        *
# *   Copyright (c) 2009, 2010 Ken Cline <cline@frii.com>                   *
# *   Copyright (c) 2020 FreeCAD Developers                                 *
# *   Copyright (c) 2025 FreeCAD Project Association                        *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************
"""Provides the viewprovider code for the Clone object."""
## @package view_clone
# \ingroup draftviewproviders
# \brief Provides the viewprovider code for the Clone object.

## \addtogroup draftviewproviders
# @{
from PySide import QtCore
from PySide import QtGui

import FreeCADGui as Gui
from drafttaskpanels import task_scale
from draftutils.translate import translate

class ViewProviderClone:
    """a view provider that displays a Clone icon instead of a Draft icon"""

    def __init__(self,vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object
        return

    def getIcon(self):
        return ":/icons/Draft_Clone.svg"

    def setEdit(self, vobj, mode):
        if mode != 0:
            return None

        self.task = task_scale.ScaleTaskPanelEdit(self.Object)
        Gui.Control.showDialog(self.task)
        return True

    def unsetEdit(self, vobj, mode):
        if mode != 0:
            return None

        self.task.finish()
        return True

    def setupContextMenu(self, vobj, menu):
        action_edit = QtGui.QAction(translate("draft", "Edit"), menu)
        QtCore.QObject.connect(action_edit,
                               QtCore.SIGNAL("triggered()"),
                               self.edit)
        menu.addAction(action_edit)

    def edit(self):
        Gui.ActiveDocument.setEdit(self.Object, 0)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def getDisplayModes(self, vobj):
        return []

    def setDisplayMode(self, mode):
        return mode


# Alias for compatibility with v0.18 and earlier
_ViewProviderClone = ViewProviderClone

## @}
