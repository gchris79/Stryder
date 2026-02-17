# Changelog
All notable changes to **Stryder** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
---

## [1.8.0] – 2026-02-17
### 🎯 New: Textual TUI Interface

- Introduced full Textual-based Terminal UI (TUI).
- Interactive import workflow with progress screen.
- Integrated `find-unparsed` review inside TUI.
- DataTable-based run views with pagination.
- Terminal graph visualizations using plotext.
- Dedicated TUI entry point (`stryder_tui`).

### Improved
- Non-blocking import operations using background workers.
- Cleaner navigation between screens.
- Safer input handling inside TUI forms.
- Clear separation between CLI and TUI execution modes.

### Internal
- Refactored import pipeline to support async UI execution.
- UI layer reorganized around screens and event handlers.
- Reduced duplication between CLI and TUI logic.

---
## [1.7.0] - 2025-12-27
### 🌐 Stryder Web (Django) – Initial Viewer Release

### Major Changes
- Introduced **Stryder Web**, a Django-based local web viewer built on top of Stryder Core.
- Established a multi-interface architecture: Core logic shared across CLI and Web.
- Web UI operates as a read-only analytics layer on the same database used by the CLI.

### Web Features
- Single run report view with interactive graph.
- Custom date range reports for aggregated analysis.
- User-selectable X/Y axes for graphs.
- Improved layout and styling to present reports as full-page views.

### CLI Improvements
- Fixed an issue where unparsed runs were not correctly skipped during processing.
- Verified continued stability and compatibility of existing CLI workflows.

### Notes
- Stryder Web complements the CLI and does not replace it.
- Data import and parsing remain CLI-driven.

---
## [1.6.0] - 2025-11-27
### 🎯 Core / CLI Split & Stability Improvements

### Major Changes
- Refactored codebase to separate core logic from the CLI interface, improving modularity and preparing for future UI layers (Textual, Django).
- Unified parsing, matching, and reporting logic inside the core module.
### Improvements
- More consistent and stable single-run and batch parsing behavior.
- Single-run now properly detects and skips already-inserted runs.
- Cleaner and more predictable handling of logs and CLI output.
### Visualizations
- Fixed Matplotlib tick formatter signature issues (fmt_hm, fmt_hms, fmt_pace_km, fmt_pace_no_unit).
- Improved time and pace axis formatting for reports.
### Bug Fixes
- Resolved TypeError in visualizations due to missing (value, pos) signature.
- Fixed edge cases involving elapsed time calculations.
- General cleanup and removal of outdated code paths.

---
## [1.5.1] – 2025-11-22
### 📑 Function Documentation

- Single line documentation for all the functions
- Fixed a bug in views that surfaced after refactoring

---
## [1.5.0] – 2025-11-15
### 🎯 Major Refactor: Canonical Metrics & Weekly Reports

- Introduced canonical metric names across the entire parsing and reporting pipeline
(consistent distance_km, unified labels/units, no more legacy aliases).
- Refactored file parsing, pipeline, batch import, and find-unparsed to emit
and consume canonical fields cleanly.
- Updated weekly reports to correctly output distance_km (fixed old mislabeling of km as meters).
- Unified weekly plot logic:
- Removed tick_mode (now always uses week_start ticks).
- Correctly aligned bars/ticks/grid for both calendar and rolling reports.
- Refactored visualizations.py to rely solely on canonical names (consistent x/y axis labeling).
- Improved internal date utilities, formatting, and utils for clearer timestamp handling.
- Cleaned dead code, removed inconsistent distance_m/km fallbacks, and modernized several modules.

🔧 Internal Quality Improvements

- Deep cleanup across 12 project files, reducing ambiguity and technical debt.

- Standardized data flow from CSV → parsing → DB → reports → plots.

- Improved future maintainability and debugging clarity.
---
## [1.4.5] - 2025-09-24
### 🎯 New: Pagination
- Pagination in views and single-run reports.
- Improved: Centralized metrics dictionary for reports (no hardcoded labels/units).
- Improved: More robust date input handling (no crashes on bad input).
- Improved: Path saving & timezone bootstrapping (Windows/Linux).
- Fixed: “Back” navigation behavior across menus.
- Fixed: Keyword/date filtered pagination pipeline alignment.

---

## [1.4.0] - 2025-08-21
### 🎯 New: Single Run Reports
- Single run reports and graph visualizations on power,pace,ground time, LSS, Cadence and Vertical Oscillation.
- Improved: Weekly mileage visualization (weekly rolling plot).
- Improved: CLI menu orchestration for reports and views.
- Fixed: Batch vs. find-unparsed logic (skips invalid Stryd CSVs).
- Fixed: Guard against empty/zero Stryd data on import.

---
## [1.3.0] - 2025-08-14
### 🎯 New: Summaries
- Weekly and Rolling weekly summaries from your SQLite data.
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

