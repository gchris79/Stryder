# Changelog
All notable changes to **Stryder** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]
### Added
- `summary` CLI command for quick training stats:
  - Total mileage
  - Average heart rate
  - Longest run
  - Fastest 5K
- Improved batch import summaries (parsed vs skipped)
- Enhanced "last used paths" prompt sequence for better UX

### Changed
- Updated documentation in README.md to reflect new commands

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

