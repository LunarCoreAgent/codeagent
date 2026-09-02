; codeagent 桌面版 Windows 安装程序（Inno Setup 6）
; 用法（在仓库根目录、已产出 dist\desktop\codeagent.exe 后）：
;   iscc /DMyAppVersion=0.24.0 packaging\windows-setup.iss

#ifndef MyAppVersion
#define MyAppVersion "0.24.0"
#endif
#define MyAppName "codeagent"
#define MyAppPublisher "codeagent"
#define MyAppExeName "codeagent.exe"

[Setup]
AppId={{A7C3E1D0-9B24-4F11-9E8A-C0DEA6E17001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=codeagent-desktop-windows-amd64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
MinVersion=10.0
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\desktop\codeagent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "win-readme.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch codeagent"; Flags: nowait postinstall skipifsilent
