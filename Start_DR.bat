@echo off
setlocal
cd /d "%~dp0"

title Desperate Render

echo.
echo ========================================
echo          DESPERATE RENDER
 echo ========================================
echo.

if not exist "main.py" (
    echo [FEHLER] main.py wurde nicht gefunden.
    echo Bitte Start_DR.bat im Hauptverzeichnis von Desperate Render ausfuehren.
    goto :error
)

if not exist ".venv\Scripts\python.exe" (
    echo [FEHLER] Desperate Render wurde noch nicht eingerichtet.
    echo Bitte zuerst INSTALL.bat ausfuehren.
    goto :error
)

echo Starte Desperate Render...
echo.
".venv\Scripts\python.exe" main.py
set "DR_EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%DR_EXIT_CODE%"=="0" (
    echo [FEHLER] Desperate Render wurde mit Fehlercode %DR_EXIT_CODE% beendet.
) else (
    echo Desperate Render wurde beendet.
)
echo Dieses Fenster kann jetzt geschlossen werden.
echo.
pause
exit /b %DR_EXIT_CODE%

:error
echo.
pause
exit /b 1
