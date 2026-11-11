@echo off
setlocal
cd /d "%~dp0"

 title Desperate Render - Installation
 echo.
 echo ========================================
 echo       DESPERATE RENDER - INSTALL
 echo ========================================
 echo.

if not exist "main.py" (
    echo [FEHLER] main.py wurde nicht gefunden.
    echo Bitte INSTALL.bat im Hauptverzeichnis von Desperate Render ausfuehren.
    goto :error
)

if not exist "requirements.txt" (
    echo [FEHLER] requirements.txt wurde nicht gefunden.
    goto :error
)

where py >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Der Python Launcher ^(py.exe^) wurde nicht gefunden.
    echo Bitte Python 3.14 ^(64-Bit^) installieren und den Python Launcher aktivieren.
    echo Download: https://www.python.org/downloads/windows/
    goto :error
)

py -3.14 --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python 3.14 wurde nicht gefunden.
    echo Bitte Python 3.14 ^(64-Bit^) installieren.
    echo Andere Python-Versionen werden fuer diesen Release-Test nicht verwendet.
    goto :error
)

echo [1/3] Python-Version:
py -3.14 --version

echo.
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Vorhandene virtuelle Umgebung wird weiterverwendet.
) else (
    echo [2/3] Erstelle virtuelle Python-Umgebung...
    py -3.14 -m venv .venv
    if errorlevel 1 goto :error
)

echo.
echo [2/3] Aktualisiere pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error

echo.
echo [3/3] Installiere Desperate-Render-Abhaengigkeiten...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo ========================================
echo Installation erfolgreich abgeschlossen.
echo Du kannst Desperate Render jetzt mit Start_DR.bat starten.
echo ========================================
echo.
pause
exit /b 0

:error
echo.
echo [FEHLER] Die Installation wurde nicht erfolgreich abgeschlossen.
echo Bitte pruefe die Meldungen oben. Es wurden keine Projektdateien geloescht.
echo.
pause
exit /b 1
