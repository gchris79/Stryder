# Changelog
All notable changes to **Stryder** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---
## [1.3.0] - 2025-08-14
### 🎯 New: Summaries
- Weekly and Rolling 4-week summaries from your SQLite data.
- Shows total distance & time, average pace, average power, and average HR.
- Clean formatting, sensible defaults, and timezone-aware date windows.

### Fixes & polish
- Prevented bad `avg_power` values from crashing summaries (legacy rows are coerced to numeric).
- Unified add/import prompts behave consistently for single and batch.
- `find-unparsed` closes its DB connection cleanly.- Safer error messages in single add (no undefined variable references).

### Upgrade notes
If you inserted single runs on v1.2.x, you may have string values in `runs.avg_power`. Run:
```sql
UPDATE runs
SET avg_power = NULL
WHERE typeof(avg_power)='text' OR avg_power GLOB '*:*';
```

---

## [1.2.1] - 2025-08-03
### Fixed
- Corrected `find-unparsed` error: “too many values to unpack (expected 3)”
- Fixed `add-single` path handling (“no such file or directory”)

---

## [1.2.0] - 2025-08-02
### Added
- `view` CLI command to display runs stored in the database
- Version tracking via Git tags (`version.py` integration)

---

## [1.1.0] - 2025-07-31
### Added
- Timezone prompt remembers last value per batch
- `find-unparsed` with manual match / skip / try another TZ options

### Changed
- Batch import skips unmatched runs to preserve data integrity

---

## [1.0.0] - 2025-07-30
### Added
- Initial CLI version of Stryder
- Batch import with timezone-aware Garmin matching
- SQLite database storage
- Basic logging

