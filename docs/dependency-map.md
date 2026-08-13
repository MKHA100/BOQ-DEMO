# Data Dependency Map

## Main chain

```text
Document / DocumentPage
→ FloorCrop
→ Calibration
→ Element
→ ElementProperty / ElementRelation
→ Wall
→ Room
→ ReviewIssue / QuantitySnapshot
→ BOQ / BOQRow
→ Export
```

## Targeted mutation rules

### Element property change

```text
Save canonical ElementProperty
→ increment floor.element_version
→ mark only related wall stale when an opening relation exists
→ increment floor.review_version and floor.boq_version
→ enqueue walls.recalculate_deduction for related wall only
→ enqueue review.refresh for the changed element
→ enqueue boq.refresh for affected element/wall rows
```

No unrelated floor, model detection, or room-build job is enqueued.

### Floor calibration change

```text
Save confirmed Calibration
→ increment selected floor.scale_version
→ preserve detections and confirmed element types
→ mark selected floor measurement, wall, room, review, and BOQ read models stale
→ enqueue selected-floor measurement/wall/room/review/BOQ jobs
```

Other floors keep their versions and outputs.

### Room polygon change

```text
Save canonical Room geometry
→ increment selected floor.room_version
→ mark that room quantity stale
→ increment selected floor.review_version and boq_version
→ enqueue rooms.measure for that room
→ enqueue review.refresh for that room
→ enqueue boq.refresh for that room's finish rows
```

### Floor crop change

```text
Save a new current FloorCrop
→ increment selected floor.crop_version
→ invalidate selected-floor calibration and downstream measured outputs
→ enqueue detection/review/BOQ tasks for the changed crop versions
```

Later crop processors should add page rendering/measurement tasks without broad project reprocessing.

### Schedule/specification source

```text
Register source file
→ increment project or floor source version
→ enqueue only the matching extraction task
→ extraction writes prioritized suggestions/canonical values
→ conflicts with confirmed values become ReviewIssue records
```

## Frontend cache rules

- Project workflow summary: `workflow.summary(projectId)`.
- Floor/entity detail queries will use separate project/floor/entity keys when later pages are implemented.
- Mutations patch the exact cached record where practical.
- Only dependency-related query keys are invalidated.
- Summary polling is enabled only when `active_jobs` is non-empty.
