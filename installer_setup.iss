; Script Inno Setup pour HADJ NO-TOUCH OFFLINE AI
; Génère l'installateur Windows autonome HADJ_NoTouch_Setup.exe

#define MyAppName "HADJ NO-TOUCH OFFLINE AI"
#define MyAppVersion "3.2.1"
#define MyAppPublisher "HADJ Open Source Project"
#define MyAppURL "http://127.0.0.1:8000"
#define MyAppExeName "HADJ_NoTouch.exe"

[Setup]
AppId={{D37B4A23-6B11-4E89-B4A1-9876543210AB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Per-user install: the app writes its settings, logs and token next to its
; own files, which Program Files would refuse without admin rights.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=HADJ_NoTouch_Setup_v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=resources\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Démarrer automatiquement HADJ NO-TOUCH à l'ouverture de session Windows"; GroupDescription: "Options d'automatisation:"; Flags: unchecked

[Files]
Source: "dist\HADJ_NoTouch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "HadjNoTouchAI"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
