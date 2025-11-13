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
from typing import Dict, List, Set, Optional, Any
from itertools import islice, zip_longest

# 모듈 자동 설치
try:
    import subprocess
    import importlib.util
    
    required_modules = ["rich", "watchdog", "ruamel.yaml", "tinydb", "pandas", "openpyxl", "safetensors"]
    
    for module in required_modules:
        if importlib.util.find_spec(module) is None:
            print(f"📦 '{module}' 모듈이 설치되어 있지 않아 설치를 시도합니다...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])
except Exception:
    pass

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_loader import ConfigLoader
from utils.yaml_handler import YAMLHandler
from utils.file_handler import FileEventHandler, FileObserver, get_file_dict_list
from utils.dict_utils import get_nested, set_nested, set_exists, update_dict, update_dict_key, convert_paths
from utils.random_utils import random_weight_count, random_min_max, random_weight, random_dict_weight, seed_int, random_items_count
from utils.type_utils import get_type_list
from utils.print_log import print, logger
from utils.comfy_api import queue_prompt, queue_prompt_wait
from utils.db_handler import DatabaseHandler
from watchdog.events import FileSystemEvent

# 설정 파일이 없으면 생성
if not Path('config.yml').exists():
    from utils.data_init import create_data_files
    create_data_files()


class ComfyUIAutomation:
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
        
        # 현재 선택된 항목
        self.checkpoint_type: Optional[str] = None
        self.checkpoint_name: Optional[str] = None
        self.checkpoint_path: Optional[str] = None
        self.char_name: Optional[str] = None
        self.char_path: Optional[str] = None
        self.lora_tmp: Optional[str] = None
        self.no_char = False
        self.no_lora = False
        
        # LoRA 및 태그
        self.loras_set: Set[str] = set()
        self.tive_weight: Dict = {}
        self.positive_dics: Dict = {}
        self.negative_dics: Dict = {}
        self.tive_checkpoint: Dict = {}
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
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """설정 값을 가져옵니다."""
        return self.config.get(key, default)
    
    def get_now(self, *keys, default: Any = None) -> Any:
        """현재 체크포인트 타입의 데이터를 가져옵니다."""
        return get_nested(self.type_dics, self.checkpoint_type, *keys, default=default)
    
    def set_now(self, value: Any, *keys):
        """현재 체크포인트 타입의 데이터를 설정합니다."""
        return set_nested(self.type_dics, value, self.checkpoint_type, *keys)
    
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
        checkpoint_path = Path(self.get_config('CheckpointPath'))
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
        lora_path = Path(self.get_config('LoraPath'))
        char_path = lora_path / checkpoint_type / self.get_config('LoraCharPath', 'char')
        
        file_dict, file_list, file_names = get_file_dict_list(char_path, lora_path)
        
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, file_dict, checkpoint_type, 'CharFileDics')
        set_nested(self.type_dics, file_list, checkpoint_type, 'CharFileLists')
        set_nested(self.type_dics, file_names, checkpoint_type, 'CharFileNames')
        
        print.Value('CharFiles', checkpoint_type, len(file_names))
    
    def _get_safetensors_etc(self, checkpoint_type: str):
        """Etc SafeTensors 파일 목록을 가져옵니다."""
        lora_path = Path(self.get_config('LoraPath'))
        etc_path = lora_path / checkpoint_type / self.get_config('LoraEtcPath', 'etc')
        
        file_dict, file_list, file_names = get_file_dict_list(etc_path, lora_path)
        
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, file_dict, checkpoint_type, 'LoraFileDics')
        set_nested(self.type_dics, file_list, checkpoint_type, 'LoraFileLists')
        set_nested(self.type_dics, file_names, checkpoint_type, 'LoraFileNames')
        
        print.Value('LoraFiles', checkpoint_type, len(file_names))
    
    def _get_setup_wildcard(self, checkpoint_type: str = None):
        """setupWildcard.yml을 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        
        if checkpoint_type:
            checkpoint_types = [checkpoint_type]
        else:
            checkpoint_types = self.checkpoint_types
        
        for ct in checkpoint_types:
            setup_wildcard = self.yaml_handler.load_simple(str(data_path / 'setupWildcard.yml')) or {}
            type_wildcard = self.yaml_handler.load_simple(str(data_path / ct / 'setupWildcard.yml')) or {}
            
            update_dict(setup_wildcard, type_wildcard)
            
            if self.get_config("setupWildcardPrint", False):
                print.Config('setupWildcard', ct, setup_wildcard)
            
            # init에서 호출될 때는 checkpoint_type을 직접 사용
            set_nested(self.type_dics, setup_wildcard, ct, 'setupWildcard')
    
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
            weight = get_nested(self.type_dics, checkpoint_type, 'dicLoraYml', key, 'weight')
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
        
        dic_checkpoint_yml = self.yaml_handler.merge_yml_files(checkpoint_path, '*.yml')
        
        if self.get_config("checkpointYmlPrint", False):
            print.Config('dicCheckpointYml', checkpoint_type, dict(islice(dic_checkpoint_yml.items(), 3)))
        
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, dic_checkpoint_yml, checkpoint_type, 'dicCheckpointYml')
    
    def _get_dic_lora_yml(self, checkpoint_type: str):
        """LoRA YAML 딕셔너리를 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        lora_path = data_path / checkpoint_type / 'lora'
        
        dic_lora_yml = self.yaml_handler.merge_yml_files(lora_path, '*.yml')
        
        if self.get_config("loraYmlPrint", False):
            print.Config('dicLoraYml', checkpoint_type, dict(islice(dic_lora_yml.items(), 3)))
        
        # init에서 호출될 때는 checkpoint_type을 직접 사용
        set_nested(self.type_dics, dic_lora_yml, checkpoint_type, 'dicLoraYml')
    
    def _get_workflow_api(self, checkpoint_type: str):
        """워크플로우 API를 가져옵니다."""
        data_path = Path(self.get_config('dataPath'))
        workflow_file = self.get_config('workflow_api', 'workflow_api.json')
        workflow_path = data_path / checkpoint_type / workflow_file
        
        workflow_api = self.yaml_handler.load_simple(str(workflow_path))
        if workflow_api:
            # init에서 호출될 때는 checkpoint_type을 직접 사용
            set_nested(self.type_dics, workflow_api, checkpoint_type, 'workflow_api')
    
    def checkpoint_change(self):
        """Checkpoint를 선택합니다."""
        checkpoint_types = self.get_config('CheckpointTypes', {})
        
        if self.is_first:
            self.is_first = False
            safetensors_start = self.get_config('safetensorsStart')
            if safetensors_start:
                safetensors_path = Path(safetensors_start)
                ck = get_nested(self.type_dics, safetensors_path.parts[0], 'CheckpointFileDics', safetensors_path.stem)
                if len(safetensors_path.parts) == 2 and \
                   safetensors_path.parts[0] in checkpoint_types and \
                   ck:
                    print.Value('safetensorsStart', safetensors_path.parts)
                    self.checkpoint_type = safetensors_path.parts[0]
                    print.Value('checkpoint_type', self.checkpoint_type)
                    self.checkpoint_name = safetensors_path.stem
                    print.Value('checkpoint_name', self.checkpoint_name)
                    self.checkpoint_path = self.get_now('CheckpointFileDics', self.checkpoint_name)
                    print.Value('checkpoint_path', self.checkpoint_path)
                    return
        
        # 랜덤으로 Checkpoint 타입 선택
        self.checkpoint_type = random_weight_count(checkpoint_types)[0]
        print.Value('checkpoint_type', self.checkpoint_type)
        
        checkpoint_weight_per = self.get_config('CheckpointWeightPer', 0.5)
        checkpoint_weight_per_result = checkpoint_weight_per > random.random()
        print.Value('CheckpointWeightPer', checkpoint_weight_per, checkpoint_weight_per_result)
        
        weight_checkpoint = self.get_now('WeightCheckpoint', default={})
        checkpoint_file_names = self.get_now('CheckpointFileNames', default=[])
        
        if not checkpoint_file_names:
            print.Err(f'CheckpointFileNames가 비어있습니다: {self.checkpoint_type}')
            print.Err(f'CheckpointPath를 확인하세요: {self.get_config("CheckpointPath")}/{self.checkpoint_type}')
            raise ValueError(f"Checkpoint 파일이 없습니다: {self.checkpoint_type}")
        
        if checkpoint_weight_per_result:
            if len(weight_checkpoint) > 0:
                self.checkpoint_name = random_weight_count(weight_checkpoint)[0]
            else:
                self.checkpoint_name = random.choice(checkpoint_file_names)
                print.Warn('no WeightCheckpoint')
        else:
            sub_checkpoint = [x for x in checkpoint_file_names if x not in weight_checkpoint.keys()]
            print.Value('SubCheckpoint', len(sub_checkpoint))
            
            if len(sub_checkpoint) > 0:
                self.checkpoint_name = random.choice(sub_checkpoint)
            else:
                self.checkpoint_name = random.choice(checkpoint_file_names)
                print.Warn('no WeightCheckpoint')
        
        print.Value('checkpoint_name', self.checkpoint_name)
        self.checkpoint_path = self.get_now('CheckpointFileDics', self.checkpoint_name)
        print.Value('checkpoint_path', self.checkpoint_path)
        
        if not self.checkpoint_path:
            print.Err(f'checkpoint_path를 찾을 수 없습니다: {self.checkpoint_name}')
            print.Err(f'CheckpointFileDics를 확인하세요')
            raise ValueError(f"Checkpoint 경로를 찾을 수 없습니다: {self.checkpoint_name}")
    
    def char_change(self):
        """Char를 선택합니다."""
        no_char_per = self.get_config('noCharPer', 0.5)
        r = random.random()
        self.no_char = no_char_per > r
        print.Value('noCharPer', no_char_per, r, self.no_char)
        
        char_file_names = self.get_now('CharFileNames', default=[])
        weight_char = self.get_now('WeightChar', default={})
        
        if self.no_char:
            self.char_name = 'noChar'
            char_file_lists = self.get_now('CharFileLists', default=[])
            self.char_path = char_file_lists[0] if char_file_lists else None
            print.Value('char_path', self.char_path)
        else:
            char_weight_per = self.get_config('CharWeightPer', 0.5)
            r = random.random()
            char_weight_per_result = char_weight_per > r
            print.Value('CharWeightPer', char_weight_per, r, char_weight_per_result)
            
            if char_weight_per_result:
                if len(weight_char) > 0:
                    self.char_name = random_weight_count(weight_char)[0]
                else:
                    print.Warn('no WeightChar')
                    self.char_name = random.choice(char_file_names) if char_file_names else None
            else:
                sub_char = [x for x in char_file_names if x not in weight_char.keys()]
                print.Value('SubChar', len(sub_char))
                
                if len(sub_char) > 0:
                    self.char_name = random.choice(sub_char)
                    logger.warning(f'no in WeightChar: {self.char_name}')
                else:
                    print.Warn('no SubChar')
                    self.char_name = random.choice(char_file_names) if char_file_names else None
            
            print.Value('char_name', self.char_name)
            self.char_path = self.get_now('CharFileDics', self.char_name)
            print.Value('char_path', self.char_path)
    
    def lora_change(self):
        """LoRA를 선택합니다."""
        self.tive_weight = {}
        self.loras_set = set()
        
        no_lora_per = self.get_config('noLoraPer', 0.5)
        r = random.random()
        self.no_lora = no_lora_per > r
        print.Value('noLoraPer', no_lora_per, r, self.no_lora)
        
        if self.no_lora:
            return
        
        weight_lora = self.get_now('WeightLora', default={})
        
        for k1, v1 in weight_lora.items():
            print.Value('LoraChange', k1, len(v1))
            dic = v1.get('dic', {})
            tive_weight_tmp = {}
            loras_set_tmp = set()
            
            # per 처리
            per = v1.get('per', False)
            if per:
                per_max = v1.get('perMax', 0)
                per_max = random_min_max(per_max)
                per_cnt = 0
                per_firsts = v1.get('perFirsts', False)
                
                for k2, v2 in dic.items():
                    if per_firsts and per_cnt >= per_max:
                        print.Value('perCnt, perMax', per_cnt, per_max)
                        break
                    
                    per_val = v2.get('per', 0)
                    r = random.random()
                    if per_val > r:
                        loras = v2.get('loras')
                        lora = random_weight(loras)
                        tive_weight_tmp[lora] = v2
                        per_cnt += 1
            
            # weight 처리
            weight = v1.get('weight', False)
            if weight:
                weight_max = v1.get('weightMax', 0)
                weight_max = random_min_max(weight_max)
                loras_key_set_tmp = set(random_dict_weight(dic, 'weight', weight_max))
                print.Value('LoraChange weight', k1, loras_key_set_tmp)
                
                for k2 in loras_key_set_tmp:
                    v2 = dic.get(k2)
                    loras = v2.get('loras')
                    lora = random_weight(loras)
                    tive_weight_tmp[lora] = v2
            
            # total 처리
            total = v1.get('total', False)
            if total:
                total_max = v1.get('totalMax', 0)
                total_max = random_min_max(total_max)
                l = random_items_count(tive_weight_tmp, total_max)
                loras_set_tmp.update(l)
            else:
                l = list(tive_weight_tmp.keys())
                loras_set_tmp.update(l)
            
            # tive_weight 업데이트
            for k2 in loras_set_tmp:
                update_dict_key(self.tive_weight, tive_weight_tmp[k2], 'positive')
                update_dict_key(self.tive_weight, tive_weight_tmp[k2], 'negative')
            
            print.Value('lorasSetTmp', k1, loras_set_tmp)
            self.loras_set = self.loras_set.union(loras_set_tmp)
        
        if self.get_config("LoraChangePrint", False):
            print.Config('positiveDics', self.positive_dics)
            print.Config('negativeDics', self.negative_dics)
        print.Value('lorasSet', self.loras_set)
    
    def get_workflow(self, node: str, key: str) -> Any:
        """워크플로우에서 값을 가져옵니다."""
        return get_nested(self.workflow_api, node, "inputs", key)
    
    def set_workflow(self, node: str, key: str, value: Any) -> bool:
        """워크플로우에 값을 설정합니다."""
        if self.get_config('SetWorkflowPrint', False):
            print.Config('SetWorkflow', node, key, value)
        return set_exists(self.workflow_api, value, node, "inputs", key) is not None
    
    def set_workflow_func_random2(self, node: str, key_list: List[str], 
                                   random_func=None, func=None):
        """워크플로우에 랜덤 값을 설정합니다."""
        setup_workflow = self.get_now('setupWorkflow', default={})
        
        for k in key_list:
            v = self.get_workflow(node, k)
            v = get_nested(setup_workflow, 'workflow', node, k, default=v)
            
            if func:
                v = func(v, k)
            
            if random_func:
                v = random_func(v)
            
            s = get_nested(setup_workflow, 'workflow_scale', node, k)
            if s:
                s = random_min_max(s)
                v *= s
            
            m = get_nested(setup_workflow, 'workflow_min', node, k)
            if m:
                m = random_min_max(m)
                v = max(v, m)
            
            m = get_nested(setup_workflow, 'workflow_max', node, k)
            if m:
                m = random_min_max(m)
                v = min(v, m)
            
            self.set_workflow(node, k, v)
    
    def set_workflow_func_random3(self, node: str, key_list: List[str], 
                                    func=None, random_func=None):
        """워크플로우에 랜덤 값을 설정합니다 (func는 node, k를 받음)."""
        for k in key_list:
            if func:
                v = func(node, k)
            else:
                v = None
            
            if random_func:
                v = random_func(v)
            
            if not v:
                continue
            
            self.set_workflow(node, k, v)
    
    def set_workflow_func_random(self, node: str, key_list: List[str], 
                                  func=None, random_func=None):
        """워크플로우에 랜덤 값을 설정합니다 (func는 k만 받음)."""
        for k in key_list:
            if func:
                v = func(k)
            else:
                v = None
            
            if random_func:
                v = random_func(v)
            
            if not v:
                continue
            
            self.set_workflow(node, k, v)
    
    def set_checkpoint_loader_simple(self):
        """CheckpointLoaderSimple을 설정합니다."""
        self.set_workflow('CheckpointLoaderSimple', 'ckpt_name', self.checkpoint_path)
        self.tive_checkpoint = self.get_now('dicCheckpointYml', self.checkpoint_name, default={})
    
    def set_ksampler_sub(self, v: Any, k: str) -> Any:
        """KSampler 서브 함수."""
        return self.get_now('dicCheckpointYml', self.checkpoint_name, k, default=v)
    
    def set_ksampler(self):
        """KSampler를 설정합니다."""
        self.set_workflow('KSampler', 'seed', seed_int())
        
        ksampler_inputs = get_nested(self.workflow_api, 'KSampler', "inputs", default={})
        l = get_type_list(ksampler_inputs, (int, float), (bool,))
        self.set_workflow_func_random2('KSampler', l, random_min_max, self.set_ksampler_sub)
        
        l = get_type_list(ksampler_inputs, (str, bool))
        self.set_workflow_func_random2('KSampler', l, random_weight, self.set_ksampler_sub)
    
    def set_setup_workflow_to_workflow_api(self):
        """워크플로우 API에 setupWorkflow.yml 값을 설정합니다."""
        exclude_nodes = set(self.get_config('excludeNode', []))
        workflow_nodes = set(self.workflow_api.keys()) - exclude_nodes
        
        for k in workflow_nodes:
            self.set_workflow(k, 'seed', seed_int())
            v = self.workflow_api.get(k, {})
            inputs = v.get("inputs", {})
            
            l = get_type_list(inputs, (int, float), (bool,))
            self.set_workflow_func_random2(k, l, random_min_max)
            
            l = get_type_list(inputs, (str, bool))
            self.set_workflow_func_random2(k, l, random_weight)
    
    def set_dic_checkpoint_yml_to_workflow_api_sub(self, node: str, k: str) -> Any:
        """Checkpoint YML을 워크플로우 API에 설정하는 서브 함수."""
        return self.get_now('dicCheckpointYml', self.checkpoint_name, node, k)
    
    def set_dic_checkpoint_yml_to_workflow_api(self):
        """Checkpoint YML을 워크플로우 API에 설정합니다."""
        dic_checkpoint_yml = self.get_now('dicCheckpointYml', self.checkpoint_name, default={})
        
        for k, v in dic_checkpoint_yml.items():
            if k in self.workflow_api:
                inputs = get_nested(self.workflow_api, k, "inputs", default={})
                l = get_type_list(inputs, (int, float), (bool,))
                self.set_workflow_func_random3(k, l, self.set_dic_checkpoint_yml_to_workflow_api_sub, random_min_max)
                
                l = get_type_list(inputs, (str, bool))
                self.set_workflow_func_random3(k, l, self.set_dic_checkpoint_yml_to_workflow_api_sub, random_weight)
    
    def set_save_image(self):
        """이미지 저장 설정을 합니다."""
        tcp = '+' if self.tive_checkpoint else ''
        tch = '+' if self.tive_char else ''
        
        ff = (f"{self.checkpoint_type}/"
               f"{self.checkpoint_name}{tcp}/"
               f"{self.char_name}{tch}/"
               f"{self.checkpoint_name}-{self.char_name}-"
               f"{time.strftime('%Y%m%d-%H%M%S')}-{self.total}")
        
        self.set_workflow('SaveImage1', 'filename_prefix', ff + "-1")
        self.set_workflow('SaveImage2', 'filename_prefix', ff + "-2")
        
        if self.get_config('noSaveImage1', False):
            from utils.dict_utils import pop_nested
            print('SaveImage1', pop_nested(self.workflow_api, 'SaveImage1', "inputs", 'images'))
    
    def set_tive(self, num_name: str, dic: Dict, reset: bool = False):
        """태그를 설정합니다."""
        if reset:
            self.positive_dics.pop(num_name, None)
            self.negative_dics.pop(num_name, None)
        
        if self.get_config("setTivePrint", False):
            print.Config('SetTive', num_name, dic)
        
        if dic:
            d = dic.get('positive')
            s = self.positive_dics.setdefault(num_name, {})
            update_dict(s, d)
            
            d = dic.get('negative')
            s = self.negative_dics.setdefault(num_name, {})
            update_dict(s, d)
        else:
            if self.get_config("setTivePrint", False):
                print.Warn(f'SetTive no: {num_name}')
    
    def set_wildcard(self):
        """Wildcard를 설정합니다."""
        self.positive_dics = {}
        self.negative_dics = {}
        
        self.set_tive('setup', self.get_now('setupWildcard', default={}), True)
        self.set_tive('Checkpoint', self.tive_checkpoint, True)
        self.set_tive('Char', self.tive_char, True)
        self.set_tive('Weight', self.tive_weight, True)
        self.set_tive('Lora', self.tive_lora, True)
        
        positive = {}
        negative = {}
        
        for k in self.get_config("SetWildcardSort", ['setup', 'Checkpoint', 'Char', 'Weight', 'Lora']):
            update_dict(positive, self.positive_dics.get(k, {}))
            update_dict(negative, self.negative_dics.get(k, {}))
        
        import yaml
        yaml_data = yaml.dump(positive, allow_unicode=True)
        self.set_workflow('PrimitiveStringMultilineP', 'value', yaml_data)
        
        yaml_data = yaml.dump(negative, allow_unicode=True)
        self.set_workflow('PrimitiveStringMultilineN', 'value', yaml_data)
        
        lpositive = list(positive.values())
        lpositive.insert(0, '/**/')
        lpositive.append('/**/')
        lnegative = list(negative.values())
        lnegative.insert(0, '/**/')
        lnegative.append('/**/')
        
        if random_weight(self.get_config("shuffleWildcard", [False, True])):
            if self.get_config("shuffleWildcardPrint", False):
                print.Config('positive', lpositive)
                print.Config('negative', lnegative)
            random.shuffle(lpositive)
            random.shuffle(lnegative)
            if self.get_config("shuffleWildcardPrint", False):
                print.Config('positive (shuffled)', lpositive)
                print.Config('negative (shuffled)', lnegative)
        
        positive_wildcard = ",".join(lpositive)
        negative_wildcard = ",".join(lnegative)
        
        if self.get_config("setWildcardDicPrint", False):
            print.Config('negativeDics', self.negative_dics)
            print.Config('positiveDics', self.positive_dics)
        if self.get_config("setWildcardTivePrint", False):
            print.Config('negative', negative)
            print.Config('positive', positive)
        if self.get_config("setWildcardPrint", False):
            print.Config('negativeWildcard', negative_wildcard)
            print.Config('positiveWildcard', positive_wildcard)
        
        self.set_workflow('positiveWildcard', 'wildcard_text', positive_wildcard)
        self.set_workflow('negativeWildcard', 'wildcard_text', negative_wildcard)
        self.set_workflow('positiveWildcard', 'seed', seed_int())
        self.set_workflow('negativeWildcard', 'seed', seed_int())
    
    def set_lora_sub(self, k: str) -> Any:
        """LoRA 서브 함수."""
        v = self.get_now('setupWorkflow', 'loraDefault', k)
        v = self.get_now('dicLoraYml', self.lora_tmp, k, default=v)
        return v
    
    def set_lora(self):
        """LoRA를 설정합니다."""
        lora_loader = get_nested(self.workflow_api, 'LoraLoader')
        lora_loader_next = lora_loader
        lora_loader_next_key = 'LoraLoader'
        lora_loader_key = 'LoraLoader'
        
        model_sampling_discrete = self.get_workflow(lora_loader_next_key, 'model')
        if isinstance(model_sampling_discrete, list):
            model_sampling_discrete = model_sampling_discrete[0]
        
        checkpoint_loader_simple = self.get_workflow(lora_loader_next_key, 'clip')
        if isinstance(checkpoint_loader_simple, list):
            checkpoint_loader_simple = checkpoint_loader_simple[0]
        
        if self.no_lora:
            self.tive_lora = self.get_config('noLoraWildcard', {})
        else:
            self.tive_lora = {}
            for self.lora_tmp in self.loras_set:
                if self.lora_tmp not in self.get_now('LoraFileNames', default=[]):
                    print.Warn('SetLora no', self.lora_tmp)
                    continue
                
                self.lora_num += 1
                
                dic = self.get_now('dicLoraYml', self.lora_tmp, default={})
                update_dict(self.tive_lora, dic)
                
                lora_loader_tmp_key = f'LoraLoader-{self.lora_tmp}'
                lora_loader_tmp = copy.deepcopy(lora_loader)
                set_nested(self.workflow_api, lora_loader_tmp, lora_loader_tmp_key)
                
                model_input = self.get_workflow(lora_loader_tmp_key, 'model')
                if isinstance(model_input, list):
                    model_input[0] = model_sampling_discrete
                
                clip_input = self.get_workflow(lora_loader_tmp_key, 'clip')
                if isinstance(clip_input, list):
                    clip_input[0] = checkpoint_loader_simple
                
                self.set_workflow(lora_loader_tmp_key, 'seed', seed_int())
                self.set_workflow(lora_loader_tmp_key, 'lora_name', 
                                  self.get_now('LoraFileDics', self.lora_tmp))
                
                self.set_workflow_func_random(lora_loader_tmp_key,
                                               ['strength_model', 'strength_clip', 'A', 'B'],
                                               self.set_lora_sub,
                                               random_min_max)
                self.set_workflow_func_random(lora_loader_tmp_key,
                                               ['preset', 'block_vector'],
                                               self.set_lora_sub,
                                               random_weight)
                
                model_input = self.get_workflow(lora_loader_next_key, 'model')
                if isinstance(model_input, list):
                    model_input[0] = lora_loader_tmp_key
                
                clip_input = self.get_workflow(lora_loader_next_key, 'clip')
                if isinstance(clip_input, list):
                    clip_input[0] = lora_loader_tmp_key
                
                lora_loader_next = lora_loader_tmp
                lora_loader_next_key = lora_loader_tmp_key
    
    def set_char_sub(self, k: str) -> Any:
        """Char 서브 함수."""
        return self.get_now('dicLoraYml', self.char_name, k,
                           default=self.get_now('setupWorkflow', 'charDefault', k))
    
    def set_char(self):
        """Char를 설정합니다."""
        self.set_workflow('LoraLoader', 'lora_name', self.char_path)
        self.set_workflow('LoraLoader', 'seed', seed_int())
        
        if self.no_char:
            self.set_workflow('LoraLoader', 'strength_model', 0.0)
            self.set_workflow('LoraLoader', 'strength_clip', 0.0)
            self.tive_char = self.get_config('noCharWildcard', {})
        else:
            self.set_workflow_func_random('LoraLoader',
                                          ['strength_model', 'strength_clip', 'A', 'B'],
                                          self.set_char_sub,
                                          random_min_max)
            self.set_workflow_func_random('LoraLoader',
                                          ['preset', 'block_vector'],
                                          self.set_char_sub,
                                          random_weight)
            self.tive_char = self.get_now('dicLoraYml', self.char_name, default={})
    
    def copy_workflow_api(self):
        """워크플로우 API를 복사합니다."""
        workflow_api = self.get_now('workflow_api', default={})
        if workflow_api:
            self.workflow_api = copy.deepcopy(workflow_api)
        else:
            self.workflow_api = {}
    
    def update_safetensors(self, path: Path, checkpoint_type: str, event_type: str,
                          config_key: str, dics_key: str, lists_key: str, names_key: str):
        """SafeTensors 파일 목록을 업데이트합니다."""
        config_path = Path(self.get_config(config_key))
        rpath = path.relative_to(config_path)
        name = rpath.stem
        print.Value(path, rpath, name)
        
        file_dics = self.get_now(dics_key, default={})
        file_lists = self.get_now(lists_key, default=[])
        file_names = self.get_now(names_key, default=[])
        spath = str(rpath)
        
        if event_type in ['deleted', 'modified']:
            file_dics.pop(name, None)
            if spath in file_lists:
                file_lists.remove(spath)
            if name in file_names:
                file_names.remove(name)
        
        if event_type in ['created', 'modified']:
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
    
    def run(self):
        """메인 실행 루프"""
        try:
            self.config_loader.reload()
            self.init(db=True)
            
            # 파일 감시 시작
            file_observer = FileObserver()
            file_observer.watch(
                self.get_config('dataPath'),
                FileEventHandler(self._data_path_callback),
                recursive=True
            )
            file_observer.watch(
                self.get_config('CheckpointPath'),
                FileEventHandler(self._checkpoint_path_callback),
                recursive=True
            )
            file_observer.watch(
                self.get_config('LoraPath'),
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
            self._loop()
            
        except KeyboardInterrupt:
            print.Warn('KeyboardInterrupt')
            logger.exception('KeyboardInterrupt')
        except Exception as e:
            logger.exception('Exception')
            print.exception(show_locals=True)
        finally:
            try:
                self.db.json_to_xlsx()
            except Exception as e:
                print.exception(show_locals=True)
            print.save_html()
            print.Info(' === finally === ')
    
    def _loop(self):
        """메인 루프"""
        while True:
            self.config_loader.reload()
            self.config = self.config_loader.config
            
            # 설정 확인
            if self.get_config('수정 안해서 작동 안시킴', False):
                print.Warn('---------------------------')
                print.Warn(f'{Path(self.get_config("dataPath"), "config.yml")} 끝까지 보세요')
                print.Warn('---------------------------')
                return
            
            self.lora_num = 0
            
            if self.checkpoint_loop_cnt == 0:
                try:
                    self.db.json_to_xlsx()
                except Exception as e:
                    print.exception(show_locals=True)
                
                self.checkpoint_change()
                self.checkpoint_loop_cnt += 1
                self.char_loop_cnt = 0
            
            self.copy_workflow_api()
            
            if self.char_loop_cnt == 0:
                self.char_change()
                self.char_loop_cnt += 1
                self.queue_loop_cnt = 0
            
            if self.queue_loop_cnt == 0:
                self.lora_change()
                self.queue_loop_cnt += 1
            
            # 워크플로우 설정
            self.set_setup_workflow_to_workflow_api()
            self.set_checkpoint_loader_simple()
            self.set_ksampler()
            self.set_dic_checkpoint_yml_to_workflow_api()
            self.set_char()
            self.set_lora()
            self.set_save_image()
            self.set_wildcard()
            
            if self.get_config("WorkflowPrint", False):
                print.Config('workflow_api', self.workflow_api)
            
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
                  f"{self.checkpoint_name}, "
                  f"{self.char_name}, "
                  f"{self.checkpoint_type}")
            
            self.db.update(self.checkpoint_type, self.checkpoint_name, self.char_name, self.loras_set)
            
            # 큐에 추가
            # 정상적으로 보냈을 경우 계속 반복, 실패했을 경우만 종료
            if not self._queue():
                return
            
            time.sleep(random_min_max(self.get_config("sleep", 1)))
            
            self.queue_loop_cnt += 1
            
            if self.queue_loop_cnt > self.queue_loop:
                self.queue_loop_cnt = 0
                self.char_loop_cnt += 1
            
            if self.char_loop_cnt > self.char_loop:
                self.char_loop_cnt = 0
                self.checkpoint_loop_cnt += 1
            
            if self.checkpoint_loop_cnt > self.checkpoint_loop:
                self.checkpoint_loop_cnt = 0
    
    def _queue(self) -> bool:
        """
        ComfyUI에 큐를 추가합니다.
        
        Returns:
            True: 정상적으로 전송됨 (계속 진행)
            False: 전송 실패 (루프 종료)
        """
        if self.get_config("queue_prompt", True):
            # queue_prompt가 성공(True)하면 계속 진행, 실패(False)하면 종료
            if not queue_prompt(self.workflow_api, url=self.get_config('url')):
                print.Err("프롬프트 전송 실패 - 루프 종료")
                return False
        
        if self.get_config("queue_prompt_wait", True):
            # queue_prompt_wait가 오류(True)면 종료, 정상(False)이면 계속 진행
            if queue_prompt_wait(url=self.get_config('url')):
                print.Err("큐 대기 중 오류 발생 - 루프 종료")
                return False
        else:
            print.Info("queue_prompt_wait 비활성화됨")
        
        # 정상적으로 전송 완료
        return True
    
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
            config_path = self.get_config('CheckpointPath')
            
            if fnmatch.fnmatch(str(path), str(Path(config_path) / '*.safetensors')):
                print.Value('CheckpointPathCallback', event)
                rel = path.relative_to(Path(config_path))
                
                if len(rel.parts) >= 1:
                    r0 = rel.parts[0]
                    if r0 not in self.checkpoint_types:
                        if self.get_config('CallbackPrint', False):
                            print.Warn('CheckpointPath type', path.parts)
                        return
                    
                    if len(rel.parts) == 2:
                        print.Value('CheckpointPath ok', event, rel)
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
            config_path = self.get_config('LoraPath')
            
            if fnmatch.fnmatch(str(path), str(Path(config_path) / '*.ffs_db')) or \
               fnmatch.fnmatch(str(path), str(Path(config_path) / '*.ffs_lock')) or \
               fnmatch.fnmatch(str(path), str(Path(config_path) / '*.ffs_tmp')):
                return
            
            if fnmatch.fnmatch(str(path), str(Path(config_path) / '*.safetensors')):
                print.Value('LoraPathCallback', event)
                rel = path.relative_to(Path(config_path))
                
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
                            self.update_safetensors_char(path, r0, event.event_type)
                            return
                        if rel.parts[1] == 'etc':
                            print.Value('LoraPath etc ok', event)
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

