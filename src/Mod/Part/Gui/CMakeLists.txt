include_directories(
    ${CMAKE_BINARY_DIR}
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_BINARY_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}
)

set(PartGui_LIBS
    Part
    FreeCADGui
    MatGui
)

if(BUILD_TRACY_FRAME_PROFILER)
    list(APPEND PartGui_LIBS TracyClient)
endif()

if(MSVC)
    include_directories(
        ${CMAKE_SOURCE_DIR}/src/3rdParty/OpenGL/api
    )
endif(MSVC)

include_directories(
    SYSTEM
    ${QtConcurrent_INCLUDE_DIRS}
)
list(APPEND PartGui_LIBS
    ${QtConcurrent_LIBRARIES}
)

generate_from_py(ViewProviderPartExt)

set (Part_TR_QRC ${CMAKE_CURRENT_BINARY_DIR}/Resources/Part_translation.qrc)
qt_find_and_add_translation(QM_SRCS "Resources/translations/*_*.ts"
    ${CMAKE_CURRENT_BINARY_DIR}/Resources/translations)
qt_create_resource_file(${Part_TR_QRC} ${QM_SRCS})
qt_add_resources(PartGui_QRC_SRCS Resources/Part.qrc ${Part_TR_QRC})

set(PartGui_UIC_SRCS
    CrossSections.ui
    Mirroring.ui
    DlgBooleanOperation.ui
    DlgExportStep.ui
    DlgExportHeaderStep.ui
    DlgExtrusion.ui
    DlgScale.ui
    DlgImportStep.ui
    DlgFilletEdges.ui
    DlgImportExportIges.ui
    DlgPartBox.ui
    DlgPartCylinder.ui
    DlgPartImportIges.ui
    DlgPartImportStep.ui
    DlgPrimitives.ui
    Location.ui
    DlgRevolution.ui
    DlgSettings3DViewPart.ui
    DlgSettingsGeneral.ui
    DlgSettingsObjectColor.ui
    DlgProjectionOnSurface.ui
    SectionCutting.ui
    ShapeFromMesh.ui
    TaskFaceAppearances.ui
    TaskShapeBuilder.ui
    TaskLoft.ui
    TaskOffset.ui
    TaskSweep.ui
    TaskAttacher.ui
)

SET(Python_SRCS
    ViewProviderPartExt.pyi
    ViewProviderPartExtPyImp.cpp
)
SOURCE_GROUP("Python" FILES ${Python_SRCS})

SET(PartGui_SRCS
    ${PartGui_QRC_SRCS}
    ${PartGui_UIC_HDRS}
    ${Python_SRCS}
    AppPartGui.cpp
    AttacherTexts.h
    AttacherTexts.cpp
    BoxSelection.cpp
    BoxSelection.h
    Command.cpp
    CommandFilter.cpp
    CommandSimple.cpp
    CommandParametric.cpp
    CrossSections.cpp
    CrossSections.h
    CrossSections.ui
    Mirroring.cpp
    Mirroring.h
    Mirroring.ui
    DlgBooleanOperation.cpp
    DlgBooleanOperation.h
    DlgBooleanOperation.ui
    DlgExportStep.cpp
    DlgExportStep.h
    DlgExportStep.ui
    DlgExportHeaderStep.ui
    DlgExtrusion.cpp
    DlgExtrusion.h
    DlgExtrusion.ui
    DlgScale.cpp
    DlgScale.h
    DlgScale.ui
    DlgFilletEdges.cpp
    DlgFilletEdges.h
    DlgFilletEdges.ui
    DlgImportStep.cpp
    DlgImportStep.h
    DlgImportStep.ui
    DlgImportExportIges.ui
    DlgPartBox.ui
    DlgPartBoxImp.cpp
    DlgPartBoxImp.h
    DlgPartCylinderImp.cpp
    DlgPartCylinderImp.h
    DlgPartCylinder.ui
    DlgPartImportIges.ui
    DlgPartImportIgesImp.cpp
    DlgPartImportIgesImp.h
    DlgPartImportStep.ui
    DlgPartImportStepImp.cpp
    DlgPartImportStepImp.h
    DlgPrimitives.cpp
    DlgPrimitives.h
    DlgPrimitives.ui
    Location.ui
    DlgRevolution.cpp
    DlgRevolution.h
    DlgRevolution.ui
    DlgSettings3DViewPart.ui
    DlgSettings3DViewPartImp.cpp
    DlgSettings3DViewPartImp.h
    DlgSettingsGeneral.cpp
    DlgSettingsGeneral.h
    DlgSettingsGeneral.ui
    DlgSettingsObjectColor.cpp
    DlgSettingsObjectColor.h
    DlgSettingsObjectColor.ui
    DlgProjectionOnSurface.cpp
    DlgProjectionOnSurface.h
    DlgProjectionOnSurface.ui
    Resources/Part.qrc
    PreCompiled.cpp
    PreCompiled.h
    PropertyEnumAttacherItem.cpp
    PropertyEnumAttacherItem.h
    SoFCShapeObject.cpp
    SoFCShapeObject.h
    SoBrepEdgeSet.cpp
    SoBrepEdgeSet.h
    SoBrepFaceSet.cpp
    SoBrepFaceSet.h
    SoBrepPointSet.cpp
    SoBrepPointSet.h
    ViewProvider.cpp
    ViewProvider.h
    ViewProviderAttachExtension.h
    ViewProviderAttachExtension.cpp
    ViewProviderDatum.cpp
    ViewProviderDatum.h
    ViewProviderExt.cpp
    ViewProviderExt.h
    ViewProviderReference.cpp
    ViewProviderReference.h
    ViewProviderBox.cpp
    ViewProviderBox.h
    ViewProviderCompound.cpp
    ViewProviderCompound.h
    ViewProviderCircleParametric.cpp
    ViewProviderCircleParametric.h
    ViewProviderLineParametric.cpp
    ViewProviderLineParametric.h
    ViewProviderPointParametric.cpp
    ViewProviderPointParametric.h
    ViewProviderEllipseParametric.cpp
    ViewProviderEllipseParametric.h
    ViewProviderGridExtension.cpp
    ViewProviderGridExtension.h
    ViewProviderHelixParametric.cpp
    ViewProviderHelixParametric.h
    ViewProviderPlaneParametric.cpp
    ViewProviderPlaneParametric.h
    ViewProviderSphereParametric.cpp
    ViewProviderSphereParametric.h
    ViewProviderCylinderParametric.cpp
    ViewProviderCylinderParametric.h
    ViewProviderConeParametric.cpp
    ViewProviderConeParametric.h
    ViewProviderPrism.cpp
    ViewProviderPrism.h
    ViewProviderRegularPolygon.cpp
    ViewProviderRegularPolygon.h
    ViewProviderTorusParametric.cpp
    ViewProviderTorusParametric.h
    ViewProviderCurveNet.cpp
    ViewProviderCurveNet.h
    ViewProviderSpline.cpp
    ViewProviderSpline.h
    ViewProviderImport.cpp
    ViewProviderImport.h
    ViewProviderExtrusion.cpp
    ViewProviderExtrusion.h
    ViewProviderScale.cpp
    ViewProviderScale.h
    ViewProvider2DObject.cpp
    ViewProvider2DObject.h
    ViewProviderMirror.cpp
    ViewProviderMirror.h
    ViewProviderPython.cpp
    ViewProviderPython.h
    ViewProviderBoolean.cpp
    ViewProviderBoolean.h
    ViewProviderProjectOnSurface.cpp
    ViewProviderProjectOnSurface.h
    ViewProviderRuledSurface.cpp
    ViewProviderRuledSurface.h
    ViewProviderPrimitive.cpp
    ViewProviderPrimitive.h
    Workbench.cpp
    Workbench.h
    WorkbenchManipulator.cpp
    WorkbenchManipulator.h
    ReferenceHighlighter.cpp
    ReferenceHighlighter.h
    SectionCutting.cpp
    SectionCutting.h
    SectionCutting.ui
    ShapeFromMesh.cpp
    ShapeFromMesh.h
    TaskFaceAppearances.cpp
    TaskFaceAppearances.h
    TaskFaceAppearances.ui
    TaskShapeBuilder.cpp
    TaskShapeBuilder.h
    TaskShapeBuilder.ui
    TaskLoft.cpp
    TaskLoft.h
    TaskLoft.ui
    TaskOffset.cpp
    TaskOffset.h
    TaskOffset.ui
    TaskSweep.cpp
    TaskSweep.h
    TaskSweep.ui
    TaskThickness.cpp
    TaskThickness.h
    TaskCheckGeometry.cpp
    TaskCheckGeometry.h
    TaskAttacher.h
    TaskAttacher.cpp
)

if(FREECAD_USE_PCH)
    add_definitions(-D_PreComp_)
    GET_MSVC_PRECOMPILED_SOURCE("PreCompiled.cpp" PCH_SRCS ${PartGui_SRCS})
    ADD_MSVC_PRECOMPILED_HEADER(PartGui PreCompiled.h PreCompiled.cpp PCH_SRCS)
endif(FREECAD_USE_PCH)

SET(PartGuiIcon_SVG
    Resources/icons/PartWorkbench.svg
)

add_library(PartGui SHARED ${PartGui_SRCS} ${PartGuiIcon_SVG})
target_link_libraries(PartGui ${PartGui_LIBS})
if (FREECAD_WARN_ERROR)
    target_compile_warn_error(PartGui)
endif()


SET_BIN_DIR(PartGui PartGui /Mod/Part)
SET_PYTHON_PREFIX_SUFFIX(PartGui)

fc_copy_sources(PartGui "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Mod/Part" ${PartGuiIcon_SVG})

INSTALL(TARGETS PartGui DESTINATION ${CMAKE_INSTALL_LIBDIR})
INSTALL(FILES ${PartGuiIcon_SVG} DESTINATION "${CMAKE_INSTALL_DATADIR}/Mod/Part/Resources/icons")
