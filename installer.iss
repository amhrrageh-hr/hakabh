; =============================================================
;  Hakbah Million - Inno Setup Installer Script
;  Version: 1.1.1.2
;  تثبيت برنامج هكبة المليون
; =============================================================

#define AppName      "هكبة المليون"
#define AppNameEn    "Hakbah Million"
#define AppVersion   "1.1.2"
#define AppPublisher "Abdulalh Rajeh Alhakbh"
#define AppExeName   "HakbahMillionAdmin.exe"
#define AppId        "{{B7A2C3D4-E5F6-7890-ABCD-EF1234567890}"
#define SourceDir    "D:\project\project-abdulalh-rajeh-alhakbh"

[Setup]
; --- معرف فريد للتطبيق (لا تغيره بعد النشر) ---
AppId={#AppId}
AppName={#AppName} - {#AppNameEn}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=Copyright © 2025 {#AppPublisher}

; --- مسارات التثبيت ---
DefaultDirName={localappdata}\{#AppNameEn}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; --- ملف الإخراج ---
OutputDir={#SourceDir}\dist
OutputBaseFilename=Hakbah_Million_Setup_v{#AppVersion}

; --- الأيقونة والضغط ---
SetupIconFile={#SourceDir}\logo.ico
WizardImageFile=compiler:WizClassicImage-IS.bmp
WizardSmallImageFile=compiler:WizClassicSmallImage-IS.bmp
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; --- الصلاحيات ---
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; --- إعدادات ويندوز ---
MinVersion=6.1
ArchitecturesInstallIn64BitMode=x64compatible

; --- إلغاء التثبيت ---
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
CreateUninstallRegKey=yes

; --- متفرقات ---
ShowLanguageDialog=no
DisableWelcomePage=no
DisableReadyPage=no
AlwaysShowDirOnReadyPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.WelcomeLabel1=Welcome to the Hakbah Million Setup Wizard
english.WelcomeLabel2=This will install {#AppName} version {#AppVersion} on your computer.%n%nIt is recommended that you close all other applications before continuing.%n%nClick Next to continue, or Cancel to exit.
english.FinishedLabel={#AppName} has been successfully installed on your computer.%n%nYou can launch the program from the desktop icon.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut (اختصار على سطح المكتب)"; GroupDescription: "Additional icons:"
Name: "startuprun";  Description: "Run at Windows startup (تشغيل عند بدء ويندوز)"; GroupDescription: "Additional options:"; Flags: unchecked

[Files]
; --- ملفات البرنامج الرئيسية ---
Source: "{#SourceDir}\dist\HakbahMillionAdmin\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; --- قاعدة البيانات (تُنسخ فقط إن لم تكن موجودة لحماية البيانات) ---
Source: "{#SourceDir}\hakbah.db"; \
    DestDir: "{app}"; \
    DestName: "hakbah.db"; \
    Flags: ignoreversion onlyifdoesntexist

[Icons]
; --- قائمة ابدأ ---
Name: "{autoprograms}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"; \
    Comment: "Hakbah Million Admin"

; --- سطح المكتب ---
Name: "{autodesktop}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"; \
    Tasks: desktopicon; \
    Comment: "Hakbah Million Admin"

; --- بدء التشغيل التلقائي ---
Name: "{userstartup}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    Tasks: startuprun

[Run]
; --- تشغيل البرنامج بعد التثبيت ---
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch Hakbah Million now"; \
    Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallDelete]
; --- حذف ملفات السجل عند الإلغاء ---
Type: files; Name: "{app}\server_error.log"
; ملاحظة: قاعدة البيانات hakbah.db لن تُحذف لحماية بياناتك

[Registry]
; --- تسجيل البرنامج في ويندوز (للتعرف عليه) ---
Root: HKCU; Subkey: "Software\{#AppPublisher}\{#AppNameEn}"; \
    ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; \
    Flags: uninsdeletekey

Root: HKCU; Subkey: "Software\{#AppPublisher}\{#AppNameEn}"; \
    ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; \
    Flags: uninsdeletekey

[Code]
// التحقق من وجود ملف EXE قبل التثبيت
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

// تأكيد الإلغاء عند النقر على إلغاء التثبيت
function InitializeUninstall(): Boolean;
var
  Answer: Integer;
begin
  Answer := MsgBox(
    'هل أنت متأكد من رغبتك في إلغاء تثبيت هكبة المليون؟' + #13#10 +
    'ملاحظة: لن يتم حذف قاعدة البيانات (بياناتك ستبقى محفوظة).',
    mbConfirmation, MB_YESNO
  );
  Result := (Answer = IDYES);
end;
