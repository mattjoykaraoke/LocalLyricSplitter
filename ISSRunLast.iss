#define MyAppName "Local Lyric Splitter"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Matt Joy"
#define MyAppURL "https://github.com/mattjoykaraoke"
#define MyAppExeName "Local Lyric Splitter.exe"

[Setup]
; App Information
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Directory
; {autopf} typically points to C:\Program Files (x86) or C:\Program Files
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes

; Output Configuration
OutputDir=.\release
OutputBaseFilename=LLS_Installer_v{#MyAppVersion}
SetupIconFile=assets\LLS_Icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 1. Pull the main executable
Source: "dist\Local Lyric Splitter\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; 2. Pull every dependency, dictionary, and library from the PyInstaller dist folder
; This is critical for Pyphen's .dic files to work properly
Source: "dist\Local Lyric Splitter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 3. Include the Licenses folder for compliance
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent