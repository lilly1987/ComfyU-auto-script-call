# -*- coding: utf-8 -*-
"""
ComfyUI API 유틸리티
"""
import json
import time
from typing import Dict, Any, Optional, Tuple
from urllib import request
from urllib.error import URLError, HTTPError
from rich.progress import Progress

from .dict_utils import convert_paths
from .print_log import print, logger


def queue_prompt(prompt: Dict[str, Any], url: str = "http://127.0.0.1:8188/prompt") -> Tuple[bool, Optional[int]]:
    """
    ComfyUI에 프롬프트를 큐에 추가합니다.
    
    Args:
        prompt: 워크플로우 딕셔너리
        url: ComfyUI API URL
    
    Returns:
        Tuple[bool, Optional[int]]: 성공 여부 및 HTTP 상태 코드
    """
    try:
        p = {"prompt": prompt}
        p = convert_paths(p)
        data = json.dumps(p).encode('utf-8')
        
        req = request.Request(url, data=data)
    except TypeError as e:
        print.exception(show_locals=True)
        print.Err("프롬프트 변환 오류:", prompt)
        return False, None
    except Exception as e:
        print.exception(show_locals=True)
        return False, None

    while True:
        try:
            request.urlopen(req)
            print("프롬프트 전송 완료")
            return True, None
        except HTTPError as e:
            print.Err('프롬프트 내용:', prompt)
            print.Err('HTTP 오류 코드:', e.code)
            logger.exception("HTTPError 발생: %s, 프롬프트: %s", e, prompt)
            return False, e.code
        except URLError as e:
            print.Warn('URL 오류:', e.reason)            
            time.sleep(1)
        except Exception as e:
            logger.exception("에러 발생:", e)
            return False, None
    
    return False, None


def queue_prompt_wait(url: str = "http://127.0.0.1:8188/prompt", max_queue: int = 1) -> bool:
    """
    ComfyUI 큐가 지정된 개수 이하가 될 때까지 대기합니다.
    
    Args:
        url: ComfyUI API URL
        max_queue: 최대 큐 개수
    
    Returns:
        오류 발생 여부
    """
    start_time = time.time()

    with Progress() as progress:
        # 총 작업량 대신 지난 시간을 표시하는 Task 생성
        task = progress.add_task("Waiting", total=None)  # total=None → 무한 진행

        while True:
            try:
                with request.urlopen(url) as response:
                    data = json.loads(response.read().decode())
                    queue_remaining = data["exec_info"]["queue_remaining"]

                    # 지난 시간 계산
                    elapsed = int(time.time() - start_time)
                    progress.update(task, description=f"Elapsed: {elapsed}s")

                    if queue_remaining == 0:
                        break

                time.sleep(1)
                #ConnectionResetError: [WinError 10054] 현재 연결은 원격 호스트에 의해 강제로 끊겼습니다
            except (URLError, ConnectionRefusedError,ConnectionResetError) as e:
                # Ignore connection-refused / URLError (e.g., WinError 10061) and keep retrying
                logger.debug(f"Ignoring connection error, will retry: {e}")
                time.sleep(1)
                continue
            except Exception as e:
                logger.error("에러 발생:", e)
                # break

