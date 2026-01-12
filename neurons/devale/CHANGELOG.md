# Changelog

## [1.2.0] - 2025-12-11
### Added
- **Restore Point**: New tool to create system restore points (handles Admin elevation).
- **Clean Temp Dialog**: Selectable categories (Temp, Prefetch, Recycle Bin) for cleanup.
- **Interactive Console**: Type and run commands directly in the bottom console.
- **Admin Support**: App can now trigger UAC prompts for specific actions if not running as Admin.

### Changed
- **Install Logic**: Runs `winget source update` before installing to fix hash mismatches.
- **Console Log**: reducing repetitive "verification" logs.
- **UI**: Added input box to console.

## [1.1.0] - 2025-12-11
- Global Console, Resume Layout.
