; Campus Pilot — instalador de Windows (Inno Setup 6)
; Lo construye dev/lib/native-packaging/build-desktop-ci.sh (Docker + Wine), que lee
; AppName/AppExeName de aquí.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "Campus Pilot"
#define AppPublisher "Andrea Osma Rafael"
#define AppExeName "Campus Pilot.exe"
#define BundleDir "..\backend\dist\Campus Pilot"
#define OutputDir "out"

[Setup]
AppId={{5C1E7A2B-9D34-4F6A-8B1C-2E7D9F0A4B63}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=CampusPilotSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; Los datos (%LOCALAPPDATA%\Campus Pilot\data) nunca se borran al desinstalar.
