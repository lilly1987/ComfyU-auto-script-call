# -*- coding: utf-8 -*-
"""
ComfyUI 자동화 메인 스크립트
"""
import os
import sys
import time
from pathlib import Path
from typing import Dict, Set, Optional, Any
import threading
import importlib.util

# 모듈 자동 설치
try:
    import subprocess
    import importlib.util
    
    required_modules = []
    
    for module in required_modules:
        if importlib.util.find_spec(module) is None:
            print(f"📦 '{module}' 모듈이 설치되어 있지 않아 설치를 시도합니다...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])
except Exception:
    pass

required_modules = ["rich", "watchdog", "ruamel.yaml", "tinydb", "pandas", "openpyxl", "safetensors"]
missing_modules = [module for module in required_modules if importlib.util.find_spec(module) is None]

if missing_modules:
    print("필수 모듈이 설치되어 있지 않습니다.")
    print("누락 모듈:", ", ".join(missing_modules))
    print("먼저 '_run_install.cmd' 또는 'python -m pip install <module>'로 설치해 주세요.")
    sys.exit(1)

import yaml

# 경로 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

from utils.config_loader import ConfigLoader
from utils.yaml_handler import YAMLHandler
from utils.dict_utils import get_nested, set_nested
from utils.print_log import print, logger
from utils.db_handler import DatabaseHandler
from scripts.logic_selector import SelectorMixin
from scripts.logic_workflow import WorkflowMixin
from scripts.logic_observer import ObserverMixin
from scripts.logic_dataloader import DataLoaderMixin
from scripts.logic_api import ApiMixin
from scripts.logic_loop import LoopMixin

dicLoraYml='dicLoraYml'

# 설정 파일이 없으면 생성
config_path = Path(parent_dir) / 'config.yml'
if not config_path.exists():
    from utils.data_init import create_data_files
    create_data_files()


class ComfyUIAutomation(SelectorMixin, WorkflowMixin, ObserverMixin, DataLoaderMixin, ApiMixin, LoopMixin):
    """ComfyUI 자동화 메인 클래스"""
    
    def __init__(self):
        self.time_start = time.time()
        
        # 설정
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.config
        self.checkpoint_types = list(self.config.get('CheckpointTypes', {}).keys())
        self.is_first = True
        
        # 타입별 데이터
        self.type_dics: Dict[str, Dict] = {}
        
        # self.selected_kind: Optional[str] = None
        # 현재 선택된 항목
        self.checkpoint_type: Optional[str] = None
        self.checkpoint_name: Optional[str] = None
        self.checkpoint_path: Optional[str] = None
        self.char_name: Optional[str] = None
        self.char_path: Optional[str] = None
        self.lora_tmp: Optional[str] = None
        self.no_char = False
        self.from_img_path: Optional[str] = None
        # self.no_lora = False
        
        # 선택된 방식
        self.checkpoint_kind: Optional[str] = None
        self.char_kind: Optional[str] = None
        self.lora_kind: Optional[str] = None
        
        # LoRA 및 태그
        self.loras_set: Set[str] = set()
        self.tive_weight: Dict = {}
        self.positive_dics: Dict = {}
        self.negative_dics: Dict = {}
        self.yml_checkpoint: Dict = {}
        self.tive_char: Dict = {}
        self.tive_lora: Dict = {}
        
        # 루프 카운터
        self.total = 0
        self.checkpoint_loop_cnt = 0
        self.char_loop_cnt = 0
        self.queue_loop_cnt = 0
        self.checkpoint_loop = 0
        self.char_loop = 0
        self.queue_loop = 0
        self.lora_num = 0
        
        # 데이터베이스
        self.db = DatabaseHandler()
        
        # 워크플로우 API
        self.workflow_api: Dict = {}
        
        # YAML 핸들러
        self.yaml_handler = YAMLHandler()
        # 이벤트 디바운스/중복 처리용
        self._recent_events: Dict[str, float] = {}
        self._recent_events_lock = threading.Lock()
        self._xlsx_export_counter = 0
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """설정 값을 가져옵니다."""
        return self.config.get(key, default)
    
    def get_now(self, *keys, default: Any = None) -> Any:
        """현재 체크포인트 타입의 데이터를 가져옵니다."""
        return get_nested(self.type_dics, self.checkpoint_type, *keys, default=default)
    
    def set_now(self, value: Any, *keys):
        """현재 체크포인트 타입의 데이터를 설정합니다."""
        return set_nested(self.type_dics, value, self.checkpoint_type, *keys)
    def get_workflow(self, node: str, key: str) -> Any:
        """워크플로우에서 값을 가져옵니다."""
        return get_nested(self.workflow_api, node, "inputs", key)


if __name__ == '__main__':
    automation = ComfyUIAutomation()
    automation.run()
