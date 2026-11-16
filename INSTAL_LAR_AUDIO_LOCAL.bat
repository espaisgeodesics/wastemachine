@echo off
cd /d "%~dp0"
py -3.12 -m pip install --only-binary=:all: -r requirements-audio.txt
pause
