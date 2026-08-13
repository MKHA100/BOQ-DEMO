# Worker Task Map

## Runtime

Jobs are persisted in `job_runs`, claimed transactionally, protected by leases and heartbeats, and deduplicated by deterministic job keys. Equivalent work for the same project, floor, entity, and input versions reuses its canonical job row.

HTTP calls to Roboflow and OpenAI run outside database write transactions. Floor-scoped jobs also reject superseded crop, scale, or wall versions before executing.

## Priority lanes

| Lane | Tasks | Default concurrency |
|---|---|---:|
| Fast | `render.floor_crop`, `extract.floor_crop_text`, `rooms.publish_model_results` | 1 |
| Detection | `vision.detect_rooms`, `vision.detect_floor_elements` | 2, configurable |
| Interpretation | `rooms.interpret_floor` | 1 |
| Precision | `rooms.precision_refine`, `rooms.calculate_areas` | 1, configurable |
| Read model | `review.refresh`, `boq.refresh` | 1 |
| Main | Remaining ingestion, wall, room-preparation, and export tasks | 1 |

The preview renderer has the highest queue priority. Detection workers may process two floors in parallel, while floor interpretation remains serialized and precision concurrency is intentionally conservative for SQLite.

## Floor room chain

```text
render.floor_crop
├─ extract.floor_crop_text
├─ vision.detect_rooms → rooms.publish_model_results
└─ vision.detect_floor_elements

rooms.prepare_lines
→ rooms.build_polygons
→ rooms.reconcile
→ rooms.identify_labels
→ rooms.assign_finishes
→ rooms.interpret_floor
→ rooms.precision_refine
→ rooms.calculate_areas
→ review.refresh + boq.refresh
```

The room-model result is saved and shown before interpretation or precision correction completes. An unavailable LLM does not stop the local geometry chain. The final calculation schedules exactly one Review refresh and one BOQ refresh.

## Job key

```text
project:{project_id}
floor:{floor_id or project}
task:{task_type}
entity:{entity_id or scope}
input:{sha256(normalized input versions)}
```
