rem Set vram state to: NORMAL_VRAM
rem  --highvram --cache-classic --cache-lru 128
:top
rem ..\python_embeded\python.exe -s ..\ComfyUI\main.py --listen 127.0.0.1,192.168.10.2,192.168.0.6
REM ..\python_embeded\python.exe -m pip install -r W:\ComfyUI_windows_portable\ComfyUI\custom_nodes\ComfyUI-Sokes-Nodes\requirements.txt
..\python_embeded\python.exe -m pip install imghdr
pause
goto top