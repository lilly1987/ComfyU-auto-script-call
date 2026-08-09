rem Set vram state to: NORMAL_VRAM
rem  --highvram --cache-classic --cache-lru 128
:top
rem ..\python_embeded\python.exe -s ..\ComfyUI\main.py --listen 127.0.0.1,192.168.10.2,192.168.0.6
REM ..\ComfyUI_windows_portable2\python_embeded\python.exe -m pip install filetype ultralytics numba ruamel.yaml webcolors colormath
..\ComfyUI_windows_portable2\python_embeded\python.exe -m pip install filetype 
REM ..\ComfyUI_windows_portable2\python_embeded\python.exe -m pip install -r ..\ComfyUI_windows_portable2\ComfyUI\custom_nodes\ComfyUI-Sokes-Nodes\requirements.txt
REM ..\ComfyUI_windows_portable2\python_embeded\python.exe -m pip install -r requirements.txt
pause
goto top