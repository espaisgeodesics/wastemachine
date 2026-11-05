@echo off
setlocal
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0wasteland_4_5_15_pas_15_editor_musical_desplegable.py"
) else if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0wasteland_4_5_15_pas_15_editor_musical_desplegable.py"
) else (
  py -3.12 "%~dp0wasteland_4_5_15_pas_15_editor_musical_desplegable.py"
)
if errorlevel 1 pause
