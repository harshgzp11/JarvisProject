[Setup]
AppName=Jarvis OS Assistant
AppVersion=1.0.0
DefaultDirName={autopf}\JarvisOSAssistant
DefaultGroupName=Jarvis OS Assistant
OutputDir=installer_output
OutputBaseFilename=JarvisSetup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Jarvis-win32-x64\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Jarvis OS Assistant"; Filename: "{app}\Jarvis.exe"
Name: "{autodesktop}\Jarvis OS Assistant"; Filename: "{app}\Jarvis.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Jarvis.exe"; Description: "{cm:LaunchProgram,Jarvis OS Assistant}"; Flags: nowait postinstall skipifsilent
