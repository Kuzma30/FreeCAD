# SPDX-License-Identifier: LGPL-2.1-or-later

IF (BUILD_GUI)
    PYSIDE_WRAP_RC(
        RELATIVE Documentation_QRC_SRCS_REL
        ABSOLUTE Documentation_QRC_SRCS
        RESOURCES Resources/Documentation.qrc
    )
ENDIF (BUILD_GUI)

SET(Documentation_SRCS
    Init.py
    InitGui.py
    DocumentationObjects.py
    DocumentationCommands.py
    DocumentationViewers.py
    DocumentationImport.py
    DocumentationRaster.py
    DocumentationRasterImport.py
    ViewProviders.py
)
SOURCE_GROUP("" FILES ${Documentation_SRCS})

SET(Documentation_Tests
    Tests/__init__.py
    Tests/TestDocumentation.py
)
SOURCE_GROUP("Tests" FILES ${Documentation_Tests})

SET(Documentation_Icons
    Resources/icons/DocumentationWorkbench.svg
    Resources/icons/Documentation_AddDocument.svg
    Resources/icons/Documentation_AddNote.svg
    Resources/icons/Documentation_EditNote.svg
    Resources/icons/Documentation_Export.svg
    Resources/icons/Documentation_File.svg
    Resources/icons/Documentation_Group.svg
    Resources/icons/Documentation_Open.svg
    Resources/icons/Documentation_Pdf.svg
    Resources/icons/Documentation_Replace.svg
    Resources/icons/Documentation_Text.svg
)

ADD_CUSTOM_TARGET(Documentation ALL
    DEPENDS ${Documentation_QRC_SRCS}
    SOURCES ${Documentation_SRCS} ${Documentation_Tests} ${Documentation_Icons}
)

fc_copy_sources(Documentation
    "${CMAKE_BINARY_DIR}/Mod/Documentation"
    ${Documentation_SRCS}
    ${Documentation_Tests}
)

# InitGui resolves the workbench icon through FreeCAD.getResourceDir(), which
# points at the data directory rather than Mod/, so the icons have to land
# there as well - the same split Draft uses.
fc_copy_sources(Documentation
    "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/Documentation"
    ${Documentation_Icons}
)

IF (BUILD_GUI)
    fc_target_copy_resource(Documentation
        "${CMAKE_CURRENT_BINARY_DIR}"
        "${CMAKE_BINARY_DIR}/Mod/Documentation"
        ${Documentation_QRC_SRCS_REL})
ENDIF (BUILD_GUI)

INSTALL(
    FILES ${Documentation_SRCS} ${Documentation_QRC_SRCS}
    DESTINATION Mod/Documentation
)

INSTALL(
    FILES ${Documentation_Tests}
    DESTINATION Mod/Documentation/Tests
)

INSTALL(
    FILES ${Documentation_Icons}
    DESTINATION "${CMAKE_INSTALL_DATADIR}/Mod/Documentation/Resources/icons"
)
