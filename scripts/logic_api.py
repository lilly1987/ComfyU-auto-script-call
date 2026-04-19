# -*- coding: utf-8 -*-
from typing import Tuple, Optional
from utils.print_log import print
from utils.comfy_api import queue_prompt, queue_prompt_wait

class ApiMixin:
    """ComfyUI API 통신 및 큐 관리를 담당하는 Mixin"""

    def _queue(self) -> Tuple[bool, Optional[int]]:
        """
        ComfyUI에 현재 설정된 워크플로우를 큐에 추가합니다.
        
        Returns:
            Tuple[bool, Optional[int]]: (성공 여부, HTTP 상태 코드)
        """
        if self.get_config("queue_prompt", True):
            success, status_code = queue_prompt(self.workflow_api, url=self.get_config('url'))
            if not success:
                print.Err("프롬프트 전송 실패", f"HTTP {status_code}" if status_code else "")
                return False, status_code
        
        if self.get_config("queue_prompt_wait", True):
            # ComfyUI 서버가 큐를 처리할 때까지 대기 (설정에 따름)
            if queue_prompt_wait(url=self.get_config('url')):
                print.Err("큐 대기 중 오류 발생 - 루프 중단 가능성")
                return False, None
        else:
            print.Info("queue_prompt_wait 비활성화됨")
        
        return True, None