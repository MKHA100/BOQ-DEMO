# Git Details by Prompt

## Prompt 4 — Scale

### Backend
Branch name: `feature/multi-floor-scale-backend`  
Commit message: `feat: add multi-floor scale calibration`  
Commit description: Adds floor-scoped calibration records, validation, versioning, and targeted measurement jobs.  
PR title: `Add Multi-Floor Scale Backend`  
PR description: Introduces known-distance calibration and dependent floor recalculation without rerunning detections.

### Frontend
Branch name: `feature/multi-floor-scale-page`  
Commit message: `feat: add multi-floor scale page`  
Commit description: Adds precise point calibration, optional verification, floor status, and saved drawing state.  
PR title: `Add Multi-Floor Scale Page`  
PR description: Introduces the floor-scoped Scale workspace with stable drawing coordinates and immediate saves.

## Prompt 5 — Model Review

### Backend
Branch name: `feature/model-review-backend`  
Commit message: `feat: add multi-floor model review`  
Commit description: Adds floor-isolated detections, element edits, schedule assignment, confirmed-value protection, and targeted jobs.  
PR title: `Add Multi-Floor Model Review Backend`  
PR description: Connects saved model results to canonical project elements and dependent calculations.

### Frontend
Branch name: `feature/model-review-page`  
Commit message: `feat: add model review page`  
Commit description: Adds floor switching, element filters, drawing overlays, box editing, and the selected-element inspector.  
PR title: `Add Multi-Floor Model Review Page`  
PR description: Introduces a fast review workspace for doors, windows, walls, and missing-element corrections.

## Prompt 6 — Walls

### Backend
Branch name: `feature/walls-backend`  
Commit message: `feat: add wall takeoff processing`  
Commit description: Adds centerlines, wall classification, explicit opening relationships, NRM2 deductions, and targeted room/BOQ updates.  
PR title: `Add Multi-Floor Walls Backend`  
PR description: Introduces floor-isolated wall geometry and quantity calculations using canonical openings.

### Frontend
Branch name: `feature/walls-page`  
Commit message: `feat: add walls page`  
Commit description: Adds wall overlays, classification and type controls, centerline tools, openings, finishes, and quantities.  
PR title: `Add Multi-Floor Walls Page`  
PR description: Introduces the wall review and takeoff workspace for every project floor.

## Prompt 7 — Floors

### Backend
Branch name: `feature/floors-backend`  
Commit message: `feat: add room and floor takeoff`  
Commit description: Adds room polygonization, measurements, labels, finishes, manual geometry edits, and wall dependencies.  
PR title: `Add Multi-Floor Room Takeoff Backend`  
PR description: Introduces automatic-first room records and targeted floor quantity updates.

### Frontend
Branch name: `feature/floors-page`  
Commit message: `feat: add floors page`  
Commit description: Adds room polygons, manual corrections, room details, finishes, and floor-scoped navigation.  
PR title: `Add Multi-Floor Floors Page`  
PR description: Introduces the room and floor finish takeoff workspace.

## Prompt 8 — Review

### Backend
Branch name: `feature/review-backend`  
Commit message: `feat: add canonical project review`  
Commit description: Adds fast review summaries, canonical item updates, confirmation rules, and floor/category filtering.  
PR title: `Add Multi-Floor Review Backend`  
PR description: Introduces a prepared review model while retaining canonical entities as the source of truth.

### Frontend
Branch name: `feature/review-page`  
Commit message: `feat: add project review page`  
Commit description: Adds floor filters, category tables, item details, confirmations, and source-page links.  
PR title: `Add Multi-Floor Review Page`  
PR description: Introduces the connected final review experience for doors, windows, walls, and floors.

## Prompt 9 — BOQ

### Backend
Branch name: `feature/boq-backend`  
Commit message: `feat: add multi-floor BOQ generation`  
Commit description: Adds template-driven grouping, traceable rows, manual item protection, targeted refresh, and cached exports.  
PR title: `Add Multi-Floor BOQ Backend`  
PR description: Connects confirmed canonical quantities to combined and floor-specific BOQ outputs.

### Frontend
Branch name: `feature/boq-page`  
Commit message: `feat: add BOQ page`  
Commit description: Adds floor and grouping controls, professional BOQ tables, manual rows, and export actions.  
PR title: `Add Multi-Floor BOQ Page`  
PR description: Introduces the final project BOQ workspace with traceable saved quantities.

## Prompt 10 — Integration and QA

### Backend
Branch name: `feature/end-to-end-integration`  
Commit message: `feat: complete workflow integration and reliability`  
Commit description: Adds targeted cross-page dependencies, version-aware workers, continuous heartbeats, recovery indexes, readiness checks, and integration tests.  
PR title: `Complete Backend Workflow Integration`  
PR description: Verifies durable synchronization, floor isolation, worker recovery, database consistency, and production diagnostics across the AutoBOQ workflow.

### Frontend
Branch name: `feature/workflow-production-qa`  
Commit message: `feat: finalize workflow UI integration`  
Commit description: Aligns shared workflow layout, removes duplicate floor controls, and verifies all production page builds.  
PR title: `Complete Frontend Workflow Integration`  
PR description: Finalizes the connected AutoBOQ workflow experience and validates consistent, fast page behavior.
