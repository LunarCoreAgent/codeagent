# CodeCoreAgent Windows 封装配置说明（v0.76.0）

在 **Windows 10/11 x64** 上把本工程打成桌面安装包。macOS 无法直接产出 `.exe`。

## 产物

| 文件 | 说明 |
|------|------|
| `dist/codeagent-desktop-windows-amd64-setup.exe` | Inno Setup 安装向导 |
| `dist/codeagent-desktop-windows-amd64.zip` | 便携包（`codeagent.exe` + README） |

## 版本号须一致

版本号来源：**`pyproject.toml` 的 `version = "0.76.0"`**。以下位置须一致：

| 位置 | 值 |
|------|-----|
| `pyproject.toml` | `0.76.0` |
| `src/codeagent/__init__.py` | `__version__ = "0.76.0"` |
| `src/codeagent/releases.py` | `Release("0.76.0", ...)` |
| `CHANGELOG.md` | `## 0.76.0` |
| `packaging/codeagent-desktop.spec` | `CFBundleShortVersionString: "0.76.0"`（macOS） |
| `packaging/windows-setup.iss` | `#define MyAppVersion "0.76.0"`（`build_desktop.py` 会用 `/DMyAppVersion=` 覆盖） |

## 本机依赖

1. Python 3.12（勾选 Add to PATH）
2. [Inno Setup 6](https://jrsoftware.org/isinfo.php)（或 `choco install innosetup -y`）
3. 可选：Git

## 一键构建

```bat
cd codeagent
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e ".[anthropic,openai,mcp,voice,desktop,packaging]"
python scripts\build_desktop.py
```

手动 Inno（若脚本未找到 iscc）：

```bat
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=0.76.0 /Fcodeagent-desktop-windows-amd64-setup packaging\windows-setup.iss
```

## 验收

1. 双击 `*-setup.exe` 能走完向导。
2. 开始菜单出现 CodeCoreAgent；启动为窗口应用，无黑色控制台。
3. 设置页可见版本 **0.76.0**；融合技能含鸿蒙相关项（harmony-next / arkts / deveco-mcp）。
4. 不要把 `.venv`、API Key、用户目录 `\.codeagent` 打进安装包。

## 0.76.0 相对上一版

- 融合鸿蒙 AI 开发：`harmony-next`、`arkts-syntax-assistant`、`deveco-mcp` 技能
- MCP 预设 `deveco_mcp()`（`npx -y deveco-mcp-server`）
