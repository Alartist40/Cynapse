# DevAle

DevAle is a powerful Windows system utility designed for easy maintenance, optimization, and setup.

## Features

### 🚀 Tools & Utilities
- **Restore Point**: Create a system restore point with one click (auto-elevates to Admin).
- **Disk Cleanup**: Selectively clean Temp files, Prefetch, Recycle Bin, and Logs.
- **Task Manager**: Quick access to system task manager.

### 📦 App Store
- **Winget Integration**: Browse and install hundreds of apps.
- **Auto-Update Sources**: Automatically updates package sources to prevent errors.

### 💻 System Console
- **Interactive Terminal**: Type and run your own commands directly in the app.
- **Real-time Logs**: See exactly what the app is doing.
- **Smart Filtering**: Reduces spammy logs for a cleaner experience.

## Installation

### Requirements
- Windows 10 or 11
- [Winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/)

### Building Executable
```bash
python -m PyInstaller --noconfirm --onefile --windowed --add-data "commands;commands" --add-data "data;data" --name "DevAle" devale.py
```

## License
MIT License