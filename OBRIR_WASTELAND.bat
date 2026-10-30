@echo off
setlocal
cd /d "%~dp0"
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
