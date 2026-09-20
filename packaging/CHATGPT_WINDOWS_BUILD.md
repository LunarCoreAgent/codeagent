# 任务：为 codeagent 桌面应用生成 Windows 安装程序

你在一台 **Windows 10/11 x64** 机器上工作。不要改 macOS 打包逻辑。目标只做 Windows 安装包。

## 仓库里已经有的东西（不要推倒重来）

| 文件 | 作用 |
|------|------|
| `packaging/codeagent-desktop.spec` | PyInstaller：Windows 下产出 **windowed** `codeagent.exe` |
| `packaging/entry_desktop.py` | 桌面入口 |
| `packaging/icon.ico` | 安装程序 / exe 图标 |
| `packaging/windows-setup.iss` | Inno Setup 6 脚本 |
| `packaging/win-readme.txt` | 打进安装目录的 README |
| `scripts/build_desktop.py` | 一键：PyInstaller → zip → 若有 `iscc` 再编 Setup.exe |
| `.github/workflows/binaries.yml` | CI：Windows 装 Inno Setup 并编译 `*-setup.exe` |

macOS 安装包已经在 Mac 上打好：`dist/codeagent-desktop-macos-arm64.dmg`。不要动。

## 你要产出的文件

在仓库 `dist/` 下必须有：

1. **`codeagent-desktop-windows-amd64-setup.exe`** — Inno Setup 安装向导（正式安装程序）
2. **`codeagent-desktop-windows-amd64.zip`** — 便携包（内含 `codeagent.exe` + `README.txt`）

版本号从 `pyproject.toml` 的 `version` 读取（当前 `0.81.0`）。

## 环境

- Python 3.10+（建议 3.12）
- 管理员 PowerShell 可装 [Inno Setup 6](https://jrsoftware.org/isinfo.php)（`choco install innosetup -y`）
- 依赖：

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e ".[anthropic,openai,mcp,voice,desktop,packaging]"
```

## 构建命令（优先用这一条）

```bat
python scripts/build_desktop.py
```

成功时应打印类似：

```
OK → dist\codeagent-desktop-windows-amd64.zip (... MB)
OK → dist\codeagent-desktop-windows-amd64-setup.exe (... MB)
```

若提示 `Inno Setup (iscc) not found`：先装 Inno Setup，确认存在

`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

然后重跑 `python scripts/build_desktop.py`。也可以手动：

```bat
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=0.81.0 /Fcodeagent-desktop-windows-amd64-setup packaging\windows-setup.iss
```

## 验收

1. 双击 `*-setup.exe` 能走完向导，默认装到 `%LocalAppData%\Programs\codeagent` 或 `Program Files\codeagent`（脚本是 `{autopf}`，用户可改目录）。
2. 开始菜单出现 codeagent；可选桌面快捷方式。
3. 启动后是窗口应用，**不要弹出黑色控制台**。
4. `--version`（若入口支持）或窗口标题为 codeagent。
5. 便携 zip 解压后直接运行 `codeagent.exe` 也能开窗口。
6. 不要把 API Key、`.venv`、用户目录 `~\.codeagent` 打进安装包。

## 允许的小改动

- 若 Inno 脚本路径、`ISCC` 探测、中文语言包缺失导致编译失败，可以修 `packaging/windows-setup.iss` 或 `scripts/build_desktop.py` 的 Windows 分支。
- WebView2 运行时：若安装后白屏，在 iss 的 `[Run]` 或文档里提示安装 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。不要把整份 Edge 打进安装包。
- **不要**改 macOS spec / DMG 脚本，除非发现明显笔误。

## 完成后回复

列出 `dist\` 里两个产物的完整路径和文件大小，以及你改过的文件（如有）。
