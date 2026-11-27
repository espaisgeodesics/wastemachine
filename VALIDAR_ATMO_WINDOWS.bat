@echo off
cd /d "%~dp0"
if not exist VALIDACIO\windows mkdir VALIDACIO\windows
set PYTHONUTF8=1
set SDL_AUDIODRIVER=dummy
py -3.12 -m compileall -q . > VALIDACIO\windows\compilacio.log 2>&1
py -3.12 -m tools.provar_tests > VALIDACIO\windows\tests.log 2>&1
set ATMO_TEST_RESULT=%ERRORLEVEL%
py -3.12 -m tools.capturar_atmo --output VALIDACIO\windows\captures --scales 1 1.25 1.5
set ATMO_CAPTURE_RESULT=%ERRORLEVEL%
echo Proves: %ATMO_TEST_RESULT% . Captures: %ATMO_CAPTURE_RESULT% .
echo Consulteu VALIDACIO\windows. Zero indica execucio correcta.
pause
