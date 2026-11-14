@echo off
echo ==============================================
echo Building executable with PyInstaller...
echo ==============================================
call .\.venv\Scripts\pyinstaller.exe HakbahMillionAdmin.spec --clean -y

echo.
echo ==============================================
echo Creating Installer with Inno Setup...
echo ==============================================
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

echo.
echo ==============================================
echo Done! You can find the installer in the "dist" folder.
echo ==============================================
pause
