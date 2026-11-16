@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python atmo_esfera_fx_integracio_12.py
) else (
  py -3 atmo_esfera_fx_integracio_12.py
)
pause
