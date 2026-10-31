@echo off
setlocal
cd /d "%~dp0"
for %%F in (wasteland_4_5_15_pas_15_editor_musical_desplegable.py spatial_zones.py spatial_zone_editor.py spatial_projection.py spatial_calibration.py marker_tracking.py aruco_observations.py participants.py domain_events.py participant_editor.py participant_simulator.py simulator_window.py common_spatial.py experience_rules.py rule_outputs.py rule_editor.py local_audio.py audio_controller.py audio_window.py bosc_viu.py) do (
  if not exist "%~dp0%%F" (
    echo Falta el fitxer %%F. Extreu tot el ZIP abans d'obrir Wasteland.
    pause
    exit /b 1
  )
)
if exist ".venv\Scripts\python.exe" goto dependencies
py -3.12 -m venv .venv
if errorlevel 1 goto python_missing
:dependencies
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed
".venv\Scripts\python.exe" wasteland_4_5_15_pas_15_editor_musical_desplegable.py
if errorlevel 1 goto run_failed
exit /b 0
:python_missing
echo Cal instal.lar Python 3.12 per a Windows amb el Python Launcher i Tcl/Tk.
echo Descarrega'l de https://www.python.org/downloads/windows/
pause
exit /b 1
:install_failed
echo No s'han pogut instal.lar les dependencies. Comprova la connexio a Internet.
pause
exit /b 1
:run_failed
echo El programa ha finalitzat amb un error. Copia el missatge anterior per revisar-lo.
pause
exit /b 1
