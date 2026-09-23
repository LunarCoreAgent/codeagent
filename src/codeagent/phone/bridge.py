"""Locate hdc/adb and run install / launch / log / UI smoke commands."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_OUTPUT = 40_000

# Common install locations on macOS / Windows / Linux.
_HDC_CANDIDATES = (
    "hdc",
    str(Path.home() / "Library/OpenHarmony/Sdk/26.0.0/toolchains/hdc"),
    str(Path.home() / "Library/OpenHarmony/Sdk/12/toolchains/hdc"),
    str(Path.home() / "Library/Huawei/Sdk/toolchains/hdc"),
    str(Path.home() / "Library/DevEcoStudio/ohos-sdk/default/openharmony/toolchains/hdc"),
    str(Path.home() / "harmony-tools/ohos-sdk-12/12/toolchains/hdc"),
    "/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc",
    "/Applications/DevEco-Studio 2.app/Contents/sdk/default/openharmony/toolchains/hdc",
    r"C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe",
)

    # Adb candidate with empty username is useless on some hosts.
_ADB_CANDIDATES = (
    "adb",
    str(Path.home() / "Library/Android/sdk/platform-tools/adb"),
    str(Path.home() / "Android/Sdk/platform-tools/adb"),
)


@dataclass
class Device:
    serial: str
    backend: str  # hdc | adb
    label: str = ""
    state: str = "device"


@dataclass
class PhoneBridge:
    """One connected device + the CLI used to drive it."""

    backend: str
    exe: str
    device: Device | None = None

    def with_device(self, serial: str | None = None) -> PhoneBridge:
        devices = list_devices(self.backend, self.exe)
        if not devices:
            raise RuntimeError(
                f"没有已连接的 {self.backend.upper()} 设备。"
                "请用 USB 连接并打开开发者选项 / 调试模式。"
            )
        if serial:
            match = next((d for d in devices if d.serial == serial), None)
            if match is None:
                known = ", ".join(d.serial for d in devices)
                raise RuntimeError(f"找不到设备 {serial!r}。当前：{known}")
            pick = match
        else:
            pick = devices[0]
        return PhoneBridge(backend=self.backend, exe=self.exe, device=pick)


def detect_hdc() -> str | None:
    return _first_exe(_HDC_CANDIDATES + _sdk_glob("hdc"))


def detect_adb() -> str | None:
    return _first_exe(_ADB_CANDIDATES)


def find_bridge(prefer: str = "auto") -> PhoneBridge | None:
    """Pick hdc or adb. ``prefer``: auto | hdc | adb | harmony | android."""
    want = (prefer or "auto").strip().lower()
    if want in ("hdc", "harmony", "ohos", "鸿蒙"):
        exe = detect_hdc()
        return PhoneBridge("hdc", exe) if exe else None
    if want in ("adb", "android", "安卓"):
        exe = detect_adb()
        return PhoneBridge("adb", exe) if exe else None
    hdc = detect_hdc()
    if hdc:
        try:
            if list_devices("hdc", hdc):
                return PhoneBridge("hdc", hdc)
        except OSError:
            pass
    adb = detect_adb()
    if adb:
        try:
            if list_devices("adb", adb):
                return PhoneBridge("adb", adb)
        except OSError:
            pass
    if hdc:
        return PhoneBridge("hdc", hdc)
    if adb:
        return PhoneBridge("adb", adb)
    return None


def _sdk_glob(name: str) -> tuple[str, ...]:
    roots = [
        Path.home() / "Library/OpenHarmony/Sdk",
        Path.home() / "Library/Huawei/Sdk",
        Path.home() / "Library/DevEcoStudio",
        Path("/Applications/DevEco-Studio.app/Contents/sdk"),
        Path("/Applications/DevEco-Studio 2.app/Contents/sdk"),
    ]
    found: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob(name):
            if path.is_file() and os.access(path, os.X_OK):
                found.append(str(path))
    return tuple(found[:12])


def _first_exe(candidates: tuple[str, ...]) -> str | None:
    for raw in candidates:
        if not raw or raw.endswith(("hdc.exe",)) and "{user}" in raw:
            continue
        path = shutil.which(raw) if "/" not in raw and "\\" not in raw else raw
        if not path:
            continue
        p = Path(path)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def _run(
    args: list[str],
    timeout: float = 120.0,
    input_text: str | None = None,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, f"命令超时（{int(timeout)}s）：{' '.join(args)}"
    text = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    if len(text) > MAX_OUTPUT:
        text = text[:MAX_OUTPUT] + "\n... [truncated]"
    return proc.returncode, text.strip()


def list_devices(backend: str, exe: str) -> list[Device]:
    if backend == "hdc":
        code, text = _run([exe, "list", "targets"], timeout=20)
        if code != 0 and not text:
            return []
        devices: list[Device] = []
        for line in text.splitlines():
            serial = line.strip().split()[0] if line.strip() else ""
            if not serial or serial.lower() in {"[empty]", "empty"}:
                continue
            if serial.startswith("["):
                continue
            devices.append(Device(serial=serial, backend="hdc", label=serial))
        return devices
    code, text = _run([exe, "devices", "-l"], timeout=20)
    devices = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if state != "device":
            continue
        model = ""
        m = re.search(r"model:(\S+)", line)
        if m:
            model = m.group(1)
        devices.append(Device(serial=serial, backend="adb", label=model or serial, state=state))
    return devices


def status_text(prefer: str = "auto") -> str:
    lines: list[str] = []
    hdc = detect_hdc()
    adb = detect_adb()
    lines.append(f"hdc：{hdc or '未找到（可装 DevEco / OpenHarmony SDK toolchains）'}")
    lines.append(f"adb：{adb or '未找到（可装 Android platform-tools）'}")
    bridge = find_bridge(prefer)
    if bridge is None:
        lines.append("没有可用的手机桥。装好 hdc 或 adb 后重试。")
        return "\n".join(lines)
    try:
        devices = list_devices(bridge.backend, bridge.exe)
    except OSError as exc:
        lines.append(f"列设备失败：{exc}")
        return "\n".join(lines)
    if not devices:
        lines.append(f"{bridge.backend} 已就绪，但没有已连接设备。请插上手机并打开 USB 调试。")
    else:
        lines.append(f"当前后端：{bridge.backend}（{bridge.exe}）")
        for d in devices:
            lines.append(f"- {d.serial}" + (f" · {d.label}" if d.label and d.label != d.serial else ""))
    lines.append(
        "可用 action：status devices info install uninstall start stop "
        "screenshot log ui_dump tap swipe input shell"
    )
    return "\n".join(lines)


def _target_args(bridge: PhoneBridge) -> list[str]:
    if bridge.device is None:
        raise RuntimeError("未选择设备")
    if bridge.backend == "hdc":
        return ["-t", bridge.device.serial]
    return ["-s", bridge.device.serial]


def device_info(bridge: PhoneBridge) -> str:
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    if live.backend == "hdc":
        keys = (
            "const.product.model",
            "const.product.name",
            "const.ohos.devicetype",
            "const.build.characteristics",
            "const.ohos.apiversion",
        )
        rows = []
        for key in keys:
            code, text = _run([live.exe, *args, "shell", "param", "get", key], timeout=15)
            rows.append(f"{key}={text.strip() if code == 0 else f'err:{text}'}")
        return f"设备 {live.device.serial}（hdc）\n" + "\n".join(rows)
    props = (
        "ro.product.model",
        "ro.product.device",
        "ro.build.version.release",
        "ro.product.cpu.abi",
    )
    rows = []
    for key in props:
        code, text = _run([live.exe, *args, "shell", "getprop", key], timeout=15)
        rows.append(f"{key}={text.strip() if code == 0 else f'err:{text}'}")
    return f"设备 {live.device.serial}（adb）\n" + "\n".join(rows)


def install_package(bridge: PhoneBridge, path: str) -> str:
    pkg = Path(path).expanduser().resolve()
    if not pkg.is_file():
        return f"安装包不存在：{pkg}"
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    suffix = pkg.suffix.lower()
    if live.backend == "hdc":
        if suffix not in {".hap", ".hsp", ".app"}:
            return f"hdc 期望 .hap / .hsp / .app，收到 {suffix or '无后缀'}：{pkg}"
        code, text = _run([live.exe, *args, "install", "-r", str(pkg)], timeout=300)
        return f"exit {code}\n{text}\n已请求安装到 {live.device.serial}"
    if suffix not in {".apk", ".apks", ".aab", ".xapk"}:
        # still try — some devices accept other containers via adb
        pass
    code, text = _run([live.exe, *args, "install", "-r", str(pkg)], timeout=300)
    return f"exit {code}\n{text}\n已请求安装到 {live.device.serial}"


def uninstall_package(bridge: PhoneBridge, package: str) -> str:
    package = (package or "").strip()
    if not package:
        return "uninstall 需要 package（bundleName / applicationId）"
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    if live.backend == "hdc":
        code, text = _run(
            [live.exe, *args, "shell", "bm", "uninstall", "-n", package],
            timeout=60,
        )
    else:
        code, text = _run([live.exe, *args, "uninstall", package], timeout=60)
    return f"exit {code}\n{text}"


def start_app(
    bridge: PhoneBridge,
    package: str,
    ability: str = "EntryAbility",
    activity: str = "",
) -> str:
    package = (package or "").strip()
    if not package:
        return "start 需要 package（bundleName / applicationId）"
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    if live.backend == "hdc":
        abl = (ability or "EntryAbility").strip()
        code, text = _run(
            [live.exe, *args, "shell", "aa", "start", "-a", abl, "-b", package],
            timeout=30,
        )
        return f"exit {code}\n{text}"
    component = activity.strip() or f"{package}/.MainActivity"
    if "/" not in component:
        component = f"{package}/{component}"
    code, text = _run(
        [live.exe, *args, "shell", "am", "start", "-n", component],
        timeout=30,
    )
    return f"exit {code}\n{text}"


def stop_app(bridge: PhoneBridge, package: str) -> str:
    package = (package or "").strip()
    if not package:
        return "stop 需要 package"
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    if live.backend == "hdc":
        code, text = _run(
            [live.exe, *args, "shell", "aa", "force-stop", package],
            timeout=20,
        )
    else:
        code, text = _run(
            [live.exe, *args, "shell", "am", "force-stop", package],
            timeout=20,
        )
    return f"exit {code}\n{text}"


def screenshot(bridge: PhoneBridge, out: str = "") -> str:
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    dest = Path(out).expanduser() if out else Path.home() / ".codeagent" / "phone-shot.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if live.backend == "hdc":
        remote = "/data/local/tmp/cca_shot.jpeg"
        code1, t1 = _run(
            [live.exe, *args, "shell", "snapshot_display", "-f", remote],
            timeout=30,
        )
        code2, t2 = _run(
            [live.exe, *args, "file", "recv", remote, str(dest)],
            timeout=30,
        )
        return f"exit {code1}/{code2}\n{t1}\n{t2}\n截图：{dest}"
    remote = "/sdcard/cca_shot.png"
    code1, t1 = _run(
        [live.exe, *args, "shell", "screencap", "-p", remote],
        timeout=30,
    )
    code2, t2 = _run([live.exe, *args, "pull", remote, str(dest)], timeout=30)
    return f"exit {code1}/{code2}\n{t1}\n{t2}\n截图：{dest}"


def recent_log(bridge: PhoneBridge, lines: int = 80, package: str = "") -> str:
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    n = max(20, min(int(lines or 80), 500))
    if live.backend == "hdc":
        code, text = _run([live.exe, *args, "shell", "hilog", "-x"], timeout=25)
        rows = text.splitlines()
        if package:
            rows = [r for r in rows if package in r]
        return f"exit {code}\n" + "\n".join(rows[-n:])
    fetch = n * 3 if package else n
    code, text = _run(
        [live.exe, *args, "logcat", "-d", "-t", str(fetch)],
        timeout=25,
    )
    rows = text.splitlines()
    if package:
        rows = [r for r in rows if package in r][-n:]
    else:
        rows = rows[-n:]
    return f"exit {code}\n" + "\n".join(rows)


def ui_dump(bridge: PhoneBridge) -> str:
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    with tempfile.TemporaryDirectory(prefix="cca-phone-") as tmp:
        local = Path(tmp) / "layout.xml"
        if live.backend == "hdc":
            remote = "/data/local/tmp/cca_layout.json"
            _run([live.exe, *args, "shell", "uitest", "dumpLayout", remote], timeout=40)
            code, text = _run(
                [live.exe, *args, "file", "recv", remote, str(local)],
                timeout=30,
            )
            if local.is_file():
                body = local.read_text(encoding="utf-8", errors="replace")
                if len(body) > MAX_OUTPUT:
                    body = body[:MAX_OUTPUT] + "\n... [truncated]"
                return f"exit {code}\n{body}"
            return f"exit {code}\n{text}\n未能拉取 UI 树"
        remote = "/sdcard/cca_window_dump.xml"
        _run([live.exe, *args, "shell", "uiautomator", "dump", remote], timeout=40)
        code, text = _run([live.exe, *args, "pull", remote, str(local)], timeout=30)
        if local.is_file():
            body = local.read_text(encoding="utf-8", errors="replace")
            if len(body) > MAX_OUTPUT:
                body = body[:MAX_OUTPUT] + "\n... [truncated]"
            return f"exit {code}\n{body}"
        return f"exit {code}\n{text}\n未能拉取 UI 树"


def tap(bridge: PhoneBridge, x: int, y: int) -> str:
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    if live.backend == "hdc":
        code, text = _run(
            [live.exe, *args, "shell", "uitest", "uiInput", "click", str(x), str(y)],
            timeout=20,
        )
    else:
        code, text = _run(
            [live.exe, *args, "shell", "input", "tap", str(x), str(y)],
            timeout=20,
        )
    return f"exit {code}\n{text}"


def swipe(
    bridge: PhoneBridge,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 400,
) -> str:
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    dur = max(50, min(int(duration_ms or 400), 5000))
    if live.backend == "hdc":
        code, text = _run(
            [
                live.exe, *args, "shell", "uitest", "uiInput", "swipe",
                str(x1), str(y1), str(x2), str(y2), str(dur),
            ],
            timeout=20,
        )
    else:
        code, text = _run(
            [
                live.exe, *args, "shell", "input", "swipe",
                str(x1), str(y1), str(x2), str(y2), str(dur),
            ],
            timeout=20,
        )
    return f"exit {code}\n{text}"


def input_text(bridge: PhoneBridge, text: str) -> str:
    value = text or ""
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    if live.backend == "hdc":
        code, out = _run(
            [live.exe, *args, "shell", "uitest", "uiInput", "inputText", "0", "0", value],
            timeout=20,
        )
    else:
        escaped = value.replace(" ", "%s")
        code, out = _run(
            [live.exe, *args, "shell", "input", "text", escaped],
            timeout=20,
        )
    return f"exit {code}\n{out}"


def device_shell(bridge: PhoneBridge, command: str) -> str:
    command = (command or "").strip()
    if not command:
        return "shell 需要 command"
    live = bridge.with_device(bridge.device.serial if bridge.device else None)
    args = _target_args(live)
    code, text = _run([live.exe, *args, "shell", command], timeout=90)
    return f"exit {code}\n{text}"


def run_action(
    action: str,
    *,
    prefer: str = "auto",
    serial: str = "",
    path: str = "",
    package: str = "",
    ability: str = "EntryAbility",
    activity: str = "",
    out: str = "",
    lines: int = 80,
    x: int = 0,
    y: int = 0,
    x2: int = 0,
    y2: int = 0,
    duration_ms: int = 400,
    text: str = "",
    command: str = "",
) -> str:
    action = (action or "status").strip().lower()
    if action == "status":
        return status_text(prefer)
    bridge = find_bridge(prefer)
    if bridge is None:
        return status_text(prefer)
    if serial:
        bridge = bridge.with_device(serial)
    elif action != "devices":
        try:
            bridge = bridge.with_device()
        except RuntimeError as exc:
            if action == "devices":
                pass
            else:
                return str(exc)

    if action == "devices":
        devices = list_devices(bridge.backend, bridge.exe)
        if not devices:
            return f"{bridge.backend} 已找到，但没有已连接设备。"
        return "\n".join(
            f"{d.serial}\t{d.backend}\t{d.label or '-'}" for d in devices
        )
    if action == "info":
        return device_info(bridge)
    if action == "install":
        return install_package(bridge, path)
    if action == "uninstall":
        return uninstall_package(bridge, package)
    if action == "start":
        return start_app(bridge, package, ability=ability, activity=activity)
    if action == "stop":
        return stop_app(bridge, package)
    if action == "screenshot":
        return screenshot(bridge, out=out)
    if action == "log":
        return recent_log(bridge, lines=lines, package=package)
    if action == "ui_dump":
        return ui_dump(bridge)
    if action == "tap":
        return tap(bridge, int(x), int(y))
    if action == "swipe":
        return swipe(bridge, int(x), int(y), int(x2), int(y2), duration_ms=duration_ms)
    if action == "input":
        return input_text(bridge, text)
    if action == "shell":
        return device_shell(bridge, command)
    return (
        f"未知 action：{action}。"
        "可用：status devices info install uninstall start stop "
        "screenshot log ui_dump tap swipe input shell"
    )


def bridge_summary() -> dict[str, Any]:
    hdc = detect_hdc()
    adb = detect_adb()
    devices: list[dict[str, str]] = []
    for backend, exe in (("hdc", hdc), ("adb", adb)):
        if not exe:
            continue
        try:
            for d in list_devices(backend, exe):
                devices.append({
                    "serial": d.serial,
                    "backend": d.backend,
                    "label": d.label,
                })
        except OSError:
            continue
    return {
        "hdc": hdc or "",
        "adb": adb or "",
        "devices": devices,
    }
