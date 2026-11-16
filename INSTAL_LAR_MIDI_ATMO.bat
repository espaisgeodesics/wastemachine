@echo off
cd /d "%~dp0"
echo ATMO: installacio de mido i python-rtmidi per al Python del llancador.
where py >nul 2>nul
if errorlevel 1 (
  python -m pip install mido==1.3.3 python-rtmidi==1.5.8
) else (
  py -3 -m pip install mido==1.3.3 python-rtmidi==1.5.8
)
pause
