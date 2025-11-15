@echo off
pushd %~dp0
:top
..\python_embeded\python.exe scripts\main.py
color 
pause
goto top

