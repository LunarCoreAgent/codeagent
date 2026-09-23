"""Official Node.js runtime fused into the desktop install.

Binaries are the Node.js project's release builds
(https://github.com/nodejs/node), downloaded from https://nodejs.org/dist/.
Active LTS pinned here: 24.21.0 (Krypton). The app prefers this copy over
whatever ``node`` happens to be on PATH, so ``npx`` MCP servers work when
the machine has no separate Node.js install.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

NODE_VERSION = "24.21.0"
NODE_DIST = f"https://nodejs.org/dist/v{NODE_VERSION}"
_LAUNCHERS = {"node", "npm", "npx"}


def archive_name(system: str | None = None, machine: str | None = None) -> str:
    """Official archive filename for this OS and CPU."""
    system = system or sys.platform
    machine = (machine or platform.machine()).lower()
    arm = machine in {"arm64", "aarch64"}
    if system == "darwin":
        arch = "arm64" if arm else "x64"
        return f"node-v{NODE_VERSION}-darwin-{arch}.tar.gz"
    if system == "win32":
        arch = "arm64" if arm else "x64"
        return f"node-v{NODE_VERSION}-win-{arch}.zip"
    arch = "arm64" if arm else "x64"
    return f"node-v{NODE_VERSION}-linux-{arch}.tar.xz"


def user_runtime_dir() -> Path:
    return Path.home() / ".codeagent" / "runtime" / "node"


def _vendor_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "packaging" / "vendor" / "node"


def _bundle_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable)
    if sys.platform == "darwin":
        return exe.parent.parent / "Resources" / "node"
    return exe.parent / "node"


def bindir(root: Path) -> Path | None:
    root = Path(root)
    unix = root / "bin" / "node"
    if unix.is_file():
        return root / "bin"
    if (root / "node.exe").is_file() or (root / "node").is_file():
        return root
    return None


def _tool(root: Path, name: str) -> Path | None:
    folder = bindir(root)
    if folder is None:
        return None
    names = [name]
    if sys.platform == "win32":
        names = [f"{name}.cmd", f"{name}.exe", name]
    for candidate in names:
        path = folder / candidate
        if path.is_file():
            return path
    return None


def _ready(root: Path) -> bool:
    return _tool(root, "node") is not None


def locate() -> Path | None:
    """Directory of the fused Node.js tree, if one is already present."""
    for root in (_bundle_dir(), _vendor_dir(), user_runtime_dir()):
        if root is not None and _ready(root):
            return root
    return None


def node_exe() -> Path | None:
    root = locate()
    return _tool(root, "node") if root else None


def npx_exe() -> Path | None:
    root = locate()
    return _tool(root, "npx") if root else None


def path_prefix() -> str:
    root = locate()
    folder = bindir(root) if root else None
    return str(folder) if folder else ""


def augment_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Environment with the fused Node ``bin`` directory first on PATH."""
    env = dict(os.environ)
    if base:
        env.update({str(k): str(v) for k, v in base.items()})
    prefix = path_prefix()
    if prefix:
        env["PATH"] = prefix + os.pathsep + env.get("PATH", "")
    return env


def resolve_launcher(command: str) -> str:
    """Rewrite bare node/npm/npx to the fused binary when it exists."""
    leaf = Path(command).name.lower()
    if leaf.endswith(".cmd") or leaf.endswith(".exe"):
        leaf = leaf.rsplit(".", 1)[0]
    if leaf not in _LAUNCHERS:
        return command
    root = locate()
    if root is None:
        return command
    found = _tool(root, leaf)
    return str(found) if found else command


def _urlopen(url: str, timeout: int):
    """Open an HTTPS URL, using certifi when the system trust store is empty."""
    import ssl

    context = ssl.create_default_context()
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    return urllib.request.urlopen(url, timeout=timeout, context=context)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_sha(name: str, timeout: int) -> str:
    url = f"{NODE_DIST}/SHASUMS256.txt"
    with _urlopen(url, timeout) as response:
        text = response.read().decode("utf-8", "replace")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        digest, fname = parts
        if fname.replace("./", "") == name:
            return digest
    raise RuntimeError(f"SHASUMS256.txt has no entry for {name}")


def _extract(archive: Path, dest: Path) -> None:
    staging = Path(tempfile.mkdtemp(prefix="cca-node-"))
    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(staging)
        else:
            with tarfile.open(archive) as packed:
                packed.extractall(staging, filter="data")
        children = [p for p in staging.iterdir() if p.name != ".DS_Store"]
        source = children[0] if len(children) == 1 and children[0].is_dir() else staging
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(source), str(dest))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def ensure_installed(dest: Path | None = None, *, timeout: int = 180) -> Path:
    """Return a Node.js tree, downloading the official LTS build if needed.

    ``dest`` is the install directory used by the desktop packager.
    With ``dest`` omitted, an already fused copy is reused; otherwise the
    runtime is installed under ``~/.codeagent/runtime/node``.
    """
    if dest is None:
        found = locate()
        if found is not None:
            return found
        dest = user_runtime_dir()
    else:
        dest = Path(dest)
        if _ready(dest):
            return dest

    name = archive_name()
    url = f"{NODE_DIST}/{name}"
    expected = _expected_sha(name, timeout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_name = tempfile.mkstemp(prefix="cca-node-", suffix=Path(name).suffix)
    os.close(fd)
    archive = Path(raw_name)
    try:
        with _urlopen(url, timeout) as response, archive.open("wb") as out:
            shutil.copyfileobj(response, out)
        actual = _sha256(archive)
        if actual != expected:
            raise RuntimeError(
                f"Node.js {NODE_VERSION} checksum mismatch for {name}"
            )
        _extract(archive, dest)
    finally:
        archive.unlink(missing_ok=True)
    if not _ready(dest):
        raise RuntimeError(f"Node.js extracted but node binary missing in {dest}")
    return dest
