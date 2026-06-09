; Inno Setup 6 — Promed Messagerie
; Compile with: ISCC.exe setup.iss
; Output: installer\output\PromedMessagerie_Setup.exe
;
; Pour une nouvelle release :
;   1. Incrémenter AppVersion ci-dessous (ex: "1.0.1")
;   2. Incrémenter APP_VERSION dans python\version.py (même valeur)
;   3. Recompiler avec PyInstaller puis ISCC.exe
;   4. Publier PromedMessagerie_Setup.exe sur GitHub Releases avec le tag vX.Y.Z

#define AppName      "Promed Messagerie"
#define AppVersion   "5.0.0"
#define AppPublisher "Promed"
#define AppExe       "PromedMessagerie.exe"
#define SourceDir    "..\python\dist\PromedMessagerie"

[Setup]
AppId={{A3F7C201-4E8B-4D2A-9B1F-7E3C52A80D14}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL=
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
; Install for the current user only (no admin needed)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Ferme l'application si elle tourne lors d'une mise à jour silencieuse
CloseApplications=yes
RestartApplications=no
#define IconPath "..\python\ressources\icone_msg.ico"
#if FileExists(IconPath)
SetupIconFile={#IconPath}
#endif
OutputDir=output
OutputBaseFilename=PromedMessagerie_Setup_{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
MinVersion=10.0
UninstallDisplayIcon={app}\icone_msg.ico

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
; Copy the entire PyInstaller one-folder output
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Application icon
Source: "..\python\ressources\icone_msg.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\icone_msg.ico"
Name: "{group}\Désinstaller {#AppName}"; Filename: "{uninstallexe}"
; Desktop (optional, controlled by task above)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\icone_msg.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent
