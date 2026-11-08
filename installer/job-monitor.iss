; Windows-Installer (Inno Setup 6): Job-Monitor-Windows-Setup.exe
; Gebaut in .github/workflows/build.yml:  iscc /DAppVersion=1.4.1 installer\job-monitor.iss
;
; - Ohne Admin-Rechte: installiert nach %LOCALAPPDATA%\Programs\Job-Monitor (dort darf die App sich selbst
;   aktualisieren, siehe jobmonitor/selbstupdate.py).
; - Startmenü-Eintrag „Job-Monitor“ – derselbe Pfad, den die App beim Start selbst pflegt (app_start.startmenue).
; - Die Deinstallationsdateien liegen außerhalb des Programmordners, weil das Update mit einem Klick diesen Ordner
;   komplett austauscht.
; - Daten (Dokumente\Job-Monitor) fasst weder Installation noch Deinstallation an.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{5C2B7E0A-3F6D-4B8E-9A41-7D2E6C1B9F30}
AppName=Job-Monitor
AppVersion={#AppVersion}
AppVerName=Job-Monitor {#AppVersion}
AppPublisher=Job-Monitor (Open Source)
AppPublisherURL=https://emanuelajumobi-ux.github.io/jobmonitor/
AppSupportURL=https://github.com/emanuelajumobi-ux/jobmonitor/issues
DefaultDirName={localappdata}\Programs\Job-Monitor
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UninstallFilesDir={localappdata}\Programs\Job-Monitor Deinstallation
UninstallDisplayIcon={app}\Job-Monitor.exe
UninstallDisplayName=Job-Monitor
OutputDir=..
OutputBaseFilename=Job-Monitor-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktop"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Job-Monitor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; neue Version: alten Programmordner vorher leeren, damit keine veralteten Dateien liegen bleiben
Type: filesandordirs; Name: "{app}\*"

[Icons]
Name: "{autoprograms}\Job-Monitor"; Filename: "{app}\Job-Monitor.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Job-Monitor"; Filename: "{app}\Job-Monitor.exe"; WorkingDir: "{app}"; Tasks: desktop

[Run]
Filename: "{app}\Job-Monitor.exe"; Description: "{cm:LaunchProgram,Job-Monitor}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; vom Update mit einem Klick angelegte Reste neben dem Programmordner
Type: filesandordirs; Name: "{localappdata}\Programs\.job-monitor-update"
Type: filesandordirs; Name: "{localappdata}\Programs\Job-Monitor.alt"
