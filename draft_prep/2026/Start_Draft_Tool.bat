@echo off
title Gridiron Grind Draft Tool
cd /d "%~dp0"
echo ============================================================
echo  Starting your Draft Day Tool server...
echo ============================================================
echo.

rem Your Python (from your venv). If it ever moves, update this one line.
set "PYEXE=C:\Users\nai19\Documents\GitHub\venv_ianrosadodotcom\Scripts\python.exe"

rem Fallbacks if that path ever changes
if not exist "%PYEXE%" (
  set "PYEXE="
  where py >nul 2>nul && set "PYEXE=py"
  if not defined PYEXE where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE goto nopy

rem Open the browser a few seconds after the server should be up
start "" cmd /c "timeout /t 3 >nul & start "" http://localhost:8000/Draft_Day_Tool.html"

echo Using "%PYEXE%"
echo Serving on http://localhost:8000  -- keep THIS window OPEN during your draft.
echo.
"%PYEXE%" "%~dp0serve_draft.py"

echo.
echo ------------------------------------------------------------
echo  The server stopped. If it closed right after starting,
echo  copy any error above and send it to Claude.
echo ------------------------------------------------------------
pause
goto :eof

:nopy
echo Could not find your Python. Update the PYEXE line in this file.
echo.
pause
