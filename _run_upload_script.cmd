@echo off
pushd %~dp0
:top
python upload_script.py
color 
pause
goto top

