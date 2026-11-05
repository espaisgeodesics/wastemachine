@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Executa primer INSTAL_LAR_AUDIO_LOCAL.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m tools.prova_audio_local --report AUDIO_PROVA_WINDOWS.json
if errorlevel 1 (
  echo La prova ha fallat. Conserva AUDIO_PROVA_WINDOWS.json i el missatge anterior.
  pause
  exit /b 1
)
echo Prova de canals i fades acabada. Cal comprovar audibilitat i latencia al dispositiu real.
pause
exit /b 0
