#!/usr/bin/env python3
"""Sign and notarize the macOS desktop app (Developer ID + Gatekeeper).

Steps:
    1. codesign the .app with "Developer ID Application" + hardened runtime
    2. rebuild the DMG from the signed .app
    3. notarize the DMG with xcrun notarytool (needs credentials, see below)
    4. staple the notarization ticket

Notarization credentials — one of:
    export NOTARY_PROFILE="AC_PASSWORD"        # keychain profile (xcrun
                                               # notarytool store-credentials)
    # or
    export APPLE_ID="you@example.com"
    export APPLE_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # app-specific password
    export APPLE_TEAM_ID="FXC38NGJH7"

Without credentials the script signs only (still kills most Gatekeeper
friction for local distribution) and says so.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP = DIST / "desktop" / "codeagent.app"

IDENTITY = "Developer ID Application: lin tong (FXC38NGJH7)"
TEAM_ID = "FXC38NGJH7"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def find_dmg() -> Path | None:
    dmgs = sorted(DIST.glob("codeagent-desktop-macos-*.dmg"))
    return dmgs[0] if dmgs else None


def sign_app() -> None:
    if not APP.is_dir():
        sys.exit(f"app not found: {APP} — run scripts/build_desktop.py first")
    run([
        "codesign", "--deep", "--force", "--timestamp",
        "--options", "runtime",  # hardened runtime, required for notarization
        "--sign", IDENTITY,
        str(APP),
    ])
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(APP)])


def rebuild_dmg() -> Path:
    old = find_dmg()
    target = old.name if old else "codeagent-desktop-macos-arm64.dmg"
    dmg = DIST / target
    with tempfile.TemporaryDirectory() as staging:
        stage = Path(staging)
        # symlinks=True is critical: the bundle seals symlinks like
        # Frameworks/Python -> Python.framework/...; dereferencing them
        # invalidates the signature.
        shutil.copytree(APP, stage / "codeagent.app", symlinks=True)
        os.symlink("/Applications", stage / "Applications")
        readme = ROOT / "scripts" / "_dmg_readme.txt"
        if readme.is_file():
            shutil.copy(readme, stage / "使用说明.txt")
        run(["hdiutil", "create", "-volname", "codeagent", "-srcfolder", str(stage),
             "-ov", "-format", "UDZO", str(dmg)])
    # sign the dmg itself too
    run(["codesign", "--force", "--timestamp", "--sign", IDENTITY, str(dmg)])
    return dmg


def notarize(dmg: Path) -> bool:
    profile = os.environ.get("NOTARY_PROFILE")
    apple_id = os.environ.get("APPLE_ID")
    password = os.environ.get("APPLE_PASSWORD")
    team = os.environ.get("APPLE_TEAM_ID", TEAM_ID)

    if profile:
        creds = ["--keychain-profile", profile]
    elif apple_id and password:
        creds = ["--apple-id", apple_id, "--password", password,
                 "--team-id", team]
    else:
        print(
            "\n未配置公证凭证，跳过 notarization（已签名，本地分发基本可用）。\n"
            "要过 Gatekeeper 完整公证，任选其一：\n"
            "  xcrun notarytool store-credentials AC_PASSWORD \\\n"
            "      --apple-id 你的AppleID --team-id FXC38NGJH7\n"
            "  然后: NOTARY_PROFILE=AC_PASSWORD python scripts/sign_macos.py\n"
            "或设置 APPLE_ID / APPLE_PASSWORD（App 专用密码）环境变量。\n"
        )
        return False

    run(["xcrun", "notarytool", "submit", str(dmg), "--wait", *creds])
    run(["xcrun", "stapler", "staple", str(dmg)])
    run(["spctl", "--assess", "--type", "open", "--verbose=2", str(dmg)])
    return True


def main() -> int:
    if sys.platform != "darwin":
        sys.exit("sign_macos.py 只能在 macOS 上运行")
    sign_app()
    dmg = rebuild_dmg()
    ok = notarize(dmg)
    print(f"\n{'✅ 已签名并公证' if ok else '✅ 已签名（未公证）'} → {dmg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
