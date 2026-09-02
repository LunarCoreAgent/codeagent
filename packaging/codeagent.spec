# PyInstaller spec for the codeagent single-file CLI binary.
#
# Bundled: core + anthropic/openai SDKs + MCP client + edge-tts voices.
# Excluded: heavy native extras (Whisper ASR, Playwright scraping, EasyOCR) —
# they are lazily imported at runtime and report clean install hints when
# missing, so the binary stays small and builds fast.

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("codeagent")
    + collect_submodules("mcp")
    + collect_submodules("edge_tts")
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
    ["entry.py"],
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
    console=True,
    icon="icon.ico" if sys.platform == "win32" else None,
)
