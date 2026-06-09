@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  ============================================
echo   Promed Messagerie  --  Script de build
echo  ============================================
echo.

:: ---- 1. PyInstaller -------------------------------------------------------
echo [1/4] Verification de PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo     Installation de PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 ( echo ERREUR installation PyInstaller & pause & exit /b 1 )
)
echo     OK

:: ---- 2. Conversion logo PNG -> ICO ----------------------------------------
echo.
echo [2/4] Conversion du logo PNG en ICO...
python -c ^
"try:^
    from PIL import Image;^
    img = Image.open('ressources/logo_promed.png');^
    img.save('ressources/logo_promed.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(256,256)]);^
    print('    OK')^
except ImportError:^
    import subprocess, sys;^
    subprocess.check_call([sys.executable,'-m','pip','install','pillow','--quiet']);^
    from PIL import Image;^
    img = Image.open('ressources/logo_promed.png');^
    img.save('ressources/logo_promed.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(256,256)]);^
    print('    OK (Pillow installe automatiquement)')^
except Exception as e:^
    print(f'    Avertissement: {e}  (le .exe sera sans icone personnalisee)')^
"

:: ---- 3. PyInstaller build -------------------------------------------------
echo.
echo [3/4] Construction avec PyInstaller (peut prendre 2-3 minutes)...
pyinstaller --clean --noconfirm PromedMessagerie.spec
if errorlevel 1 (
    echo.
    echo ERREUR lors de la construction PyInstaller !
    pause
    exit /b 1
)
echo     OK  -^>  dossier cree : dist\PromedMessagerie\

:: ---- 4. Inno Setup (optionnel) --------------------------------------------
echo.
echo [4/4] Recherche de Inno Setup pour creer l'installateur .exe...

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if "!ISCC!"=="" (
    echo     Inno Setup non trouve.
    echo     Pour creer un .exe installateur avec raccourcis :
    echo       1. Telecharger Inno Setup 6 : https://jrsoftware.org/isdl.php
    echo       2. Relancer ce script
    echo.
    echo     En attendant, vous pouvez distribuer le dossier :
    echo       dist\PromedMessagerie\
    echo     (lancez PromedMessagerie.exe depuis ce dossier)
) else (
    echo     Inno Setup trouve. Creation de l'installateur...
    "!ISCC!" ..\installer\setup.iss
    if errorlevel 1 (
        echo     ERREUR lors de la compilation Inno Setup !
    ) else (
        echo     OK  -^>  installateur cree : ..\installer\output\PromedMessagerie_Setup.exe
    )
)

echo.
echo ============================================
echo   Build termine !
echo ============================================
echo.
pause
