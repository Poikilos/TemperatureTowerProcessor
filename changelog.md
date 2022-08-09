# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [git] - 2022-08-07
### Added
- Load settings on GUI start.
- Switch to "Smart compact temperature calibration tower" by gaaZolee and Poikilos (no longer use 3dMakernoob's "Temperature Tower Generic" by default).

## Changed
- Rename some functions.
- Change the base of the new tower to a large rectangle as a heat shield for a more consistent comparison between layers.

### Fixed
- Cast types correctly (allows getVar to work).


## [git] - 2019-12-27
### Added
- Create a quality script that calls pycodestyle-3 and outputinspector (for Linux; only affects development).

### Changed
- Conform code style to PEP8.


## [git] - 2019-12-27
### Changed
- Write "settings descriptions.txt" on first run.
- Always generate settings.json (even if operation cannot continue).
- Show percentage complete in console and GUI.


## [git] - 2019-12-26
### Changed
- Move functionality to a separate module (gcodefollower.py) so that CLI and GUI versions can be maintained while retaining the same functionality and most code.


## [git] - 2019-12-26
### Changed
- Detect height changes from G0 commands.
- Ensure that first temperature is not skipped.
- Improve GUI messages.
- Load default path in GUI automatically.
