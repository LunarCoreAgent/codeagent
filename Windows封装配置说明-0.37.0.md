# CodeCoreAgent Windows 封装配置说明（v0.37.0）

本文档说明如何用仓库内的配置在 **Windows 10/11 x64** 机器上把 CodeCoreAgent 桌面版
封装成安装程序（`*-setup.exe`）和便携包（`*.zip`），以及版本号与版本信息如何保持同步。

---

## 1. 产出的文件（放在 `dist/` 下）

| 文件 | 说明 |
|------|------|
| `codeagent-desktop-windows-amd64-setup.exe` | Inno Setup 安装向导（正式安装程序） |
| `codeagent-desktop-windows-amd64.zip` | 便携包（内含 `codeagent.exe` + `README.txt`） |
| `dist/desktop/codeagent.exe` | PyInstaller 产出的 windowed 可执行文件（中间产物） |

## 2. 一键构建（推荐）

在仓库根目录，用 Python 3.12 虚拟环境：

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e ".[anthropic,openai,mcp,voice,desktop,packaging]"
python scripts\build_desktop.py
```

`scripts/build_desktop.py` 会自动：
1. 调 PyInstaller 按 `packaging/codeagent-desktop.spec` 编译 `codeagent.exe`（windowed，无控制台）；
2. 打 zip 便携包 `codeagent-desktop-windows-amd64.zip`；
3. 若检测到 Inno Setup 6（`iscc` 在 PATH，或 `%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe`），
   再按 `packaging/windows-setup.iss` 编译 `codeagent-desktop-windows-amd64-setup.exe`。

没有 Inno Setup 时脚本会跳过 Setup.exe（只出 zip），可用：
```bat
choco install innosetup -y --no-progress
```

## 3. 各配置文件的作用

| 文件 | 作用 |
|------|------|
| `packaging/codeagent-desktop.spec` | PyInstaller 桌面 spec：windowed exe；`icon="icon.ico"`（Windows）/ `icon.icns`（macOS）；macOS 的 `CFBundleShortVersionString` 在这里 |
| `packaging/codeagent.spec` | PyInstaller CLI spec（可选，桌面版不需要） |
| `packaging/entry_desktop.py` | 桌面入口脚本（spec 的入口） |
| `packaging/icon.ico` | 安装程序 / exe 图标（由 `make_icon.py` 从 `logo-art.png` 生成） |
| `packaging/windows-setup.iss` | Inno Setup 6 脚本：安装目录、开始菜单、桌面快捷方式、卸载、`SetupIconFile=icon.ico`；`MyAppVersion` 默认值在这里 |
| `packaging/win-readme.txt` | 打进安装目录的 `README.txt` |
| `packaging/logo-art.png` | 标志母版（唯一 logo 源图，改 logo 只改它） |
| `packaging/make_icon.py` | 从 `logo-art.png` 生成 `icon.png`/`icon.icns`/`icon.ico`/`mark.png` + 侧栏 `brand_mark.py` |
| `scripts/build_desktop.py` | 一键构建脚本（读 `pyproject.toml` 的 version） |

## 4. 版本号与版本信息必须同步（重要）

版本号只有一处来源：**`pyproject.toml` 的 `version = "0.37.0"`**。
以下位置都必须与它一致，否则打包出来的版本信息会错位：

| 位置 | 当前值 | 改版时要改 |
|------|--------|-----------|
| `pyproject.toml` | `0.37.0` | ✅ 唯一来源，先改这里 |
| `src/codeagent/__init__.py` | `__version__ = "0.37.0"` | ✅ |
| `src/codeagent/releases.py` | `Release("0.37.0", "2026-09-09", ...)` | ✅ 版本信息/更新记录 |
| `CHANGELOG.md` | `## 0.37.0（2026-09-09）` | ✅ 更新说明 |
| `packaging/codeagent-desktop.spec` | `CFBundleShortVersionString: "0.37.0"` | ✅ macOS App 版本号 |
| `packaging/windows-setup.iss` | `#define MyAppVersion "0.37.0"` | ✅ Windows 安装程序版本号（`build_desktop.py` 会用 `/DMyAppVersion=` 覆盖，但默认值也要一致） |

> 版本同步自检命令：
> ```bat
> grep -n "0.3x.0" pyproject.toml src\codeagent\__init__.py src\codeagent\releases.py CHANGELOG.md packaging\codeagent-desktop.spec packaging\windows-setup.iss
> ```

## 5. 更新 logo 的流程

logo 只有一处源图：`packaging/logo-art.png`。改它之后跑：

```bat
python packaging\make_icon.py
```

会自动重生成 `icon.png` / `icon.icns` / `icon.ico` / `mark.png`，
并重写 `src/codeagent/desktop/brand_mark.py`（桌面侧栏/聊天页 logo 数据 URI）。
然后重新跑 `scripts\build_desktop.py` 打包即可。

## 6. 手动编译 Setup.exe（可选）

```bat
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=0.37.0 /Fcodeagent-desktop-windows-amd64-setup packaging\windows-setup.iss
```

## 7. 本 zip 内已含的必需文件

源码 `src/`、`pyproject.toml`、`uv.lock`、`packaging/`、`scripts/`、`README.md`、`CHANGELOG.md`、
`LICENSE`、`PRIVACY.md` 均已打包，按第 2 节即可在 Windows 上构建。
