"""PyInstaller entry point for the codeagent desktop (windowed) app."""

from codeagent.desktop import run_desktop

if __name__ == "__main__":
    raise SystemExit(run_desktop())
