# -*- coding: utf-8 -*-
"""
ComfyUI API 유틸리티
"""
import json
import time
from typing import Dict, Any, Optional
from urllib import request
from urllib.error import URLError, HTTPError
from rich.progress import Progress

from .dict_utils import convert_paths
from .print_log import print, logger


def queue_prompt(prompt: Dict[str, Any], url: str = "http://127.0.0.1:8188/prompt") -> bool:
    """
    ComfyUI에 프롬프트를 큐에 추가합니다.
    
    Args:
        prompt: 워크플로우 딕셔너리
        url: ComfyUI API URL
    
    Returns:
        성공 여부
    """
    try:
        p = {"prompt": prompt}
        p = convert_paths(p)
        data = json.dumps(p).encode('utf-8')
        
        req = request.Request(url, data=data)
    except TypeError as e:
        print.exception(show_locals=True)
        print.Err("프롬프트 변환 오류:", prompt)
        return False
    except Exception as e:
        print.exception(show_locals=True)
        return False
    
    while True:
        try:
            request.urlopen(req)
        except HTTPError as e:
            print.Err('HTTP 오류 코드:', e.code)
            logger.exception("HTTPError 발생: %s", e)
            return False
        except URLError as e:
            print.Warn('URL 오류:', e.reason)
        else:
            break
    
    print("프롬프트 전송 완료")
    return True


def queue_prompt_wait(url: str = "http://127.0.0.1:8188/prompt", max_queue: int = 1) -> bool:
    """
    ComfyUI 큐가 지정된 개수 이하가 될 때까지 대기합니다.
    
    Args:
        url: ComfyUI API URL
        max_queue: 최대 큐 개수
    
    Returns:
        오류 발생 여부
    """
    try:
        with Progress() as progress:
            while True:
                if progress.finished:
                    task = progress.add_task("대기 중", total=60)
                
                req = request.Request(url)
                while True:
                    try:
                        response = request.urlopen(req)
                    except HTTPError as e:
                        progress.stop()
                        print.Err('HTTP 오류 코드:', e.code)
                        return True
                    except URLError as e:
                        progress.stop()
                        print.Warn('URL 오류:', e.reason)
                    else:
                        break
                
                html = response.read().decode("utf-8")
                data = json.loads(html)
                
                queue_remaining = data.get('exec_info', {}).get('queue_remaining', 0)
                
                if queue_remaining < max_queue:
                    progress.stop()
                    break
                
                progress.update(task, advance=1)
                time.sleep(1)
        
        return False
    except Exception as e:
        print.exception(show_locals=True)
        return True

