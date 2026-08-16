; Instalador Windows do Tube Fetch Desktop — gerado pelo workflow .github/workflows/build-windows.yml
; (runner windows-latest, ISCC.exe via Chocolatey). Não requer Inno Setup instalado localmente
; a menos que você queira gerar o instalador manualmente.
;
; Uso manual (Windows, com Inno Setup 6 instalado):
;   iscc packaging\installer.iss /DAPP_VERSION=1.0.0
;
; Espera que "pyinstaller packaging\tube-fetch-desktop.spec" já tenha rodado (dist\TubeFetchDesktop\).

#ifndef APP_VERSION
  #define APP_VERSION "0.0.0-dev"
#endif

#define MyAppName "Tube Fetch Desktop"
#define MyAppExeName "TubeFetchDesktop.exe"
#define MyAppPublisher "Cleverson Rodrigues"

[Setup]
AppId={{85C25910-EF64-4245-89FB-0C374499E6F6}
AppName={#MyAppName}
AppVersion={#APP_VERSION}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\TubeFetchDesktop
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=TubeFetchDesktop-Setup-{#APP_VERSION}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
SourceDir={#SourcePath}\..

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\TubeFetchDesktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} agora"; Flags: nowait postinstall skipifsilent
