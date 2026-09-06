# PyInstaller spec for the codeagent desktop app (windowed, no console).
# Produces codeagent.app on macOS and a windowed codeagent.exe on Windows.

import sys

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("codeagent")
    + collect_submodules("mcp")
    + collect_submodules("edge_tts")
    + collect_submodules("webview")
)

excludes = [
    "faster_whisper", "whisper", "ctranslate2",
    "sounddevice", "soundfile",
    "playwright", "patchright", "scrapling", "curl_cffi",
    "easyocr", "torch", "torchaudio", "torchvision",
    "opuslib", "websockets",
    "pytest", "pytest_asyncio",
]

a = Analysis(
    ["entry_desktop.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    # onedir: every dylib is a real file inside the .app, so codesign --deep
    # re-signs them all under one Team ID. onefile would extract a
    # differently-signed Python.framework to /tmp at runtime and hardened
    # runtime kills it ("different Team IDs").
    exe = EXE(
        pyz,
        a.scripts,
        exclude_binaries=True,
        name="codeagent",
        debug=False,
        strip=False,
        upx=False,
        console=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="codeagent")
    app = BUNDLE(
        coll,
        name="CodeCoreAgent.app",
        icon="icon.icns",
        bundle_identifier="com.codeagent.desktop",
        info_plist={
            "CFBundleName": "CodeCoreAgent",
            "CFBundleDisplayName": "CodeCoreAgent",
            "CFBundleShortVersionString": "0.34.0",
            "NSHighResolutionCapable": True,
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="codeagent",
        debug=False,
        strip=False,
        upx=False,
        console=False,  # windowed: no terminal
        icon="icon.ico",
    )
