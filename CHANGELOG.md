# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https.keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https.semver.org/spec/v2.0.0.html).

## [0.18] - 2025-06-25

### Added
- Heart rate chart to the workout details page.
- Synchronized time axis for all charts on the details page, starting at 0:00.
- Heart Rate Zone settings.
- Equipment selection dropdown for manual workout entries.
- Display of total participants in workout rankings.
- Average power and heart rate to the workout details summary.
- 500m split summary table to the details page.
- Heart rate zone summary table to the details page.

### Fixed
- Charts now correctly align even if heart rate data begins after the workout starts.
- Corrected the average heart rate calculation to exclude null values.
- Resolved various minor bugs and visual inconsistencies in the charting implementation.
- Prevented `UnboundLocalError` on the details page when a workout was missing certain metric data (e.g., heart rate, distance).

### Changed
- DB schema updated to 0.18.
