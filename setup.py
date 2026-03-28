"""py2app build script for Claude Usage menu bar app."""

from setuptools import setup

APP = ["claude_usage.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,  # Important: must be False on modern macOS
    "plist": {
        "CFBundleName": "Claude Usage",
        "CFBundleDisplayName": "Claude Usage",
        "CFBundleIdentifier": "com.claude.menubar-usage",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,  # Hide from Dock — menu bar only
        "NSHumanReadableCopyright": "MIT License",
    },
    "packages": ["requests", "rookiepy", "rumps"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
