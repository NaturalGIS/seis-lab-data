# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]


### Added

- Teledyne PDS `.pds` files get their acquisition date, CRS and planned survey area from the file header


### Fixed

- Records created during discovery not checking for duplicate names
- Bulk-updated records not being validated, nor published or unpublished accordingly
- Filtering by spatial extent including projects, survey missions and records without a spatial extent


## [1.0.0-rc2] - 2026-11-19

### Added

- systemd unit files for cleaning up docker images and containers regularly and keep test and prod envs from running out of disk space
- PDF report of the automated test results
- Client-facing docstrings for all test modules and tests
- System version shown in the UI footer and in the STAC API - the tag for tagged releases, otherwise the branch and commit
- User guide
- Admin guide section on managing user accounts: creating them, giving them the editor role and deactivating them
- `session_max_age_seconds` setting, defaulting to one week, for the lifetime of the session cookie


### Changed

- admin guide now contains information on how to set up the systemd units for cleaning up docker images and containers
- Test modules and tests require docstrings, enforced by ruff (`D100`/`D103`, only in `tests/**/test_*.py`)
- CI stores the results of the unit, integration and end-to-end tests as a workflow artifact
- CI publishes the docker image from the cached layers of the tested build, instead of building it again
- The docker image stores its version information in the `git_commit`, `git_tag` and `git_branch` settings, replacing the unused `GIT_COMMIT` environment variable and `git-commit.txt` file
- Improved version of sysadmin guide
- Improved version of dev guide
- A spatial extent is no longer required for a survey-related record to be valid. Projects and survey missions still require one
- The asset discovery configurations for the magnetometer `.ovr` and `.xml` auxiliary files were removed from the bootstrap data
- Changing the implicit CRS of a survey mission and running the discovery again now corrects the records already discovered
- Users stay logged in, also after closing the browser, until they log out or have not used the system for a week. See the upgrade steps for version 1.0.0-rc1 in the admin guide
- Changes to a user's roles in authentik take effect when their access token is next renewed, within an hour, instead of at their next login
- Logging out revokes the refresh and access tokens in authentik
- The session cookie only keeps the user info claims that are used by the system, reducing its size


### Removed

- Unused `TokenIntrospectionMiddleware` and `AuthConfig.token_introspection_cache_seconds`


### Fixed

- Language picker of the docs site linking to the wrong URL from the home pages when the site is served under a path prefix, as in the test and prod environments
- A discovery re-run did not update the spatial extent of a record when its file has no dates (XYZ, GeoTIFF and others)


## [1.0.0-rc1] - 2026-11-17

### Added

- Export of survey-related records to GeoNode
- Thumbnails for projects and survey missions, drawn over the base map and shown on listing cards, regenerated when their spatial extent changes
- Implicit CRS of survey missions can be set in the UI and is validated. New survey missions default to EPSG:32629
- Extraction of coordinates and extents from SEG-Y headers, with track previews built from sampled trace positions
- Previews for more dataset formats; preview eligibility is now part of the asset discovery configuration and can be toggled in its form
- Records created or edited by hand now go through the discovery pipeline, which fills in the metadata extracted from their data files
- Metadata extracted by discovery is stored in a dedicated field and shown on the record detail page
- Discovery can be canceled, recovers from dead workers, reports its progress and asks for confirmation before starting
- Discovery publishes the valid records it creates at the end of a run
- Route serving the list of download links of a resource, for bulk downloads
- Aggregated information on the detail pages of projects and survey missions
- Full asset paths are shown on the record detail page
- Missing filters on the listing pages
- Initial version of the user guide, with the Portuguese version downloadable as PDF
- All UI texts are now translatable, with Portuguese translations


### Changed

- Discovery is much faster: the archive is walked once, metadata is extracted concurrently in worker processes, records are written in batches, previews are requested in batches and point cloud files (XYZ, KML) are sampled. A run stops after a configurable time limit (`discovery_time_limit_hours`)
- Workers were reorganized: `processing-worker` is renamed to `interactive-worker`, `previews-worker` to `long-tasks-worker`, and the new `discovery-worker` runs discovery in its own queue. Database connection pools are bounded by the `db_pool_size`, `db_max_overflow` and `db_pool_timeout` settings
- Resources that are busy (e.g. under discovery, export or preview generation) cannot be modified, and the mutation buttons of a resource are disabled while any of its descendants is busy
- Projects, survey missions and records can no longer be edited or deleted from their list pages
- A description is no longer required for a resource to be valid
- Discovery no longer overwrites user-supplied record descriptions
- The project's `root_path` was removed, and the creation and editing forms were tightened up
- Improved UI of notifications, list items and modal dialogs (which now name the resource they pertain to), layout on smaller displays and harmonized map drawing colors
- Upgraded all Python dependencies to their current versions, including SQLAlchemy 2.1 and SQLModel 0.0.50
- Replaced `httpx` with its maintained successor `httpx2`; TLS verification now uses the operating system's trust store instead of `certifi`
- Upgraded GDAL to 3.12.4 (docker base image and Python bindings) and uv to 0.13.8 in the docker image
- Upgraded PostGIS to 3.7, martin to 1.16.1, dozzle to v11 and the GeoNode nginx image to 1.31.8
- Upgraded the images used by the CI deployment pipeline
- Martin no longer serves the projects, survey missions and survey-related records tables, only the PMTiles base map
- The creation timestamps of projects, survey missions and survey-related records, and the GeoNode export timestamp of records, are now stored with their time zone
- Adopted the default rule set of ruff 0.17 and fixed the code accordingly; alembic migrations and auxiliary scripts are excluded from ruff

### Fixed

- docker healthcheck for auth-db in prod and test envs now pass the correct user to `pg_isready`
- Incorrect survey mission status after discovery
- Incorrectly drawn map widgets; map zoom animation is turned off
- Incorrect pagination after deleting a resource
- Record selection checkbox not working

Upgrading from 0.6.0 requires manual steps, see "Version-specific upgrade steps" in the administration guide.


## [0.6.0] - 2026-11-01


### Added
- Discovery of pre-existing data in the archive
- Generation of previews for select datasets
- Initial version of individual dataset downloads

### Changed
- Upgraded authentik to version 2026.8.5 in all environments
- User self-registration is disabled; accounts are created by a system admin
- Removed the `seis-lab-data-catalog-admins` group and `catalog-admin` role; catalog editors can now also manage dataset categories, workflow stages and asset discovery configurations

### Fixed
- Various UI fixes
- Possible DB deadlock on the first authentik boot, which could leave the seis-lab-data application uncreated


## [0.5.0] - 2026-09-06

### Added
- Initial version of STAC API
- Initial version of archive discovery
- UI Footer
- Added more tests

### Fixed
- Multiple UI improvements and fixes
- Improve reliability of CI

### Changed
- Docs are now part of the stack


## [0.1.17] - 2026-02-17

### Added
- Added dozzle for monitoring logs

### Fixed
- Fixed wrong TLS key filenames


## [0.1.16] - 2026-02-17

### Fixed
- Added missing commit


## [0.1.15] - 2026-02-17

### Added
- TLS configuration


## [0.1.14] - 2026-02-07

### Fixed

- Fix incorrect public URL in prod deployment compose file


## [0.1.13] - 2026-02-07

### Changed

- Removed healtchcheck on auth-worker service, as it was relying on
  the bootstrap token always being valid, which was a faulty logic


## [0.1.12] - 2026-02-07

### Added

- Added production log config file

### Changed

- Tweaking woodpecker deployment to production


## [0.1.11] - 2026-02-07

### Changed

- Tweaking woodpecker deployment to production


## [0.1.10] - 2026-02-07

### Changed

- Tweaking woodpecker deployment to production


## [0.1.9] - 2026-02-07

### Changed

- Tweaking woodpecker deployment to production


## [0.1.8] - 2026-02-07

### Changed

- Tweaking woodpecker deployment to production


## [0.1.7] - 2026-02-07

### Changed

- Tweaking woodpecker deployment to production


## [0.1.6] - 2026-02-07

### Changed

- Tweaking woodpecker deployment to production


## [0.1.5] - 2026-02-07

### Changed

- Tweaking woodpecker deployment to production


## [0.1.4] - 2026-02-06

### Changed

- Tweaking woodpecker deployment to production


## [0.1.3] - 2026-02-06

### Changed

- Tweaking woodpecker deployment to production


## [0.1.2] - 2026-02-06

### Changed

- Tweaking woodpecker deployment to production


## [0.1.1] - 2026-02-06

### Changed

- Tweaking woodpecker deployment to production


## [0.1.0] - 2026-02-05

### Added

- First release, mainly for trying out the deployment workflows


[unreleased]: https://github.com/naturalgis/seis-lab-data/compare/v1.0.0-rc2...HEAD
[1.0.0-rc2]: https://github.com/naturalgis/seis-lab-data/compare/v1.0.0-rc1...v1.0.0-rc2
[1.0.0-rc1]: https://github.com/naturalgis/seis-lab-data/compare/v0.6.0...v1.0.0-rc1
[0.6.0]: https://github.com/naturalgis/seis-lab-data/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.17...v0.5.0
[0.1.17]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.16...v0.1.17
[0.1.16]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.15...v0.1.16
[0.1.15]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.14...v0.1.15
[0.1.14]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.13...v0.1.14
[0.1.13]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.12...v0.1.13
[0.1.12]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/naturalgis/seis-lab-data/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/naturalgis/seis-lab-data/tree/v0.1.0
