@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-audio.txt
if errorlevel 1 goto failed
echo Complement instal.lat. Obre OBRIR_WASTELAND.bat i activa Audio local.
pause
exit /b 0
:failed
echo No s'ha pogut instal.lar el complement. Copia l'error anterior.
pause
exit /b 1
