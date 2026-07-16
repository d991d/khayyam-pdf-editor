; installer.iss — Inno Setup script for Khayyam PDF Editor (Windows)
;
; Prerequisites:
;   1. Run  build.bat  first to produce  dist\Khayyam PDF Editor\
;   2. Install Inno Setup 6: https://jrsoftware.org/isinfo.php
;   3. Compile this script with Inno Setup Compiler (ISCC.exe)
;      or open it in the Inno Setup IDE and press Ctrl+F9
;
; Output: installer\Khayyam-PDF-Editor-Setup-1.1.exe

#define AppName      "Khayyam PDF Editor"
#define AppVersion   "1.1"
#define AppPublisher "d991d"
#define AppURL       "https://d991d.com/khayyam-pdf-editor/"
#define AppExeName   "Khayyam PDF Editor.exe"
#define AppId        "{{A3F8C2D1-7E4B-4F9A-8C3E-2B5D6A1F0E9C}"

; ── [Setup] ───────────────────────────────────────────────────────────────────
[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL=https://d991d.com/support
AppUpdatesURL={#AppURL}
AppCopyright=Copyright (C) 2026 d991d

; Install to Program Files by default (auto-detects x86 vs x64)
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}

; Output
OutputDir=installer
OutputBaseFilename=Khayyam-PDF-Editor-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Appearance
WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=no

; Require admin only if installing to Program Files
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Misc
ChangesAssociations=yes
AllowNoIcons=yes
ShowLanguageDialog=auto
MinVersion=10.0

; ── [Languages] ───────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── [Tasks] ───────────────────────────────────────────────────────────────────
[Tasks]
; Desktop shortcut is opt-in (unchecked by default)
Name: "desktopicon";   Description: "{cm:CreateDesktopIcon}";   GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; .pdf association is opt-in
Name: "pdfassoc";      Description: "Open PDF files with {#AppName}";                                     GroupDescription: "File associations:"; Flags: unchecked

; ── [Files] ───────────────────────────────────────────────────────────────────
[Files]
; Main app bundle (built by PyInstaller into dist\Khayyam PDF Editor\)
Source: "dist\Khayyam PDF Editor\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; ── [Icons] ───────────────────────────────────────────────────────────────────
[Icons]
; Start Menu
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; \
    WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional task)
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; \
    WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\{#AppExeName}"

; ── [Registry] ────────────────────────────────────────────────────────────────
[Registry]
; Register the app so it appears in "Open With" for .pdf files
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}"; \
    ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; \
    Flags: uninsdeletekey

Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\shell\open\command"; \
    ValueType: string; ValueName: ""; \
    ValueData: """{app}\{#AppExeName}"" ""%1"""; \
    Flags: uninsdeletevalue

Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\SupportedTypes"; \
    ValueType: string; ValueName: ".pdf"; ValueData: ""; \
    Flags: uninsdeletekey

; .pdf default association (only if the user opted in)
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; \
    ValueType: string; ValueName: "KhayyamPDFEditor.Document"; ValueData: ""; \
    Flags: uninsdeletevalue; Tasks: pdfassoc

Root: HKA; Subkey: "Software\Classes\KhayyamPDFEditor.Document"; \
    ValueType: string; ValueName: ""; ValueData: "PDF Document"; \
    Flags: uninsdeletekey; Tasks: pdfassoc

Root: HKA; Subkey: "Software\Classes\KhayyamPDFEditor.Document\DefaultIcon"; \
    ValueType: string; ValueName: ""; \
    ValueData: "{app}\{#AppExeName},0"; \
    Flags: uninsdeletekey; Tasks: pdfassoc

Root: HKA; Subkey: "Software\Classes\KhayyamPDFEditor.Document\shell\open\command"; \
    ValueType: string; ValueName: ""; \
    ValueData: """{app}\{#AppExeName}"" ""%1"""; \
    Flags: uninsdeletekey; Tasks: pdfassoc

; ── [Run] (post-install options) ──────────────────────────────────────────────
[Run]
Filename: "{app}\{#AppExeName}"; \
    Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent; \
    WorkingDir: "{app}"

; ── [UninstallDelete] ─────────────────────────────────────────────────────────
[UninstallDelete]
; Clean up any .pyc cache files written at runtime
Type: filesandordirs; Name: "{app}\src\__pycache__"
Type: filesandordirs; Name: "{app}\src\dialogs\__pycache__"

; ── [Code] — wizard customisations ────────────────────────────────────────────
[Code]
// Notify Windows shell of file association changes after install/uninstall
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RegWriteStringValue(HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice',
      '', '');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteKeyIfEmpty(HKEY_CURRENT_USER,
      'Software\Classes\KhayyamPDFEditor.Document');
end;
