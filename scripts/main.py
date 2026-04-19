# -*- coding: utf-8 -*-
"""
ComfyUI 자동화 메인 스크립트
"""
import os
import sys
import time
import copy
import random
import datetime
import fnmatch
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from urllib import request as urllib_request
from itertools import islice, zip_longest
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
from utils.file_handler import FileEventHandler, FileObserver, get_file_dict_list
from utils.dict_utils import get_nested, set_nested, set_exists, update_dict, update_dict_key, convert_paths, add_exists
from utils.random_utils import random_weight_count, random_min_max, random_weight, random_dict_weight, seed_int, random_items_count
from utils.type_utils import get_type_list
from utils.print_log import print, logger
from utils.comfy_api import queue_prompt, queue_prompt_wait
from utils.db_handler import DatabaseHandler
from watchdog.events import FileSystemEvent
from PIL import Image
import json
from scripts.logic_selector import SelectorMixin
from scripts.logic_workflow import WorkflowMixin

dicLoraYml='dicLoraYml'

# 설정 파일이 없으면 생성
config_path = Path(parent_dir) / 'config.yml'
if not config_path.exists():
    from utils.data_init import create_data_files
    create_data_files()


class ComfyUIAutomation(SelectorMixin, WorkflowMixin):
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
    
    def _load_wildcards(self):
        """각 checkpoint_type의 setupWildcard.yml에서 CharWildcard/LoraWildcard를 로드합니다.
        우선순위: {dataPath}/{checkpoint_type}/setupWildcard.yml > {dataPath}/setupWildcard.yml > config.yml
        """
        data_path = Path(self.get_config('dataPath'))
        
        for checkpoint_type in self.checkpoint_types:
            # 기본값: config.yml에서 로드
            char_wildcard = self.get_config('CharWildcard', {})
            lora_wildcard = self.get_config('LoraWildcard', {})
            # LoraWildcardEtc = self.get_config('LoraWildcardEtc', {})
            
            # setupWildcard.yml 로드 (base + type-specific)
            setup_wildcard = self.yaml_handler.load_simple(str(data_path / 'setupWildcard.yml')) or {}
            type_wildcard = self.yaml_handler.load_simple(str(data_path / checkpoint_type / 'setupWildcard.yml')) or {}
            
            # type-specific이 base를 덮어쓴다
            update_dict(setup_wildcard, type_wildcard)
            
            # CharWildcard, LoraWildcard 개별적으로 확인
            if setup_wildcard.get('CharWildcard'):
                char_wildcard = setup_wildcard['CharWildcard']
            
            if setup_wildcard.get('LoraWildcard'):
                lora_wildcard = setup_wildcard['LoraWildcard']
            
            # if setup_wildcard.get('LoraWildcardEtc'):
            #     LoraWildcardEtc = setup_wildcard['LoraWildcardEtc']
            
            # type_dics에 저장
            set_nested(self.type_dics, char_wildcard, checkpoint_type, 'CharWildcard')
            set_nested(self.type_dics, lora_wildcard, checkpoint_type, 'LoraWildcard')
            # set_nested(self.type_dics, LoraWildcardEtc, checkpoint_type, 'LoraWildcardEtc')
    
    def init(self, delete: bool = True, db: bool = False):
        """초기화합니다."""
        if db:
            self.db.init(self.get_config('dataPath'))
        
        data_path = Path(self.get_config('dataPath'))
        
        for checkpoint_type in self.checkpoint_types:
            self.type_dics[checkpoint_type] = {}
            
            # SafeTensors 파일 목록 가져오기
            self._get_safetensors_checkpoint(checkpoint_type)
            self._get_safetensors_char(checkpoint_type)
            self._get_safetensors_etc(checkpoint_type)
            
            # 설정 파일 가져오기
            self._load_wildcards()
            self._get_setup_wildcard(checkpoint_type)
            self._get_setup_workflow(checkpoint_type)
            
            # 가중치 가져오기
            self._get_weight_checkpoint(checkpoint_type)
            self._get_weight_lora(checkpoint_type, delete)
            self._get_weight_char(checkpoint_type)
            
            # YAML 딕셔너리 가져오기
            self._get_dic_checkpoint_yml(checkpoint_type)
            self._get_dic_lora_yml(checkpoint_type)
            
            # 워크플로우 API 가져오기
            self._get_workflow_api(checkpoint_type)
    
    def _get_safetensors_checkpoint(self, checkpoint_type: str):
        """Checkpoint SafeTensors 파일 목록을 가져옵니다."""
        checkpoint_path = Path(self.get_config('base_dir'),self.get_config('CheckpointPath'))
        base_path = checkpoint_path / checkpoint_type
        
        file_dict, file_list, file_names = get_file_dict_list(base_path, checkpoint_path)
        
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, file_dict, checkpoint_type, 'CheckpointFileDics')
        set_nested(self.type_dics, file_list, checkpoint_type, 'CheckpointFileLists')
        set_nested(self.type_dics, file_names, checkpoint_type, 'CheckpointFileNames')
        
        if not file_dict or not file_list or not file_names:
            print.Err('Checkpoint 파일 없음', checkpoint_type)
            print.Err(f'경로 확인: {base_path}')
            raise FileNotFoundError(f"Checkpoint 파일이 없습니다: {checkpoint_type}")
        
        print.Value('CheckpointFiles', checkpoint_type, len(file_names))
    
    def _get_safetensors_char(self, checkpoint_type: str):
        """Char SafeTensors 파일 목록을 가져옵니다."""
        lora_path = Path(self.get_config('base_dir'),self.get_config('LoraPath'))
        char_path = lora_path / checkpoint_type / self.get_config('LoraCharPath', 'char')
        
        file_dict, file_list, file_names = get_file_dict_list(char_path, lora_path)
        
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, file_dict, checkpoint_type, 'CharFileDics')
        set_nested(self.type_dics, file_list, checkpoint_type, 'CharFileLists')
        set_nested(self.type_dics, file_names, checkpoint_type, 'CharFileNames')
        
        print.Value('CharFiles', checkpoint_type, len(file_names))
    
    def _get_safetensors_etc(self, checkpoint_type: str):
        """Etc SafeTensors 파일 목록을 가져옵니다."""
        lora_path = Path(self.get_config('base_dir'),self.get_config('LoraPath'))
        etc_path = lora_path / checkpoint_type / self.get_config('LoraEtcPath', 'etc')
        
        file_dict, file_list, file_names = get_file_dict_list(etc_path, lora_path)
        
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, file_dict, checkpoint_type, 'LoraFileDics')
        set_nested(self.type_dics, file_list, checkpoint_type, 'LoraFileLists')
        set_nested(self.type_dics, file_names, checkpoint_type, 'LoraFileNames')
        
        print.Value('LoraFiles', checkpoint_type, len(file_names))

    def _cycle_sample(self, pool_key: str, source_items: List[str], count: int = 1) -> List[str]:
        """Cycle through source_items so every item is used once before repeating."""
        if not source_items or count <= 0:
            return []
        
        pool = list(self.get_now(pool_key, default=[]))
        if not pool:
            pool = list(source_items)
        
        selected: List[str] = []
        while count > 0:
            if not pool:
                pool = list(source_items)
                if not pool:
                    break
            idx = random.randrange(len(pool))
            selected.append(pool.pop(idx))
            count -= 1
        print.Value('pool',pool_key, len(pool))
        self.set_now(pool, pool_key)
        return selected

    def _collect_lora_tags(self) -> List[str]:
        """현재 선택된 LoRA의 태그를 모읍니다."""
        if  not self.loras_set:
            return []

        tags: List[str] = []
        dic_lora_yml = self.get_now(dicLoraYml, default={})

        for lora_name in self.loras_set:
            entry = dic_lora_yml.get(lora_name)
            if not isinstance(entry, dict):
                continue

            tag_field = entry.get('tag')
            if isinstance(tag_field, list):
                print.Value('tag', lora_name, len(tag_field), tag_field[:3])
                for tag in tag_field:
                    if isinstance(tag, str):
                        cleaned = tag.strip()
                        if cleaned:
                            tags.append(cleaned)
            elif isinstance(tag_field, str):
                print.Value('tag', lora_name, tag_field)
                cleaned = tag_field.strip()
                if cleaned:
                    tags.append(cleaned)

        return tags
    
    def _get_setup_wildcard(self, checkpoint_type: str = None):
        """setupWildcard.yml을 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        
        if checkpoint_type:
            checkpoint_types = [checkpoint_type]
        else:
            checkpoint_types = self.checkpoint_types
        
        for ct in checkpoint_types:
            try:
                setup_wildcard = self.yaml_handler.load_simple(str(data_path / 'setupWildcard.yml')) or {}
                type_wildcard = self.yaml_handler.load_simple(str(data_path / ct / 'setupWildcard.yml')) or {}
                
                update_dict(setup_wildcard, type_wildcard)
                
                if self.get_config("setupWildcardPrint", False):
                    print.Config('setupWildcard', ct, setup_wildcard)
                
                # init에서 호출될 때는 checkpoint_type을 직접 사용
                set_nested(self.type_dics, setup_wildcard, ct, 'setupWildcard')

            except Exception as e:
                print.Err(f"setupWildcard YML 파일 로드 실패: ",e)
    
    def _get_setup_workflow(self, checkpoint_type: str = None):
        """setupWorkflow.yml을 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        
        if checkpoint_type:
            checkpoint_types = [checkpoint_type]
        else:
            checkpoint_types = self.checkpoint_types
        
        for ct in checkpoint_types:
            setup_workflow = self.yaml_handler.load_simple(str(data_path / 'setupWorkflow.yml')) or {}
            type_workflow = self.yaml_handler.load_simple(str(data_path / ct / 'setupWorkflow.yml')) or {}
            
            update_dict(setup_workflow, type_workflow)
            
            if self.get_config("setupWorkflowPrint", False):
                print.Config('setupWorkflow', ct, setup_workflow)
            
            # init에서 호출될 때는 checkpoint_type을 직접 사용
            set_nested(self.type_dics, setup_workflow, ct, 'setupWorkflow')
    
    def _get_weight_checkpoint(self, checkpoint_type: str):
        """WeightCheckpoint.yml을 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        # checkpoint_type을 직접 사용
        checkpoint_file_names = get_nested(self.type_dics, checkpoint_type, 'CheckpointFileNames', default=[])
        
        weight_checkpoint = {}
        weight_yml = self.yaml_handler.load_simple(str(data_path / checkpoint_type / "WeightCheckpoint.yml")) or {}
        
        for key in checkpoint_file_names:
            # checkpoint_type을 직접 사용
            weight = get_nested(self.type_dics, checkpoint_type, 'dicCheckpointYml', key, 'weight')
            if weight:
                weight_checkpoint[key] = weight
            elif key in weight_yml:
                weight_checkpoint[key] = weight_yml[key]
            else:
                weight_checkpoint[key] = self.get_config('CheckpointWeightDefault', 150)
        
        print.Value('WeightCheckpoint', checkpoint_type, len(weight_checkpoint))
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, weight_checkpoint, checkpoint_type, 'WeightCheckpoint')
    
    def _get_weight_char(self, checkpoint_type: str):
        """WeightChar.yml을 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        # checkpoint_type을 직접 사용
        char_file_names = get_nested(self.type_dics, checkpoint_type, 'CharFileNames', default=[])
        
        weight_char = {}
        weight_yml = self.yaml_handler.load_simple(str(data_path / checkpoint_type / "WeightChar.yml")) or {}
        
        for key in char_file_names:
            # checkpoint_type을 직접 사용
            weight = get_nested(self.type_dics, checkpoint_type, dicLoraYml, key, 'weight')
            if weight:
                weight_char[key] = weight
            elif key in weight_yml:
                weight_char[key] = weight_yml[key]
            else:
                weight_char[key] = self.get_config('CharWeightDefault', 150)
        
        print.Value('WeightChar', checkpoint_type, len(weight_char))
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, weight_char, checkpoint_type, 'WeightChar')
    
    def _get_weight_lora(self, checkpoint_type: str, delete: bool = True):
        """WeightLora.yml을 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        weight_lora = self.yaml_handler.load_simple(str(data_path / checkpoint_type / "WeightLora.yml")) or {}
        
        print.Value('WeightLora', checkpoint_type, len(weight_lora))
        
        # 먼저 저장한 후 정리
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, weight_lora, checkpoint_type, 'WeightLora')
        
        if delete:
            self._clean_weight_lora(checkpoint_type)
        
        # 정리 후 다시 확인
        cleaned_weight_lora = get_nested(self.type_dics, checkpoint_type, 'WeightLora', default={})
        print.Value('WeightLora (cleaned)', checkpoint_type, len(cleaned_weight_lora))
    
    def _clean_weight_lora(self, checkpoint_type: str):
        """WeightLora에서 존재하지 않는 파일을 제거합니다."""
        # checkpoint_type을 직접 사용
        lora_file_names = get_nested(self.type_dics, checkpoint_type, 'LoraFileNames', default=[])
        weight_lora = get_nested(self.type_dics, checkpoint_type, 'WeightLora', default={})
        
        if not weight_lora:
            return
        
        for k1, v1 in list(weight_lora.items()):
            if not isinstance(v1, dict):
                continue
            
            dic = v1.get('dic', {})
            
            for k2, v2 in list(dic.items()):
                weight = v2.get('weight')
                per = v2.get('per')
                
                if not weight and not per:
                    dic.pop(k2)
                    continue
                
                loras = v2.get('loras', {})
                loras_tmp = None
                
                if isinstance(loras, dict):
                    loras_tmp = {k3: v3 for k3, v3 in loras.items() if k3 in lora_file_names}
                elif isinstance(loras, list):
                    loras_tmp = [k3 for k3 in loras if k3 in lora_file_names]
                elif isinstance(loras, str):
                    loras_tmp = loras if loras in lora_file_names else None
                
                if not loras_tmp:
                    dic.pop(k2)
                else:
                    dic[k2]["loras"] = loras_tmp
            
            if not dic:
                weight_lora.pop(k1)
            else:
                weight_lora[k1]['dic'] = dic
        
        # 정리된 weight_lora를 다시 저장
        # checkpoint_type 파라미터를 직접 사용
        set_nested(self.type_dics, weight_lora, checkpoint_type, 'WeightLora')
    
    def _get_dic_checkpoint_yml(self, checkpoint_type: str):
        """Checkpoint YAML 딕셔너리를 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        checkpoint_path = data_path / checkpoint_type / 'checkpoint'
        try:
            dic_checkpoint_yml = self.yaml_handler.merge_yml_files(checkpoint_path, '*.yml')
            
            if self.get_config("checkpointYmlPrint", False):
                print.Config('dicCheckpointYml', checkpoint_type, dict(islice(dic_checkpoint_yml.items(), 3)))
            
            # init에서 호출될 때는 checkpoint_type을 직접 사용
            set_nested(self.type_dics, dic_checkpoint_yml, checkpoint_type, 'dicCheckpointYml')
        except Exception as e:
            print.Err(f"Checkpoint YML 파일 로드 실패: ",e)

    def _get_dic_lora_yml(self, checkpoint_type: str):
        """LoRA YAML 딕셔너리를 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        lora_path = data_path / checkpoint_type / 'lora'
        try:
            dic_lora_yml = self.yaml_handler.merge_yml_files(lora_path, '*.yml')
            
            if self.get_config("loraYmlPrint", False):
                print.Config(dicLoraYml, checkpoint_type, dict(islice(dic_lora_yml.items(), 3)))
            
            # init에서 호출될 때는 checkpoint_type을 직접 사용
            set_nested(self.type_dics, dic_lora_yml, checkpoint_type, dicLoraYml)
        except Exception as e:
            print.Err(f"LoRA YML 파일 로드 실패: ",e)
            
    def _get_workflow_api(self, checkpoint_type: str):
        """워크플로우 API를 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        workflow_file = self.get_config('workflow_api', 'workflow_api.json')
        workflow_path = data_path / checkpoint_type / workflow_file
        
        workflow_api = self.yaml_handler.load_simple(str(workflow_path))
        if workflow_api:
            # init에서 호출될 때는 checkpoint_type을 직접 사용
            set_nested(self.type_dics, workflow_api, checkpoint_type, 'workflow_api')
    
    def get_workflow(self, node: str, key: str) -> Any:
        """워크플로우에서 값을 가져옵니다."""
        return get_nested(self.workflow_api, node, "inputs", key)

    def set_tive(self, num_name: str, dic: Dict, reset: bool = False):
        if reset:
            self.positive_dics.pop(num_name, None); self.negative_dics.pop(num_name, None)
        if dic:
            for key in ['positive', 'negative']:
                target = self.positive_dics if key == 'positive' else self.negative_dics
                update_dict(target.setdefault(num_name, {}), dic.get(key))


    def copy_workflow_api(self):
        if self.fromImg:
            return
        """워크플로우 API를 복사합니다."""
        workflow_api = self.get_now('workflow_api', default={})
        if workflow_api:
            self.workflow_api = copy.deepcopy(workflow_api)
        else:
            self.workflow_api = {}
    
    def update_safetensors(self, path: Path, checkpoint_type: str, event_type: str,
                          config_key: str, dics_key: str, lists_key: str, names_key: str):
        """SafeTensors 파일 목록을 생성/삭제 이벤트 기준으로 업데이트합니다."""
        # 구성에 저장된 상대 경로를 기준 폴더(base_dir)와 결합하여 절대 경로로 만듭니다.
        config_path = Path(self.get_config('base_dir'), self.get_config(config_key))
        try:
            rpath = path.relative_to(config_path)
        except ValueError:
            # 드물지만 path가 config_path의 하위가 아닐 경우에 대비한 폴백 처리
            if self.get_config('CallbackPrint', False):
                print.Warn('Path not in config_path, using fallback', path, config_path)
            rpath = Path(path.name)
        name = Path(rpath).stem
        print.Value(path, rpath, name)
        
        file_dics = self.get_now(dics_key, default={})
        file_lists = self.get_now(lists_key, default=[])
        file_names = self.get_now(names_key, default=[])
        spath = str(rpath)
        
        if event_type == 'deleted':
            file_dics.pop(name, None)
            if spath in file_lists:
                file_lists.remove(spath)
            if name in file_names:
                file_names.remove(name)
        
        if event_type == 'created':
            file_dics[name] = rpath
            if spath not in file_lists:
                file_lists.append(spath)
            if name not in file_names:
                file_names.append(name)
        
        self.set_now(file_dics, dics_key)
        self.set_now(file_lists, lists_key)
        self.set_now(file_names, names_key)
    
    def update_safetensors_char(self, path: Path, checkpoint_type: str, event_type: str):
        """Char SafeTensors 파일 목록을 업데이트합니다."""
        self.update_safetensors(path, checkpoint_type, event_type,
                               'LoraPath',
                               'CharFileDics',
                               'CharFileLists',
                               'CharFileNames')
    
    def update_safetensors_etc(self, path: Path, checkpoint_type: str, event_type: str):
        """Etc SafeTensors 파일 목록을 업데이트합니다."""
        self.update_safetensors(path, checkpoint_type, event_type,
                               'LoraPath',
                               'LoraFileDics',
                               'LoraFileLists',
                               'LoraFileNames')
    
    def update_safetensors_checkpoint(self, path: Path, checkpoint_type: str, event_type: str):
        """Checkpoint SafeTensors 파일 목록을 업데이트합니다."""
        self.update_safetensors(path, checkpoint_type, event_type,
                               'CheckpointPath',
                               'CheckpointFileDics',
                               'CheckpointFileLists',
                               'CheckpointFileNames')

    def _wait_for_stable_file(self, path: Path, stable_time: float = 0.5, timeout: float = 5.0) -> bool:
        """파일이 안정화(크기 변경 없음) 될 때까지 대기합니다.

        Returns:
            True: 안정화됨
            False: 타임아웃 또는 파일 접근 불가
        """
        start = time.time()
        last_size = -1
        stable_since = None
        while time.time() - start < timeout:
            try:
                size = path.stat().st_size
            except Exception:
                return False

            if size == last_size:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= stable_time:
                    return True
            else:
                last_size = size
                stable_since = None

            time.sleep(0.2)

        return False

    def _should_process_event(self, path: Path, event_type: str, debounce_seconds: float = 1.5) -> bool:
        """최근에 처리한 동일 이벤트를 무시하기 위한 단순 디바운스.

        Returns:
            True: 처리해야 함
            False: 무시
        """
        key = f"{event_type}:{str(path)}"
        now = time.time()
        with self._recent_events_lock:
            last = self._recent_events.get(key)
            # prune old entries
            if len(self._recent_events) > 1000:
                # remove entries older than 60s
                cutoff = now - 60
                keys_to_remove = [k for k, v in self._recent_events.items() if v < cutoff]
                for k in keys_to_remove:
                    self._recent_events.pop(k, None)

            if last and now - last < debounce_seconds:
                return False
            self._recent_events[key] = now
        return True

    def _maybe_export_db_xlsx(self, force: bool = False):
        """DB 엑셀 변환을 필요할 때만 수행합니다."""
        if force:
            self.db.json_to_xlsx()
            return

        interval = self.get_config('json_to_xlsx_interval', 0)
        if not interval:
            return

        self._xlsx_export_counter += 1
        if self._xlsx_export_counter >= interval:
            self.db.json_to_xlsx()
            self._xlsx_export_counter = 0
    
    def run(self):
        """메인 실행 루프"""
        try:
            self.init(db=True)
            
            # 파일 감시 시작
            file_observer = FileObserver()
            file_observer.watch(
                str(Path(self.get_config('dataPath'))),
                FileEventHandler(self._data_path_callback),
                recursive=True
            )
            file_observer.watch(
                str(Path(self.get_config('base_dir'), self.get_config('CheckpointPath'))),
                FileEventHandler(self._checkpoint_path_callback),
                recursive=True
            )
            file_observer.watch(
                str(Path(self.get_config('base_dir'), self.get_config('LoraPath'))),
                FileEventHandler(self._lora_path_callback),
                recursive=True
            )
            file_observer.watch(
                ".",
                FileEventHandler(self._config_callback),
                recursive=False
            )
            file_observer.start()
            
            # 메인 루프            
            while True:
                try:
                    self._loop()
                except Exception:
                    logger.exception('Exception')
                    print.exception(show_locals=True)
            
        except KeyboardInterrupt:
            print.Warn('KeyboardInterrupt')
            logger.info('KeyboardInterrupt')
        except Exception:
            logger.exception('Exception')
            print.exception(show_locals=True)
        finally:
            try:
                if 'file_observer' in locals() and file_observer:
                    file_observer.stop()

                self.db.close()
                self._maybe_export_db_xlsx(force=True)
            except Exception:
                print.exception(show_locals=True)
            
            print.save_html()
            print.Info(' === finally === ')
    
    def set_fromImg(self):
        """fromImg 모드에서 seed 랜덤화와 ckpt_name 설정을 수행합니다."""
        # Checkpoint ckpt_name을 현재 checkpoint_path로 교체
        self.set_workflow('CheckpointLoaderSimple', 'ckpt_name', self.checkpoint_path)
        
        # Ultralytics model_name 경로 동기화
        self._sync_model_names(self.workflow_api)
        
        # seed 값들을 변경 및 LoRA 파라미터 설정
        for node_id, node_config in self.workflow_api.items():
            if isinstance(node_config, dict) and 'inputs' in node_config:
                inputs = node_config['inputs']
                if not isinstance(inputs, dict):
                    continue

                # Seed 처리
                if 'seed' in inputs:
                    inputs['seed'] = seed_int()

                # LoRA 파라미터 처리 (set_lora 로직 참조)
                class_type = str(node_config.get('class_type', ''))
                if class_type.startswith('LoraLoader'):
                    lora_name_val = inputs.get('lora_name')
                    if lora_name_val and isinstance(lora_name_val, str):
                        # set_lora_sub에서 사용하는 self.lora_tmp 설정
                        self.lora_tmp = Path(lora_name_val).stem
                        for k in ['strength_model', 'strength_clip', 'A', 'B']:
                            val = self.set_lora_sub(k)
                            if val is not None:
                                inputs[k] = random_min_max(val)
        
        print.Value('fromImg seeds and LoRA parameters updated')
    
    def _loop(self):
        """메인 루프"""
        # 설정 확인
        if self.get_config('수정 안해서 작동 안시킴', False):
            print.Warn('---------------------------')
            print.Warn(f'{Path(self.get_config("dataPath"), "config.yml")} 끝까지 보세요')
            print.Warn('---------------------------')
            return
        
        self.lora_num = 0
        
        # Checkpoint 변경 (첫번째 루프)
        if self.checkpoint_loop_cnt == 0:
            try:
                self._maybe_export_db_xlsx()
            except Exception as e:
                print.exception(show_locals=True)
            
            self.checkpoint_change() # self.fromImg 와 파일 이름만
            self.checkpoint_loop_cnt += 1
            self.char_loop_cnt = 0

        if not self.fromImg:
            self.copy_workflow_api()
        
        # 일반 모드: 기존 로직
        if self.char_loop_cnt == 0:
            self.char_change()
            self.char_loop_cnt += 1
            self.queue_loop_cnt = 0
        
        if self.queue_loop_cnt == 0:
            self.lora_change()
            self.queue_loop_cnt += 1
     
        if self.fromImg:
            self.set_fromImg()
        else:
        # 워크플로우 설정
            self.set_setup_workflow_to_workflow_api()
            self.set_checkpoint_loader_simple()
            self.set_ksampler()
            self.set_dic_checkpoint_yml_to_workflow_api()
            self.set_char()
            self.set_lora()
            self.set_wildcard()
    
        # 저장 이미지 설정
        self.set_save_image()
        
        # 디버그 출력
        if self.get_config("WorkflowPrint", False):
            print.Config('workflow_api', self.workflow_api)            
        
        if self.get_config("tivePrint", False) or self.get_config("positivePrint", False):
            print.Config('positivePrint', self.positive_dics)
        
        if self.get_config("tivePrint", False) or self.get_config("negativePrint", False):
            print.Config('negativePrint',  self.negative_dics)
        
        # 루프 최대값 설정
        self.checkpoint_loop = random_min_max(self.get_config("CheckpointLoop", [1, 1]))
        self.char_loop = random_min_max(self.get_config("CharLoop", [1, 1]))
        self.queue_loop = random_min_max(self.get_config("queueLoop", [1, 1]))
        
        self.total += 1
        elapsed = datetime.timedelta(seconds=(time.time() - self.time_start))
        
        print(f"{self.total}, "
                f"{self.checkpoint_loop_cnt}/{self.checkpoint_loop}, "
                f"{self.char_loop_cnt}/{self.char_loop}, "
                f"{self.queue_loop_cnt}/{self.queue_loop}, "
                f"{elapsed}, "
                f"{self.checkpoint_type}, "
                f"{self.checkpoint_name}, "
                f"{self.char_name}, "
                f"{self.get_workflow('EmptyLatentImage', 'batch_size')}")
        
        # DB 업데이트 (fromImg 모드 제외)
        if not self.fromImg:
            lora_tags = self._collect_lora_tags()
            self.db.update(
                self.checkpoint_type,
                self.checkpoint_name,
                self.char_name,
                self.loras_set,
                tags=lora_tags,
            )
        
        # 큐에 추가
        success, status_code = self._queue()
        if not success:
            if self.fromImg and status_code == 400:
                failed_image = self.from_img_path
                self.from_img_path = self._select_from_img(exclude={failed_image})
                if self.from_img_path:
                    print.Warn(f'fromImg prompt HTTP 400. 다른 이미지로 교체: {failed_image} -> {self.from_img_path}')
                else:
                    print.Warn('fromImg 대체 이미지가 없습니다. 일반 모드로 전환합니다.')
                    self.checkpoint_kind = 'Weight'
                return
        
        time.sleep(random_min_max(self.get_config("sleep", 1)))
        
        self.queue_loop_cnt += 1
        
        if self.queue_loop_cnt > self.queue_loop:
            self.queue_loop_cnt = 0
            self.char_loop_cnt += 1
        
        if self.char_loop_cnt > self.char_loop:
            self.char_loop_cnt = 0
            if self.fromImg and self.checkpoint_loop_cnt < self.checkpoint_loop:
                failed_image = self.from_img_path
                self.from_img_path = self._select_from_img(exclude={failed_image} if failed_image else None)
                if self.from_img_path:
                    print.Value('fromImg image changed on checkpoint_loop increment', failed_image, '->', self.from_img_path)
                    # SelectorMixin의 handle_from_img_mode 로직 활용
                    if not self._handle_from_img_mode():
                        print.Warn('fromImg new prompt load failed')
                else:
                    print.Warn('fromImg 새 이미지 선택 실패, 기존 이미지 유지')
            self.checkpoint_loop_cnt += 1
        
        if self.checkpoint_loop_cnt > self.checkpoint_loop:
            self.checkpoint_loop_cnt = 0

    
    def _queue(self) -> Tuple[bool, Optional[int]]:
        """
        ComfyUI에 큐를 추가합니다.
        
        Returns:
            Tuple[bool, Optional[int]]:
                success: True이면 정상적으로 전송됨
                status_code: HTTP 오류 코드가 있을 경우 해당 코드
        """
        if self.get_config("queue_prompt", True):
            # queue_prompt가 성공(True)하면 계속 진행, 실패(False)하면 종료
            success, status_code = queue_prompt(self.workflow_api, url=self.get_config('url'))
            if not success:
                print.Err("프롬프트 전송 실패", f"HTTP {status_code}" if status_code else "")
                return False, status_code
        
        if self.get_config("queue_prompt_wait", True):
            if queue_prompt_wait(url=self.get_config('url')):
                print.Err("큐 대기 중 오류 발생 - 루프 종료")
                return False, None
        else:
            print.Info("queue_prompt_wait 비활성화됨")
        
        # 정상적으로 전송 완료
        return True, None
    
    def _data_path_callback(self, event: FileSystemEvent):
        """데이터 경로 변경 콜백"""
        try:
            path = Path(event.src_path)
            config_path = self.get_config('dataPath')
            
            if self.get_config('CallbackPrint', False):
                print.Value('dataPath', config_path)
            
            if fnmatch.fnmatch(str(path), str(Path(config_path) / '*')):
                rel = path.relative_to(config_path)
                if self.get_config('CallbackPrint', False):
                    print.Value('rel.parts', rel.parts)
                
                if len(rel.parts) > 0:
                    r0 = rel.parts[0]
                    if r0 in self.checkpoint_types:
                        if len(rel.parts) > 1:
                            r1 = rel.parts[1]
                            if r1 == 'setupWildcard.yml':
                                print.Value('setupWildcard.yml ok', event)
                                self._get_setup_wildcard(r0)
                                return
                            if r1 == 'setupWorkflow.yml':
                                print.Value('setupWorkflow.yml ok', event)
                                self._get_setup_workflow(r0)
                                return
                            if r1 == 'WeightCheckpoint.yml':
                                print.Value('WeightCheckpoint.yml ok', event)
                                self._get_weight_checkpoint(r0)
                                return
                            if r1 == 'WeightChar.yml':
                                print.Value('WeightChar.yml ok', event)
                                self._get_weight_char(r0)
                                return
                            if r1 == 'WeightLora.yml':
                                print.Value('WeightLora.yml ok', event)
                                self._get_weight_lora(r0)
                                return
                            if r1 == 'workflow_api.yml' or r1 == 'workflow_api.json':
                                print.Value('workflow_api ok', event)
                                self._get_workflow_api(r0)
                                return
                            if len(rel.parts) == 3:
                                if r1 == 'checkpoint':
                                    print.Value('checkpoint/*.yml ok', event)
                                    self._get_dic_checkpoint_yml(r0)
                                    return
                                if r1 == 'lora':
                                    print.Value('lora/*.yml ok', event)
                                    self._get_dic_lora_yml(r0)
                                    self._get_weight_char(r0)
                                    return
                    
                    if r0 == 'setupWildcard.yml':
                        print.Value('setupWildcard.yml ok', event)
                        self._get_setup_wildcard()
                        return
                    if r0 == 'setupWorkflow.yml':
                        print.Value('setupWorkflow.yml ok', event)
                        self._get_setup_workflow()
                        return
                    if r0 == 'config.yml':
                        print.Value('config.yml ok', event)
                        self.config_loader.reload()
                        self.config = self.config_loader.config
                        return
                
                if self.get_config('CallbackPrint', False):
                    print.Warn('dataPath not', path.parts)
        except Exception as e:
            print.exception(show_locals=True)
    
    def _checkpoint_path_callback(self, event: FileSystemEvent):
        """Checkpoint 경로 변경 콜백"""
        try:
            path = Path(event.src_path)
            config_path = Path(self.get_config('base_dir'), self.get_config('CheckpointPath'))
            
            if fnmatch.fnmatch(str(path), str(config_path / '*.safetensors')):
                if event.event_type not in {'created', 'deleted'}:
                    if self.get_config('CallbackPrint', False):
                        print.Value('CheckpointPath ignored event', event.event_type, path)
                    return

                print.Value('CheckpointPathCallback', event)
                rel = path.relative_to(config_path)
                
                if len(rel.parts) >= 1:
                    r0 = rel.parts[0]
                    if r0 not in self.checkpoint_types:
                        if self.get_config('CallbackPrint', False):
                            print.Warn('CheckpointPath type', path.parts)
                        return
                    
                    if len(rel.parts) == 2:
                        print.Value('CheckpointPath ok', event, rel)
                        # 디바운스/안정화 처리
                        if not self._should_process_event(path, event.event_type):
                            if self.get_config('CallbackPrint', False):
                                print.Value('Ignored duplicate event', path, event.event_type)
                            return

                        if event.event_type == 'created' and path.exists():
                            stable = self._wait_for_stable_file(path)
                            if not stable:
                                if self.get_config('CallbackPrint', False):
                                    print.Warn('File not stable, skipping', path)
                                return

                        self.update_safetensors_checkpoint(path, r0, event.event_type)
                        return
                    else:
                        if self.get_config('CallbackPrint', False):
                            print.Warn('CheckpointPath over', path, rel)
        except Exception as e:
            print.exception(show_locals=True)
    
    def _lora_path_callback(self, event: FileSystemEvent):
        """LoRA 경로 변경 콜백"""
        try:
            path = Path(event.src_path)
            config_path = Path(self.get_config('base_dir'), self.get_config('LoraPath'))
            
            if fnmatch.fnmatch(str(path), str(config_path / '*.ffs_db')) or \
               fnmatch.fnmatch(str(path), str(config_path / '*.ffs_lock')) or \
               fnmatch.fnmatch(str(path), str(config_path / '*.ffs_tmp')):
                return
            
            if fnmatch.fnmatch(str(path), str(config_path / '*.safetensors')):
                if event.event_type not in {'created', 'deleted'}:
                    if self.get_config('CallbackPrint', False):
                        print.Value('LoraPath ignored event', event.event_type, path)
                    return

                # print.Value('LoraPathCallback', event)
                rel = path.relative_to(config_path)
                
                if len(rel.parts) >= 1:
                    r0 = rel.parts[0]
                    if r0 not in self.checkpoint_types:
                        if self.get_config('CallbackPrint', False):
                            print.Warn('LoraPath type', path.parts)
                        return
                    
                    print.Value('LoraPath', path, rel)
                    if len(rel.parts) == 3:
                        if rel.parts[1] == 'char':
                            print.Value('LoraPath char ok', event)
                            # 디바운스/안정화 처리
                            if not self._should_process_event(path, event.event_type):
                                if self.get_config('CallbackPrint', False):
                                    print.Value('Ignored duplicate event', path, event.event_type)
                                return

                            if event.event_type == 'created' and path.exists():
                                stable = self._wait_for_stable_file(path)
                                if not stable:
                                    if self.get_config('CallbackPrint', False):
                                        print.Warn('File not stable, skipping', path)
                                    return

                            self.update_safetensors_char(path, r0, event.event_type)
                            return
                        if rel.parts[1] == 'etc':
                            print.Value('LoraPath etc ok', event)
                            # 디바운스/안정화 처리
                            if not self._should_process_event(path, event.event_type):
                                if self.get_config('CallbackPrint', False):
                                    print.Value('Ignored duplicate event', path, event.event_type)
                                return

                            if event.event_type == 'created' and path.exists():
                                stable = self._wait_for_stable_file(path)
                                if not stable:
                                    if self.get_config('CallbackPrint', False):
                                        print.Warn('File not stable, skipping', path)
                                    return

                            self.update_safetensors_etc(path, r0, event.event_type)
                            return
                    else:
                        if self.get_config('CallbackPrint', False):
                            print.Warn('LoraPath over', path, rel)
        except Exception as e:
            print.exception(show_locals=True)
    
    def _config_callback(self, event: FileSystemEvent):
        """설정 파일 변경 콜백"""
        try:
            path = Path(event.src_path)
            if path.name == 'config.yml':
                print.Value('ConfigCallback', path)
                self.config_loader.reload()
                self.config = self.config_loader.config
        except Exception as e:
            print.exception(show_locals=True)


if __name__ == '__main__':
    automation = ComfyUIAutomation()
    automation.run()
