# Complete Existing PDF Workflow Map

This map is generated from the original source tree, Next.js route files, imports, frontend API strings, FastAPI decorators, worker registrations, and database schema definitions.

## 1. Entry and source selection

- **Route:** `/boq-generation`
  - Page: `frontend/app/boq-generation/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/components/SignOutButton.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq-generation/components/BoqGenerationPage.tsx`, `frontend/features/platform/components/PlatformShell.tsx`, `frontend/features/platform/services/platformService.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/platform/account/profile`, `/api/v1/platform/account/settings`, `/api/v1/platform/admin/organizations`, `/api/v1/platform/admin/overview`, `/api/v1/platform/admin/subscription-plans`, `/api/v1/platform/admin/super-admins`, `/api/v1/platform/audit-logs`, `/api/v1/platform/billing-history`, `/api/v1/platform/exported-files`, `/api/v1/platform/me`, `/api/v1/platform/notifications`, `/api/v1/platform/organization/invitations`, `/api/v1/platform/organization/members`, `/api/v1/platform/organization/overview`, `/api/v1/platform/organization/roles`, `/api/v1/platform/password-reset/request`
- **Route:** `/boq-generation/import`
  - Page: `frontend/app/boq-generation/import/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/components/SignOutButton.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq-generation/components/ExternalImportPage.tsx`, `frontend/features/boq-generation/components/ExternalJsonImportPage.tsx`, `frontend/features/boq-generation/components/FieldMappingPanel.tsx`, `frontend/features/boq-generation/components/ImportPreviewTable.tsx`, `frontend/features/boq-generation/components/SourceImportPage.tsx`, `frontend/features/boq-generation/components/ValidationIssuesPanel.tsx`, `frontend/features/boq-generation/components/sourceImportUtils.ts`, `frontend/features/boq-generation/services/importBoqApi.ts`, `frontend/features/boq-generation/types/boqGenerationTypes.ts`, `frontend/features/canonical-takeoff/types/canonicalTakeoffTypes.ts`, `frontend/features/projects/services/projectService.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/projects`
- **Route:** `/boq-generation/costx`
  - Page: `frontend/app/boq-generation/costx/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/components/SignOutButton.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq-generation/components/CostXImportPage.tsx`, `frontend/features/boq-generation/components/FieldMappingPanel.tsx`, `frontend/features/boq-generation/components/ImportPreviewTable.tsx`, `frontend/features/boq-generation/components/ValidationIssuesPanel.tsx`, `frontend/features/boq-generation/components/sourceImportUtils.ts`, `frontend/features/boq-generation/services/importBoqApi.ts`, `frontend/features/boq-generation/types/boqGenerationTypes.ts`, `frontend/features/canonical-takeoff/types/canonicalTakeoffTypes.ts`, `frontend/features/projects/services/projectService.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/projects`
- **Route:** `/boq-generation/revit`
  - Page: `frontend/app/boq-generation/revit/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/components/SignOutButton.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq-generation/components/FieldMappingPanel.tsx`, `frontend/features/boq-generation/components/ImportPreviewTable.tsx`, `frontend/features/boq-generation/components/RevitImportPage.tsx`, `frontend/features/boq-generation/components/ValidationIssuesPanel.tsx`, `frontend/features/boq-generation/components/sourceImportUtils.ts`, `frontend/features/boq-generation/services/importBoqApi.ts`, `frontend/features/boq-generation/types/boqGenerationTypes.ts`, `frontend/features/canonical-takeoff/types/canonicalTakeoffTypes.ts`, `frontend/features/projects/services/projectService.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/projects`
- **Route:** `/boq-generation/acc`
  - Page: `frontend/app/boq-generation/acc/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/components/SignOutButton.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq-generation/components/AccImportPage.tsx`, `frontend/features/boq-generation/components/AccTakeoffPage.tsx`, `frontend/features/boq-generation/components/FieldMappingPanel.tsx`, `frontend/features/boq-generation/components/ImportPreviewTable.tsx`, `frontend/features/boq-generation/components/ValidationIssuesPanel.tsx`, `frontend/features/boq-generation/components/sourceImportUtils.ts`, `frontend/features/boq-generation/services/importBoqApi.ts`, `frontend/features/boq-generation/types/boqGenerationTypes.ts`, `frontend/features/canonical-takeoff/types/canonicalTakeoffTypes.ts`, `frontend/features/projects/services/projectService.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/projects`
- **Route:** `/boq-generation/saved`
  - Page: `frontend/app/boq-generation/saved/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/components/SignOutButton.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq-generation/components/SavedTakeoffsPage.tsx`, `frontend/features/canonical-takeoff/services/canonicalTakeoffService.ts`, `frontend/features/canonical-takeoff/types/canonicalTakeoffTypes.ts`, `frontend/features/projects/services/projectService.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/canonical-takeoffs`, `/api/v1/projects`

## 2. Project creation and PDF upload

- **Route:** `/upload`
  - Page: `frontend/app/upload/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/components/SignOutButton.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/platform/components/PlatformShell.tsx`, `frontend/features/platform/services/platformService.ts`, `frontend/features/upload/components/PdfUploadBox.tsx`, `frontend/features/upload/components/UploadProgress.tsx`, `frontend/features/upload/services/uploadService.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/platform/account/profile`, `/api/v1/platform/account/settings`, `/api/v1/platform/admin/organizations`, `/api/v1/platform/admin/overview`, `/api/v1/platform/admin/subscription-plans`, `/api/v1/platform/admin/super-admins`, `/api/v1/platform/audit-logs`, `/api/v1/platform/billing-history`, `/api/v1/platform/exported-files`, `/api/v1/platform/me`, `/api/v1/platform/notifications`, `/api/v1/platform/organization/invitations`, `/api/v1/platform/organization/members`, `/api/v1/platform/organization/overview`, `/api/v1/platform/organization/roles`, `/api/v1/platform/password-reset/request`

## 3. Drawing setup and crop views

- **Route:** `/workspace/[projectId]`
  - Page: `frontend/app/workspace/[projectId]/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/crop-list/constants/cropTypes.ts`, `frontend/features/crop-preview/services/cropPreviewService.ts`, `frontend/features/page-thumbnails/components/PageThumbnailCard.tsx`, `frontend/features/page-thumbnails/components/PageThumbnailList.tsx`, `frontend/features/page-thumbnails/services/thumbnailService.ts`, `frontend/features/pdf-viewer/components/PdfPageCanvas.tsx`, `frontend/features/pdf-viewer/components/PdfViewer.tsx`, `frontend/features/pdf-viewer/components/ZoomControls.tsx`, `frontend/features/pdf-viewer/hooks/usePdfViewport.ts`, `frontend/features/pdf-viewer/services/pdfViewerService.ts`, `frontend/features/project-state/stores/cropStore.ts`, `frontend/features/project-state/stores/projectStore.ts`, `frontend/features/project-state/stores/selectionStore.ts`, `frontend/features/project-state/stores/viewerStore.ts`, `frontend/features/selection-tools/components/FreehandSelectionTool.tsx`, `frontend/features/selection-tools/components/PolygonSelectionTool.tsx` …
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`
- **Route:** `/workspace/[projectId]/setup`
  - Page: `frontend/app/workspace/[projectId]/setup/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/crop-list/constants/cropTypes.ts`, `frontend/features/drawing-setup/components/DrawingSetupPage.tsx`, `frontend/features/drawing-setup/services/drawingSetupService.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 4. Schedules and specifications

- **Route:** `/workspace/[projectId]/schedules`
  - Page: `frontend/app/workspace/[projectId]/schedules/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/element-details/types/elementDetailsTypes.ts`, `frontend/features/schedules/components/DoorWindowSchedulePage.tsx`, `frontend/features/schedules/services/scheduleApi.ts`, `frontend/features/schedules/types/scheduleTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`
- **Route:** `/workspace/[projectId]/specifications`
  - Page: `frontend/app/workspace/[projectId]/specifications/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/page-thumbnails/components/PageThumbnailCard.tsx`, `frontend/features/page-thumbnails/components/PageThumbnailList.tsx`, `frontend/features/page-thumbnails/services/thumbnailService.ts`, `frontend/features/pdf-viewer/components/PdfPageCanvas.tsx`, `frontend/features/pdf-viewer/components/PdfViewer.tsx`, `frontend/features/pdf-viewer/components/ZoomControls.tsx`, `frontend/features/pdf-viewer/hooks/usePdfViewport.ts`, `frontend/features/pdf-viewer/services/pdfViewerService.ts`, `frontend/features/project-state/stores/selectionStore.ts`, `frontend/features/project-state/stores/viewerStore.ts`, `frontend/features/selection-tools/components/FreehandSelectionTool.tsx`, `frontend/features/selection-tools/components/PolygonSelectionTool.tsx`, `frontend/features/selection-tools/components/RectangleSelectionTool.tsx`, `frontend/features/selection-tools/components/SelectionHandles.tsx`, `frontend/features/selection-tools/components/SelectionOverlay.tsx`, `frontend/features/selection-tools/components/SelectionToolbar.tsx` …
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 5. Scale calibration

- **Route:** `/workspace/[projectId]/scale`
  - Page: `frontend/app/workspace/[projectId]/scale/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/crop-list/constants/cropTypes.ts`, `frontend/features/scale-calibration/components/ScaleCalibrationPage.tsx`, `frontend/features/scale-calibration/services/scaleCalibrationService.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkspaceQuickLinks.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 6. Elevation mapping

- **Route:** `/workspace/[projectId]/mapping`
  - Page: `frontend/app/workspace/[projectId]/mapping/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/drawing-setup/services/drawingSetupService.ts`, `frontend/features/view-mapping/components/DualMappingCanvas.tsx`, `frontend/features/view-mapping/components/ImageMappingCanvas.tsx`, `frontend/features/view-mapping/components/MappingCanvasToolbar.tsx`, `frontend/features/view-mapping/components/MappingSideSelector.tsx`, `frontend/features/view-mapping/components/MappingStatusPanel.tsx`, `frontend/features/view-mapping/components/MappingWorkbench.tsx`, `frontend/features/view-mapping/services/viewMappingService.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 7. Drawing analysis and detection

- **Route:** `/workspace/[projectId]/analysis`
  - Page: `frontend/app/workspace/[projectId]/analysis/page.tsx`
  - Main frontend files: `frontend/features/analysis/components/AnalysisPage.tsx`, `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/detection-review/services/detectionReviewService.ts`, `frontend/features/detection-review/services/modelAnalysisService.ts`, `frontend/features/drawing-setup/services/drawingSetupService.ts`, `frontend/features/model-analysis/components/ModelAnalysisPage.tsx`, `frontend/features/scale-calibration/services/scaleCalibrationService.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 8. Elevation crops and height extraction

- **Route:** `/workspace/[projectId]/elevation-crops`
  - Page: `frontend/app/workspace/[projectId]/elevation-crops/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/element-details/services/elementDetailsService.ts`, `frontend/features/element-details/types/elementDetailsTypes.ts`, `frontend/features/elevation-crops/components/ElevationCropsPage.tsx`, `frontend/features/plan-elements/components/SelectedElementCropPreview.tsx`, `frontend/features/plan-elements/components/WallDeductionSummaryCard.tsx`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 9. Plan element assignment

- **Route:** `/workspace/[projectId]/plan-elements`
  - Page: `frontend/app/workspace/[projectId]/plan-elements/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/element-details/services/elementDetailsService.ts`, `frontend/features/element-details/types/elementDetailsTypes.ts`, `frontend/features/exterior-boundary/components/BoundaryEditorOverlay.tsx`, `frontend/features/exterior-boundary/services/exteriorBoundaryService.ts`, `frontend/features/exterior-boundary/types/exteriorBoundaryTypes.ts`, `frontend/features/plan-elements/components/PlanElementsPage.tsx`, `frontend/features/plan-elements/components/SelectedElementCropPreview.tsx`, `frontend/features/plan-elements/components/WallDeductionSummaryCard.tsx`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`
- **Route:** `/workspace/[projectId]/review`
  - Page: `frontend/app/workspace/[projectId]/review/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/detection-review/services/detectionReviewService.ts`, `frontend/features/drawing-setup/services/drawingSetupService.ts`, `frontend/features/element-details/services/elementDetailsService.ts`, `frontend/features/element-details/types/elementDetailsTypes.ts`, `frontend/features/element-types/components/TypeLibraryModal.tsx`, `frontend/features/element-types/services/elementTypeService.ts`, `frontend/features/exterior-boundary/components/BoundaryEditorOverlay.tsx`, `frontend/features/exterior-boundary/services/exteriorBoundaryService.ts`, `frontend/features/exterior-boundary/types/exteriorBoundaryTypes.ts`, `frontend/features/scale-calibration/services/scaleCalibrationService.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkspaceQuickLinks.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 10. Wall measurement and takeoff

- **Route:** `/workspace/[projectId]/walls`
  - Page: `frontend/app/workspace/[projectId]/walls/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/page-thumbnails/components/PageThumbnailCard.tsx`, `frontend/features/page-thumbnails/components/PageThumbnailList.tsx`, `frontend/features/page-thumbnails/services/thumbnailService.ts`, `frontend/features/pdf-viewer/components/PdfPageCanvas.tsx`, `frontend/features/pdf-viewer/components/PdfViewer.tsx`, `frontend/features/pdf-viewer/components/ZoomControls.tsx`, `frontend/features/pdf-viewer/hooks/usePdfViewport.ts`, `frontend/features/pdf-viewer/services/pdfViewerService.ts`, `frontend/features/project-state/stores/selectionStore.ts`, `frontend/features/project-state/stores/viewerStore.ts`, `frontend/features/selection-tools/components/FreehandSelectionTool.tsx`, `frontend/features/selection-tools/components/PolygonSelectionTool.tsx`, `frontend/features/selection-tools/components/RectangleSelectionTool.tsx`, `frontend/features/selection-tools/components/SelectionHandles.tsx`, `frontend/features/selection-tools/components/SelectionOverlay.tsx`, `frontend/features/selection-tools/components/SelectionToolbar.tsx` …
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 11. Floor area takeoff

- **Route:** `/workspace/[projectId]/floor-areas`
  - Page: `frontend/app/workspace/[projectId]/floor-areas/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/crop/services/cropApi.ts`, `frontend/features/floor-areas/components/FloorAreaDetailsPanel.tsx`, `frontend/features/floor-areas/components/FloorAreaEmptyState.tsx`, `frontend/features/floor-areas/components/FloorAreaPlanPreview.tsx`, `frontend/features/floor-areas/components/FloorAreaSourceCompare.tsx`, `frontend/features/floor-areas/components/FloorAreaTable.tsx`, `frontend/features/floor-areas/components/FloorAreaToolbar.tsx`, `frontend/features/floor-areas/components/FloorAreaValidationMessage.tsx`, `frontend/features/floor-areas/components/FloorAreasPage.tsx`, `frontend/features/floor-areas/components/FloorZoneOverlay.tsx`, `frontend/features/floor-areas/components/ManualFloorPolygonTool.tsx`, `frontend/features/floor-areas/hooks/useFloorAreaEditor.ts`, `frontend/features/floor-areas/services/floorAreasApi.ts`, `frontend/features/floor-areas/types/floorAreasTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx` …
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 12. Final element review

- **Route:** `/workspace/[projectId]/elements`
  - Page: `frontend/app/workspace/[projectId]/elements/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/element-details/components/ElementDetailsPage.tsx`, `frontend/features/element-details/services/elementDetailsService.ts`, `frontend/features/element-details/types/elementDetailsTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx`, `frontend/features/workspace/services/workspaceApi.ts`, `frontend/features/workspace/types/workspaceTypes.ts`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`
- **Route:** `/workspace/[projectId]/type-groups`
  - Page: `frontend/app/workspace/[projectId]/type-groups/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/element-details/components/ElementTypeGroupsPage.tsx`, `frontend/features/element-details/services/elementDetailsService.ts`, `frontend/features/element-details/types/elementDetailsTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkflowPageShell.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`

## 13. BOQ setup, generation, and review

- **Route:** `/workspace/[projectId]/boq`
  - Page: `frontend/app/workspace/[projectId]/boq/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq/components/BoqDashboard.tsx`, `frontend/features/boq/services/boqApi.ts`, `frontend/features/boq/types/boqSetupTypes.ts`, `frontend/features/boq/types/boqTypes.ts`, `frontend/features/template-packages/services/templatePackageService.ts`, `frontend/features/template-packages/types/templatePackageTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkspaceQuickLinks.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/template-packages`
- **Route:** `/workspace/[projectId]/boq/setup`
  - Page: `frontend/app/workspace/[projectId]/boq/setup/page.tsx`
- **Route:** `/workspace/[projectId]/boq/settings`
  - Page: `frontend/app/workspace/[projectId]/boq/settings/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq/components/BoqReportSettingsPage.tsx`, `frontend/features/boq/services/boqSetupApi.ts`, `frontend/features/boq/types/boqSetupTypes.ts`, `frontend/features/boq/types/boqTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkspaceQuickLinks.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`
- **Route:** `/workspace/[projectId]/boq/templates`
  - Page: `frontend/app/workspace/[projectId]/boq/templates/page.tsx`
- **Route:** `/workspace/[projectId]/boq/descriptions`
  - Page: `frontend/app/workspace/[projectId]/boq/descriptions/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq/components/BoqDashboard.tsx`, `frontend/features/boq/services/boqApi.ts`, `frontend/features/boq/types/boqSetupTypes.ts`, `frontend/features/boq/types/boqTypes.ts`, `frontend/features/template-packages/services/templatePackageService.ts`, `frontend/features/template-packages/types/templatePackageTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkspaceQuickLinks.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/template-packages`
- **Route:** `/workspace/[projectId]/boq/autodesk`
  - Page: `frontend/app/workspace/[projectId]/boq/autodesk/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq/components/BoqDashboard.tsx`, `frontend/features/boq/services/boqApi.ts`, `frontend/features/boq/types/boqSetupTypes.ts`, `frontend/features/boq/types/boqTypes.ts`, `frontend/features/template-packages/services/templatePackageService.ts`, `frontend/features/template-packages/types/templatePackageTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkspaceQuickLinks.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/template-packages`

## 14. Exports

- **Route:** `/workspace/[projectId]/export`
  - Page: `frontend/app/workspace/[projectId]/export/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`
- **Route:** `/workspace/[projectId]/boq/export`
  - Page: `frontend/app/workspace/[projectId]/boq/export/page.tsx`
  - Main frontend files: `frontend/features/auth/components/AuthGuard.tsx`, `frontend/features/auth/services/authService.ts`, `frontend/features/boq/components/BoqDashboard.tsx`, `frontend/features/boq/services/boqApi.ts`, `frontend/features/boq/types/boqSetupTypes.ts`, `frontend/features/boq/types/boqTypes.ts`, `frontend/features/template-packages/services/templatePackageService.ts`, `frontend/features/template-packages/types/templatePackageTypes.ts`, `frontend/features/workflow/components/WorkflowNav.tsx`, `frontend/features/workflow/components/WorkspaceQuickLinks.tsx`
  - API paths referenced: `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`, `/api/v1/auth/register`, `/api/v1/template-packages`

## Backend workflow API modules

- `backend/app/api/v1/acc_import_routes.py`: `POST /api/v1/projects/{project_id}/acc-imports`, `POST /api/v1/projects/{project_id}/acc-imports/upload`
- `backend/app/api/v1/boq_autodesk_routes.py`: `GET /api/v1/projects/{project_id}/boq/autodesk/status`, `GET /api/v1/projects/{project_id}/boq/autodesk/authorize`, `GET /api/v1/projects/{project_id}/boq/autodesk/callback`, `GET /api/v1/projects/{project_id}/boq/autodesk/hubs`, `GET /api/v1/projects/{project_id}/boq/autodesk/hubs/{hub_id}/projects`, `POST /api/v1/projects/{project_id}/boq/autodesk/import`, `GET /api/v1/projects/{project_id}/boq/autodesk/packages`, `GET /api/v1/projects/{project_id}/boq/autodesk/package/{record_id}`
- `backend/app/api/v1/boq_description_routes.py`: `GET /api/v1/projects/{project_id}/boq/descriptions/layers`, `GET /api/v1/projects/{project_id}/boq/descriptions/custom`, `PUT /api/v1/projects/{project_id}/boq/descriptions/custom`, `DELETE /api/v1/projects/{project_id}/boq/descriptions/custom/{item_key}`
- `backend/app/api/v1/boq_google_routes.py`: `GET /api/v1/projects/{project_id}/boq/google/status`
- `backend/app/api/v1/boq_routes.py`: `GET /api/v1/projects/{project_id}/boq/source-json`, `GET /api/v1/projects/{project_id}/boq/dashboard`, `GET /api/v1/projects/{project_id}/boq/reports`, `GET /api/v1/projects/{project_id}/boq/reports/latest`, `POST /api/v1/projects/{project_id}/boq/generate`, `POST /api/v1/projects/{project_id}/boq/generate-job`, `GET /api/v1/projects/{project_id}/boq/reports/{report_id}`, `POST /api/v1/projects/{project_id}/boq/reports/{report_id}/exports/{export_type}`, `POST /api/v1/projects/{project_id}/boq/reports/{report_id}/exports/{export_type}/job`, `GET /api/v1/boq/exports/{export_id}/download`
- `backend/app/api/v1/boq_settings_routes.py`: `GET /api/v1/projects/{project_id}/boq/settings`, `PUT /api/v1/projects/{project_id}/boq/settings`, `GET /api/v1/organization/boq/settings`, `PUT /api/v1/organization/boq/settings`
- `backend/app/api/v1/boq_setup_routes.py`: `GET /api/v1/projects/{project_id}/boq/setup`, `PUT /api/v1/projects/{project_id}/boq/setup`, `POST /api/v1/projects/{project_id}/boq/setup/generate`
- `backend/app/api/v1/boq_template_routes.py`: `GET /api/v1/projects/{project_id}/boq/templates`, `POST /api/v1/projects/{project_id}/boq/templates/categories`, `DELETE /api/v1/projects/{project_id}/boq/templates/categories/{category_id}`, `POST /api/v1/projects/{project_id}/boq/templates`, `PUT /api/v1/projects/{project_id}/boq/templates/{template_id}`, `DELETE /api/v1/projects/{project_id}/boq/templates/{template_id}`
- `backend/app/api/v1/canonical_takeoff_routes.py`: `GET /api/v1/canonical-takeoffs`, `GET /api/v1/canonical-takeoffs/{record_id}`, `GET /api/v1/projects/{project_id}/canonical-takeoffs`, `POST /api/v1/projects/{project_id}/canonical-takeoffs/reviewed`, `POST /api/v1/projects/{project_id}/canonical-takeoffs/import`
- `backend/app/api/v1/costx_import_routes.py`: `POST /api/v1/projects/{project_id}/costx-imports`, `POST /api/v1/projects/{project_id}/costx-imports/upload`, `GET /api/v1/projects/{project_id}/costx-imports/connection-status`, `POST /api/v1/projects/{project_id}/costx-imports/test-connection`, `GET /api/v1/projects/{project_id}/costx-imports/workbooks`, `POST /api/v1/projects/{project_id}/costx-imports/api-import`
- `backend/app/api/v1/crop_routes.py`: `POST /api/v1/projects/{project_id}/crops`, `GET /api/v1/projects/{project_id}/crops`, `GET /api/v1/crops/{crop_id}`, `GET /api/v1/crops/{crop_id}/image`, `PUT /api/v1/crops/{crop_id}`, `DELETE /api/v1/crops/{crop_id}`
- `backend/app/api/v1/detection_routes.py`: `POST /api/v1/projects/{project_id}/crops/{crop_id}/analyze-job`, `POST /api/v1/projects/{project_id}/crops/{crop_id}/analyze`, `GET /api/v1/projects/{project_id}/crops/{crop_id}/detections`, `POST /api/v1/projects/{project_id}/crops/{crop_id}/detections`, `PUT /api/v1/projects/{project_id}/crops/{crop_id}/detections/{detection_id}`, `DELETE /api/v1/projects/{project_id}/crops/{crop_id}/detections/{detection_id}`, `GET /api/v1/projects/{project_id}/crops/{crop_id}/model-output/{output_type}`, `POST /api/v1/crops/{crop_id}/detections/run`, `GET /api/v1/crops/{crop_id}/detections`
- `backend/app/api/v1/door_window_schedule_routes.py`: `GET /api/v1/projects/{project_id}/door-window-schedules`, `POST /api/v1/projects/{project_id}/door-window-schedules`, `PATCH /api/v1/projects/{project_id}/door-window-schedules/{schedule_id}`, `DELETE /api/v1/projects/{project_id}/door-window-schedules/{schedule_id}`, `POST /api/v1/projects/{project_id}/door-window-schedules/{schedule_id}/apply`, `POST /api/v1/projects/{project_id}/door-window-schedules/items/{item_id}/manual-dimensions`, `POST /api/v1/projects/{project_id}/door-window-schedules/apply-common-height`
- `backend/app/api/v1/drawing_setup_routes.py`: `GET /api/v1/projects/{project_id}/drawing-setup`, `PUT /api/v1/projects/{project_id}/drawing-setup`
- `backend/app/api/v1/element_detail_routes.py`: `GET /api/v1/projects/{project_id}/element-details`, `POST /api/v1/projects/{project_id}/element-details/prepare-final-data`, `POST /api/v1/projects/{project_id}/element-details/prepare-final-data/job`, `GET /api/v1/projects/{project_id}/element-details/processing-status`, `POST /api/v1/projects/{project_id}/element-details/start-processing`, `POST /api/v1/projects/{project_id}/element-details/force-reprocess`, `POST /api/v1/projects/{project_id}/element-details/assign`, `GET /api/v1/projects/{project_id}/element-details/type-groups`, `POST /api/v1/projects/{project_id}/element-details/type-groups/auto`, `POST /api/v1/projects/{project_id}/element-details/type-groups`, `PATCH /api/v1/projects/{project_id}/element-details/type-groups/{group_id}`, `POST /api/v1/projects/{project_id}/element-details/type-groups/{group_id}/assign-items`, `POST /api/v1/projects/{project_id}/element-details/elevation-crops`, `POST /api/v1/projects/{project_id}/element-details/elevation-crops/generate`, `POST /api/v1/projects/{project_id}/element-details/refine`, `POST /api/v1/projects/{project_id}/element-details/elevation-crops/refine-all`, `POST /api/v1/projects/{project_id}/element-details/{item_id}/refine`, `POST /api/v1/projects/{project_id}/element-details/elevation-crops/{item_id}/refine`, `POST /api/v1/projects/{project_id}/element-details/{item_id}/manual-crop`, `POST /api/v1/projects/{project_id}/element-details/elevation-crops/{item_id}/manual-box`, `GET /api/v1/projects/{project_id}/element-details/{item_id}/crop-image`, `POST /api/v1/projects/{project_id}/element-details/wall-height`, `POST /api/v1/projects/{project_id}/element-details/defaults`, `PATCH /api/v1/projects/{project_id}/element-details/{item_id}`, `POST /api/v1/projects/{project_id}/element-details/structured`
- `backend/app/api/v1/element_match_routes.py`: `POST /api/v1/projects/{project_id}/element-matches/run`, `GET /api/v1/projects/{project_id}/element-matches`, `PUT /api/v1/projects/{project_id}/element-matches/{match_id}/confirm`, `PUT /api/v1/projects/{project_id}/element-matches/{match_id}/reject`
- `backend/app/api/v1/element_type_routes.py`: `GET /api/v1/projects/{project_id}/element-types`, `POST /api/v1/projects/{project_id}/element-types`, `PUT /api/v1/projects/{project_id}/element-types/{type_id}`, `DELETE /api/v1/projects/{project_id}/element-types/{type_id}`
- `backend/app/api/v1/export_routes.py`: `POST /api/v1/projects/{project_id}/exports/combined-pdf`, `POST /api/v1/projects/{project_id}/exports/zip`, `POST /api/v1/projects/{project_id}/exports/metadata`, `POST /api/v1/projects/{project_id}/exports/model-package`, `GET /api/v1/exports/{export_id}/download`
- `backend/app/api/v1/exterior_boundary_routes.py`: `GET /api/v1/projects/{project_id}/exterior-boundary`, `POST /api/v1/projects/{project_id}/exterior-boundary/generate`, `PUT /api/v1/projects/{project_id}/exterior-boundary`
- `backend/app/api/v1/external_import_routes.py`: `POST /api/v1/projects/{project_id}/external-imports`, `POST /api/v1/projects/{project_id}/external-imports/upload`
- `backend/app/api/v1/floor_area_routes.py`: `GET /api/v1/projects/{project_id}/floor-areas`, `POST /api/v1/projects/{project_id}/floor-areas/run-takeoff`, `POST /api/v1/projects/{project_id}/floor-areas/manual`, `PATCH /api/v1/projects/{project_id}/floor-areas/{zone_id}`, `POST /api/v1/projects/{project_id}/floor-areas/{zone_id}/confirm`, `DELETE /api/v1/projects/{project_id}/floor-areas/{zone_id}`
- `backend/app/api/v1/floor_takeoff_routes.py`: `GET /api/v1/projects/{project_id}/floor-takeoff`, `POST /api/v1/projects/{project_id}/floor-takeoff/generate`, `POST /api/v1/projects/{project_id}/floor-takeoff/generate-job`, `PATCH /api/v1/projects/{project_id}/floor-takeoff/{floor_id}`, `POST /api/v1/projects/{project_id}/floor-takeoff/sync-final-review`, `POST /api/v1/projects/{project_id}/floor-takeoff/{floor_id}/accept`, `POST /api/v1/projects/{project_id}/floor-takeoff/{floor_id}/reject`, `POST /api/v1/projects/{project_id}/floor-takeoff/{floor_id}/recalculate`, `POST /api/v1/projects/{project_id}/floor-takeoff/manual-polygon`, `DELETE /api/v1/projects/{project_id}/floor-takeoff/{floor_id}`
- `backend/app/api/v1/job_routes.py`: `GET /api/v1/jobs/types`, `GET /api/v1/jobs/{job_id}`, `GET /api/v1/projects/{project_id}/jobs`
- `backend/app/api/v1/mapping_routes.py`: `GET /api/v1/projects/{project_id}/mapping`, `PUT /api/v1/projects/{project_id}/mapping/elevations/{elevation_type}`, `PUT /api/v1/projects/{project_id}/mapping/walls`, `DELETE /api/v1/projects/{project_id}/mapping/elevations/{elevation_type}`
- `backend/app/api/v1/pdf_routes.py`: `GET /api/v1/projects/{project_id}/pages`, `GET /api/v1/projects/{project_id}/pages/{page_number}/image`, `GET /api/v1/projects/{project_id}/pages/{page_number}/thumbnail`, `POST /api/v1/projects/{project_id}/pages/{page_number}/render`
- `backend/app/api/v1/plan_tag_routes.py`: `POST /api/v1/projects/{project_id}/plan-tags/run`, `GET /api/v1/projects/{project_id}/plan-tags`, `GET /api/v1/projects/{project_id}/detections/{detection_id}/plan-tags`, `PUT /api/v1/projects/{project_id}/detections/{detection_id}/plan-tags`
- `backend/app/api/v1/project_status_routes.py`: `GET /api/v1/projects/{project_id}/status`, `POST /api/v1/projects/{project_id}/status/refresh`
- `backend/app/api/v1/revit_import_routes.py`: `POST /api/v1/projects/{project_id}/revit-imports`, `POST /api/v1/projects/{project_id}/revit-imports/upload`, `POST /api/v1/projects/{project_id}/revit-imports/cloud-import`
- `backend/app/api/v1/scale_routes.py`: `GET /api/v1/projects/{project_id}/scale-calibrations`, `PUT /api/v1/projects/{project_id}/scale-calibrations`
- `backend/app/api/v1/schedule_routes.py`: `POST /api/v1/projects/{project_id}/schedules/extract-job`
- `backend/app/api/v1/spec_extraction_routes.py`: `POST /api/v1/projects/{project_id}/spec-extraction/run`, `GET /api/v1/projects/{project_id}/spec-extraction/latest`, `GET /api/v1/projects/{project_id}/spec-extraction/records`
- `backend/app/api/v1/supporting_document_routes.py`: `GET /api/v1/projects/{project_id}/supporting-documents`, `POST /api/v1/projects/{project_id}/supporting-documents/upload`, `POST /api/v1/projects/{project_id}/supporting-documents/crop`, `POST /api/v1/projects/{project_id}/supporting-documents/{document_type}/skip`, `DELETE /api/v1/projects/{project_id}/supporting-documents/{document_id}`, `GET /api/v1/supporting-documents/{document_id}/file`
- `backend/app/api/v1/takeoff_export_routes.py`: `GET /api/v1/projects/{project_id}/exports/takeoff-json`
- `backend/app/api/v1/template_package_routes.py`: `GET /api/v1/template-packages`, `POST /api/v1/template-packages`, `GET /api/v1/template-packages/projects/{project_id}/assignment`, `POST /api/v1/template-packages/projects/{project_id}/assignment`, `POST /api/v1/template-packages/organizations/{organization_id}/assignment`, `GET /api/v1/template-packages/{package_id}`, `PUT /api/v1/template-packages/{package_id}`
- `backend/app/api/v1/wall_measurement_routes.py`: `GET /api/v1/projects/{project_id}/walls`, `POST /api/v1/projects/{project_id}/walls/prepare`, `POST /api/v1/projects/{project_id}/walls/prepare-job`, `POST /api/v1/projects/{project_id}/walls/extract-types`, `POST /api/v1/projects/{project_id}/walls/extract-types-job`, `POST /api/v1/projects/{project_id}/walls/types`, `PATCH /api/v1/projects/{project_id}/walls/types/{type_id}`, `DELETE /api/v1/projects/{project_id}/walls/types/{type_id}`, `POST /api/v1/projects/{project_id}/walls/segments`, `PATCH /api/v1/projects/{project_id}/walls/segments/{segment_id}`, `DELETE /api/v1/projects/{project_id}/walls/segments/{segment_id}`, `POST /api/v1/projects/{project_id}/walls/apply-thickness`, `GET /api/v1/projects/{project_id}/walls/height-sources`, `POST /api/v1/projects/{project_id}/walls/height-sources/suggest`, `POST /api/v1/projects/{project_id}/walls/height-sources-job`, `POST /api/v1/projects/{project_id}/walls/height-sources/crop`, `POST /api/v1/projects/{project_id}/walls/height-sources/selection`, `POST /api/v1/projects/{project_id}/walls/overlay-mapping`, `POST /api/v1/projects/{project_id}/walls/height-sources/auto-align`, `POST /api/v1/projects/{project_id}/walls/height-sources/reference-align`, `POST /api/v1/projects/{project_id}/walls/height-align-job`, `POST /api/v1/projects/{project_id}/walls/height-reference-align-job`, `POST /api/v1/projects/{project_id}/walls/height-zones`, `POST /api/v1/projects/{project_id}/walls/assign-height-zone`, `POST /api/v1/projects/{project_id}/walls/area-drawings`, `POST /api/v1/projects/{project_id}/walls/area-drawings/suggest-match`, `POST /api/v1/projects/{project_id}/walls/area-drawings/apply`, `DELETE /api/v1/projects/{project_id}/walls/area-drawings/{drawing_id}`, `POST /api/v1/projects/{project_id}/walls/apply-height`, `POST /api/v1/projects/{project_id}/walls/link-openings`, `POST /api/v1/projects/{project_id}/walls/link-openings-job`, `PUT /api/v1/projects/{project_id}/walls/segments/{segment_id}/openings`, `POST /api/v1/projects/{project_id}/walls/calculate`, `POST /api/v1/projects/{project_id}/walls/calculate-job`, `POST /api/v1/projects/{project_id}/walls/sync-locations`, `POST /api/v1/projects/{project_id}/walls/sync-locations-job`, `POST /api/v1/projects/{project_id}/walls/sync-final-review`, `POST /api/v1/projects/{project_id}/walls/sync-final-review-job`, `GET /api/v1/projects/{project_id}/walls/boq-summary`
- `backend/app/api/v1/wall_takeoff_routes.py`: `GET /api/v1/projects/{project_id}/wall-takeoff`, `POST /api/v1/projects/{project_id}/wall-takeoff/generate`, `POST /api/v1/projects/{project_id}/wall-takeoff/generate-job`, `PATCH /api/v1/projects/{project_id}/wall-takeoff/{wall_id}`, `POST /api/v1/projects/{project_id}/wall-takeoff/{wall_id}/recalculate`

## Background jobs registered by the original worker

- `pdf_rendering` (`PDF_RENDER_JOB_TYPE`)
- `specification_extraction` (`SPECIFICATION_EXTRACTION_JOB_TYPE`)
- `detection` (`DETECTION_JOB_TYPE`)
- `final_review_preparation` (`FINAL_REVIEW_JOB_TYPE`)
- `wall_takeoff` (`WALL_TAKEOFF_JOB_TYPE`)
- `floor_takeoff` (`FLOOR_TAKEOFF_JOB_TYPE`)
- `boq_generation` (`BOQ_GENERATION_JOB_TYPE`)
- `boq_export` (`BOQ_EXPORT_JOB_TYPE`)
- `wall_measurement_prepare` (`WALL_MEASUREMENT_PREPARE_JOB_TYPE`)
- `wall_type_extraction` (`WALL_TYPE_EXTRACTION_JOB_TYPE`)
- `wall_geometry_normalization` (`WALL_GEOMETRY_NORMALIZATION_JOB_TYPE`)
- `wall_opening_linking` (`WALL_OPENING_LINKING_JOB_TYPE`)
- `wall_height_suggestion` (`WALL_HEIGHT_SUGGESTION_JOB_TYPE`)
- `wall_height_alignment` (`WALL_HEIGHT_ALIGNMENT_JOB_TYPE`)
- `wall_height_reference_alignment` (`WALL_HEIGHT_REFERENCE_ALIGNMENT_JOB_TYPE`)
- `wall_area_calculation` (`WALL_AREA_CALCULATION_JOB_TYPE`)
- `wall_review_sync` (`WALL_REVIEW_SYNC_JOB_TYPE`)
- `wall_location_sync` (`WALL_LOCATION_SYNC_JOB_TYPE`)

## Original workflow database tables

- `exported_files`
- `project_status_cache`
- `pdf_pages`
- `crops`
- `drawing_setups`
- `scale_calibrations`
- `elevation_mappings`
- `takeoff_elements`
- `exports`
- `canonical_takeoffs`
- `element_details`
- `element_detail_versions`
- `element_detail_records`
- `element_type_groups`
- `element_processing_status`
- `structured_element_exports`
- `exterior_boundaries`
- `door_window_schedules`
- `wall_height_profiles`
- `boq_template_categories`
- `boq_templates`
- `boq_custom_descriptions`
- `boq_reports`
- `boq_report_items`
- `boq_external_tokens`
- `boq_poller_jobs`
- `template_packages`
- `template_package_items`
- `project_template_assignments`
- `organization_template_assignments`
- `organization_boq_settings`
- `project_boq_settings`
- `boq_document_setups`
- `supporting_documents`
- `spec_extraction_records`
- `plan_tag_matches`
- `element_schedule_matches`
- `floor_area_zones`
- `wall_measurement_types`
- `wall_measurement_segments`
- `wall_measurement_height_zones`
- `wall_measurement_opening_deductions`
- `wall_measurement_overlay_mappings`
- `wall_measurement_review_items`
- `wall_measurement_project_state`
- `detections`
- `project_status_cache`
- `does`
