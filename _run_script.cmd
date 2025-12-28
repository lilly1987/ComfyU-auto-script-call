@echo off
pushd %~dp0
:top
..\ComfyUI_windows_portable\python_embeded\python.exe scripts\main.py
color 
pause
goto top

