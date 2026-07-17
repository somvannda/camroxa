; Camxora desktop installer (Inno Setup 6+)
; Builds a Windows installer that:
;  - installs the PyInstaller dist\Camxora folder
;  - installs Visual C++ Redistributable silently
;  - includes bundled FFmpeg next to Camxora.exe
;
; Prerequisites:
;   1. .\scripts\build-desktop.ps1 -Environment sandbox|production
;   2. .\scripts\prepare-installer-assets.ps1
;   3. ISCC.exe Camxora.iss

#define MyAppName "Camxora"
#ifdef CamxoraVersion
  #define MyAppVersion CamxoraVersion
#else
  #define MyAppVersion "0.2.0"
#endif
#define MyAppPublisher "Camxora"
#define MyAppExeName "Camxora.exe"
#ifndef CamxoraDistDir
  #define CamxoraDistDir "..\dist\Camxora"
#endif
#ifndef CamxoraVendorDir
  #define CamxoraVendorDir "..\vendor"
#endif

[Setup]
AppId={{A7C2E8D1-4F19-4B6A-9C31-CAMXORA2026}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=CamxoraSetup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile={#CamxoraDistDir}\_internal\resources\app-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartIfNeededByRun=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Full PyInstaller onedir bundle
Source: "{#CamxoraDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Bundled FFmpeg (ffmpeg.exe + ffprobe.exe) — also copied by build script into dist
Source: "{#CamxoraVendorDir}\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion skipifsourcedoesntexist
; VC++ redistributable bootstrapper (installed silently in [Run])
Source: "{#CamxoraVendorDir}\vcredist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Install VC++ runtime quietly when present (safe no-op if already installed)
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Visual C++ Redistributable…"; Flags: waituntilterminated skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
