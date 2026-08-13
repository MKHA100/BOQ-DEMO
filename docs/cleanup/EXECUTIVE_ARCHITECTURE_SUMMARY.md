# Executive Architecture Summary

## Current project

The supplied project contains a Next.js 14 frontend and a FastAPI backend. The general platform layer covers authentication, dashboard navigation, projects, organizations, members, roles, subscription plans, billing, account settings, notifications, audit logs, SQLite/PostgreSQL selection, local/R2 storage, and shared error/API infrastructure.

The old document pipeline is a second, much larger subsystem. It begins with PDF upload and page rendering, then continues through crop setup, schedule/specification extraction, scale calibration, elevation mapping, Roboflow detection, element matching, elevation height extraction, wall measurement, floor-area takeoff, final review, BOQ generation, external imports, and PDF/Excel/CSV/package exports. It is connected to the general application through the project table/service, dashboard and sidebar links, workspace routes, the central schema, job queue registrations, environment settings, and storage directories.

## Resulting clean project

The clean copy retains the general platform and rewrites the project entity as a neutral construction project. Project creation now accepts only a project name and does not upload, render, inspect, or process a PDF. The old workspace subroutes and all workflow API modules are removed. The dashboard and sidebar retain their established layout but replace **Automated BOQ** with **PDF Generation** and remove old output/template links.

`/pdf-generation` is a calm, empty workspace shell. It imports no PDF service, starts no polling hook, makes no workflow request, and registers no backend processing endpoint. Generic storage and a generic database job repository/registry remain available for the future implementation.

## Source inspection scope

- Original relevant source/config/document files inventoried: **859**
- Original workflow-connected files in the detailed workflow inventory: **745**
- Original backend endpoint definitions inventoried: **251**
- Clean project relevant files: **135**

The complete per-file classification is in `FILE_CLASSIFICATION.csv`; the full workflow-connected file inventory is in `PDF_WORKFLOW_FILES.csv`.

## Separate-project integrity

The extracted `original-project` was never edited. All changes were made only in `new-simple-project`; a fresh extraction of the supplied ZIP matched the retained original reference exactly.
