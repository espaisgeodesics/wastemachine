@echo off
cd /d "%~dp0"
py -3.12 -m pip install --only-binary=:all: mido==1.3.3 python-rtmidi==1.5.8
pause
