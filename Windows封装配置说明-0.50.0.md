# CodeCoreAgent Windows 封装配置说明（v0.50.0）

本文档说明如何在 **Windows 10/11 x64** 上把桌面版封装成安装程序
（`*-setup.exe`）和便携包（`*.zip`）。macOS 打不出 Windows `.exe`，必须在 Windows 上构建。

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

或从 https://jrsoftware.org/isinfo.php 安装 Inno Setup 6。

## 3. 各配置文件的作用

| 文件 | 作用 |
|------|------|
| `packaging/codeagent-desktop.spec` | PyInstaller 桌面 spec：windowed exe；Windows 用 `icon.ico` |
| `packaging/entry_desktop.py` | 桌面入口脚本（spec 的入口） |
| `packaging/icon.ico` | 安装程序 / exe 图标 |
| `packaging/windows-setup.iss` | Inno Setup 6：安装目录、开始菜单、桌面快捷方式、卸载 |
| `packaging/win-readme.txt` | 打进安装目录的 `README.txt` |
| `packaging/logo-art.png` | 标志母版（改 logo 只改它） |
| `packaging/make_icon.py` | 从 `logo-art.png` 生成各尺寸图标 |
| `scripts/build_desktop.py` | 一键构建（读 `pyproject.toml` 的 version） |
| `packaging/CHATGPT_WINDOWS_BUILD.md` | 交给 Windows 上 AI 助手的构建任务说明 |

## 4. 版本号必须同步

版本号来源：**`pyproject.toml` 的 `version = "0.50.0"`**。以下位置须一致：

| 位置 | 当前值 |
|------|--------|
| `pyproject.toml` | `0.50.0` |
| `src/codeagent/__init__.py` | `__version__ = "0.50.0"` |
| `src/codeagent/releases.py` | `Release("0.50.0", ...)` |
| `CHANGELOG.md` | `## 0.50.0（2026-09-10）` |
| `packaging/codeagent-desktop.spec` | `CFBundleShortVersionString: "0.50.0"`（macOS） |
| `packaging/windows-setup.iss` | `#define MyAppVersion "0.50.0"`（`build_desktop.py` 会用 `/DMyAppVersion=` 覆盖） |

## 5. 更新 logo

```bat
python packaging\make_icon.py
python scripts\build_desktop.py
```

## 6. 手动编译 Setup.exe（可选）

先有 `dist\desktop\codeagent.exe` 之后：

```bat
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=0.50.0 /Fcodeagent-desktop-windows-amd64-setup packaging\windows-setup.iss
```

## 7. 验收

1. 双击 `*-setup.exe` 能走完向导。
2. 开始菜单出现 CodeCoreAgent；可选桌面快捷方式。
3. 启动后是窗口应用，**不要弹出黑色控制台**。
4. 便携 zip 解压后直接运行 `codeagent.exe` 也能开窗口。
5. 不要把 API Key、`.venv`、`%USERPROFILE%\\.codeagent` 打进安装包。
6. 若安装后白屏，安装 [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。

## 8. 本 zip 内已含的必需文件

`codeagent/` 下有源码 `src/`、`pyproject.toml`、`uv.lock`、`packaging/`、`scripts/`、
`README.md`、`CHANGELOG.md`、`LICENSE`、`PRIVACY.md`。按第 2 节即可在 Windows 上构建。
