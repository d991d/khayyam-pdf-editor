@echo off
setlocal enabledelayedexpansion
REM ═══════════════════════════════════════════════════════════════════════════
REM  Khayyam PDF Editor — Full Windows Build Pipeline
REM
REM  What this does:
REM    1. Generates icon.ico from the Mac PNG icon set
REM    2. Bundles the app with PyInstaller  →  dist\Khayyam PDF Editor\
REM    3. Compiles installer.iss with Inno Setup  →  installer\*.exe
REM
REM  Prerequisites (run once):
REM    pip install -r requirements.txt
REM    pip install pyinstaller Pillow
REM    Install Inno Setup 6: https://jrsoftware.org/isinfo.php
REM ═══════════════════════════════════════════════════════════════════════════

echo.
echo  ██╗  ██╗██╗  ██╗ █████╗ ██╗   ██╗██╗   ██╗ █████╗ ███╗   ███╗
echo  ██║ ██╔╝██║  ██║██╔══██╗╚██╗ ██╔╝╚██╗ ██╔╝██╔══██╗████╗ ████║
echo  █████╔╝ ███████║███████║ ╚████╔╝  ╚████╔╝ ███████║██╔████╔██║
echo  ██╔═██╗ ██╔══██║██╔══██║  ╚██╔╝    ╚██╔╝  ██╔══██║██║╚██╔╝██║
echo  ██║  ██╗██║  ██║██║  ██║   ██║      ██║   ██║  ██║██║ ╚═╝ ██║
echo  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝
echo  PDF Editor for Windows — Build Script
echo.

REM ── Step 0: sanity checks ─────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ and add it to PATH.
    goto :fail
)

python -c "import fitz" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyMuPDF not installed. Run:  pip install -r requirements.txt
    goto :fail
)

python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyQt6 not installed. Run:  pip install -r requirements.txt
    goto :fail
)

python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller not installed. Run:  pip install pyinstaller
    goto :fail
)

REM ── Step 1: Generate icon.ico ─────────────────────────────────────────────
echo [1/3] Generating icon.ico ...
python make_icon.py
if %errorlevel% neq 0 (
    echo [ERROR] Icon generation failed. Run:  pip install Pillow
    goto :fail
)
echo.

REM ── Step 2: PyInstaller — bundle the app ──────────────────────────────────
echo [2/3] Bundling with PyInstaller ...
echo.

REM Clean previous build artefacts
if exist dist   rmdir /s /q dist
if exist build  rmdir /s /q build

pyinstaller khayyam.spec --noconfirm --clean
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed.
    goto :fail
)

REM Verify output
if not exist "dist\Khayyam PDF Editor\Khayyam PDF Editor.exe" (
    echo [ERROR] Expected exe not found after build.
    goto :fail
)
echo.
echo   App bundle ready: dist\Khayyam PDF Editor\
echo.

REM ── Step 3: Inno Setup — create the installer ─────────────────────────────
echo [3/3] Compiling installer with Inno Setup ...
echo.

REM Look for Inno Setup in common install locations
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
) else (
    REM Check PATH
    where ISCC >nul 2>&1
    if %errorlevel% == 0 set ISCC=ISCC
)

if "%ISCC%"=="" (
    echo [WARNING] Inno Setup not found.
    echo   Download and install it from: https://jrsoftware.org/isinfo.php
    echo   Then re-run this script to build the installer.
    echo.
    echo   The app bundle is still usable from:
    echo     dist\Khayyam PDF Editor\Khayyam PDF Editor.exe
    goto :done_no_installer
)

if not exist installer mkdir installer

"%ISCC%" /Q installer.iss
if %errorlevel% neq 0 (
    echo [ERROR] Inno Setup compilation failed.
    goto :fail
)

echo.
echo ═══════════════════════════════════════════════════════════════════
echo   BUILD COMPLETE
echo.
echo   App bundle:  dist\Khayyam PDF Editor\Khayyam PDF Editor.exe
for %%f in (installer\*.exe) do echo   Installer:   %%f
echo ═══════════════════════════════════════════════════════════════════
echo.
pause
exit /b 0

:done_no_installer
echo ═══════════════════════════════════════════════════════════════════
echo   BUILD COMPLETE (app only — install Inno Setup for the installer)
echo.
echo   App bundle:  dist\Khayyam PDF Editor\Khayyam PDF Editor.exe
echo ═══════════════════════════════════════════════════════════════════
echo.
pause
exit /b 0

:fail
echo.
echo ═══════════════════════════════════════════════════════════════════
echo   BUILD FAILED — see errors above.
echo ═══════════════════════════════════════════════════════════════════
echo.
pause
exit /b 1
