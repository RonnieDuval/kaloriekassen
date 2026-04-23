# Minimal refactor toward a central fitness data system

## 1) Tight coupling found in current ingestion

- Sync adapters are tightly coupled to provider-specific response shape and directly map to daily aggregate tables (`raw_mfp`, `raw_fitbit`, `raw_intervals`).
- No shared immutable event log means normalization/export logic depends on provider tables directly.
- Canonical modeling and dedupe are missing; activity provider data is flattened at day-level too early.
- Export preparation is mixed conceptually with analytics (`daily_balance` view) because no sync state tables exist.

## 2) Minimal module restructuring (incremental)

- Keep existing sync entry points and raw aggregate tables (backward compatible).
- Add `raw_event` ingestion hook in `BaseSyncAdapter` (default no-op).
- Add `src/pipeline/` for normalization jobs:
  - `normalize.py` for activity + source links with basic dedupe.
  - `normalize_nutrition.py` for MFP meal-entry normalization.
- Add `src/export/google_health.py` as minimal queue/mark module for idempotent export lifecycle.
- Keep DB as source of truth, with all dedupe and export state persisted in SQL tables.

## 3) Canonical model additions

- `raw_event`: immutable payload store (`payload_sha256` uniqueness).
- `activity`: canonical deduped activity rows.
- `activity_source_link`: map one canonical activity to multiple provider activities.
- `nutrition_entry`: meal-level entries from MyFitnessPal diary meals.
- `export_google_health_activity` and `export_google_health_nutrition`: idempotent export queue/state.

## 4) First dedupe version

- Normalize `raw_event` with `source_event_type='activity'` into canonical `activity`.
- First-pass dedupe key: rounded `(start_minute, activity_type, distance, calories)` hash.
- If dedupe key already exists, only add a new `activity_source_link` with confidence `0.90`.
- If no match, create canonical activity and link with confidence `1.0`.

## 5) Google Health export outline (minimal)

- Queue export rows keyed by `(entity_id, export_hash)`.
- Fetch pending rows in created order.
- Mark success/failure with attempts and timestamps.
- Keep API client integration separate; this module only manages DB idempotency and lifecycle.
