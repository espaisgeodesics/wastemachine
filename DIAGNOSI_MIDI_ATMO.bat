@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python atmo_midi_diagnostics.py
) else (
  py -3 atmo_midi_diagnostics.py
)
pause
