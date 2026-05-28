# -*- coding: utf-8 -*-
import yaml
import random
import time
import copy
from pathlib import Path
from typing import Any, List, Dict
from utils.dict_utils import get_nested, set_exists, add_exists, update_dict, pop_nested
from utils.random_utils import random_min_max, random_weight, seed_int
from utils.type_utils import get_type_list
from utils.print_log import print, logger

class WorkflowMixin:
    """ComfyUI 워크플로우 수정을 담당하는 Mixin"""

    def copy_workflow_api(self):

        if self.fromImg: 
            
            return
        self.workflow_api = copy.deepcopy(self.get_now('workflow_api', default={}))

    def set_tive(self, num_name: str, dic: Dict, reset: bool = False):
        if reset:
            self.positive_dics.pop(num_name, None); self.negative_dics.pop(num_name, None)
        if dic:
            for key in ['positive', 'negative']:
                target = self.positive_dics if key == 'positive' else self.negative_dics
                update_dict(target.setdefault(num_name, {}), dic.get(key))

    def apply_workflow_settings(self, node: str, keys: List[str], value_func=None, random_func=random_min_max):
        """워크플로우 노드에 설정값과 랜덤 가중치를 일괄 적용합니다."""
        setup = self.get_now('setupWorkflow', default={})
        for k in keys:
            val = self.get_workflow(node, k)
            if value_func:
                # Bound methods include 'self' in co_argcount, so we adjust the count check
                c = value_func.__code__.co_argcount - (1 if hasattr(value_func, '__self__') else 0)
                val = value_func(node, k) if c == 2 else value_func(k)
            val = get_nested(setup, 'workflow', node, k, default=val)
            if random_func and val is not None: val = random_func(val)
            if val is None: continue

            for meta in ['scale', 'min', 'max']:
                m_val = get_nested(setup, f'workflow_{meta}', node, k)
                if m_val:
                    m_val = random_min_max(m_val)
                    if meta == 'scale': val *= m_val
                    elif meta == 'min': val = max(val, m_val)
                    elif meta == 'max': val = min(val, m_val)
            self.set_exists_workflow(node, k, val)

    def set_exists_workflow(self, node: str, key: str, value: Any) -> bool:
        return set_exists(self.workflow_api, value, node, "inputs", key) is not None

    def add_exists_workflow(self, node: str, key: str, value: Any) -> bool:
        """워크플로우 노드의 기존 값에 새로운 내용을 추가합니다 (주로 문자열 누적용)."""
        return add_exists(self.workflow_api, value, node, "inputs", key) is not None

    def set_checkpoint_loader_simple(self):
        self.set_exists_workflow('CheckpointLoaderSimple', 'ckpt_name', self.checkpoint_path)
        # 정보성 텍스트 초기화 및 체크포인트 경로 기록
        self.set_exists_workflow('PrimitiveStringMultilineInfo', 'value', str(self.checkpoint_kind) + " \n")
        self.add_exists_workflow('PrimitiveStringMultilineInfo', 'value', str(self.checkpoint_path) + " \n")
        if not self.fromImg:
            self.yml_checkpoint = self.get_now('dicCheckpointYml', self.checkpoint_name, default={})

    def set_ksampler(self):
        # self.set_exists_workflow('KSampler', 'seed', seed_int())
        inputs = get_nested(self.workflow_api, 'KSampler', "inputs", default={})
        func = lambda k: self.get_now('dicCheckpointYml', self.checkpoint_name, k)
        self.apply_workflow_settings('KSampler', get_type_list(inputs, (int, float), (bool,)), value_func=func)
        self.apply_workflow_settings('KSampler', get_type_list(inputs, (str, bool)), value_func=func, random_func=random_weight)

    def set_char(self):
        if not self.fromImg: 
            self.set_exists_workflow('LoraLoader', 'lora_name', self.char_path)
        # 캐릭터 LoRA 경로 추가
        self.add_exists_workflow('PrimitiveStringMultilineInfo', 'value', str(self.char_kind) + " \n")
        self.add_exists_workflow('PrimitiveStringMultilineInfo', 'value', str(self.char_path) + " \n")
        # self.set_exists_workflow('LoraLoader', 'seed', seed_int())
        if self.no_char:
            self.set_exists_workflow('LoraLoader', 'strength_model', 0.0)
            self.set_exists_workflow('LoraLoader', 'strength_clip', 0.0)
        else:
            func = lambda k: self.get_now('dicLoraYml', self.char_name, k, default=self.get_now('setupWorkflow', 'charDefault', k))
            self.apply_workflow_settings('LoraLoader', ['strength_model', 'strength_clip', 'A', 'B'], value_func=func)
            self.apply_workflow_settings('LoraLoader', ['preset', 'block_vector'], value_func=func, random_func=random_weight)

    def set_lora_sub(self, k: str) -> Any:
        v = self.get_now('setupWorkflow', 'loraDefault', k)
        return self.get_now('dicLoraYml', self.lora_tmp, k, default=v)

    def set_lora(self):
        if self.lora_kind != 'Wildcard':
            self.tive_lora = {}
        
        if self.fromImg:
            self._from_img_char_is_wildcard = False
            for node_id, node_cfg in self.workflow_api.items():
                inputs = node_cfg.get('inputs', {})
                class_type = str(node_cfg.get('class_type', ''))
                if class_type.startswith('LoraLoader'):
                    if node_id == 'LoraLoader' and self._is_disabled_lora_loader(inputs):
                        self._from_img_char_is_wildcard = True
                    lname = inputs.get('lora_name')
                    if lname:
                        self.lora_tmp = Path(lname).stem
                        for k in ['strength_model', 'strength_clip', 'A', 'B']:
                            v = self.set_lora_sub(k)
                            if v is not None: inputs[k] = random_min_max(v)
            return
        lora_loader_node = get_nested(self.workflow_api, 'LoraLoader')
        if not lora_loader_node: return
        
        next_key = 'LoraLoader' # 다른 노드들이 다 참조함.
        dic_cp = self.get_now('dicCheckpointYml', self.checkpoint_name, default={})
        h_model_conn = ['ModelSamplingDiscrete', 0] if isinstance(dic_cp.get('ModelSamplingDiscrete'), dict) else self.get_workflow(next_key, 'model')
        h_clip_conn = ['CLIPSetLastLayer', 0] if isinstance(dic_cp.get('CLIPSetLastLayer'), dict) else self.get_workflow(next_key, 'clip')

        
        self.IsStyleLora, self.IsDressLora = False, False

        for lora in self.loras_set:
            if lora not in self.get_now('LoraFileNames', default=[]): continue
            self.lora_num += 1
            self.lora_tmp = lora
            dic = self.get_now('dicLoraYml', lora, default={})
            tags = [str(x).lower() for x in dic.get('tag', [])]
            if 'style' in tags: self.IsStyleLora = True
            if 'dress' in tags: self.IsDressLora = True
            update_dict(self.tive_lora, dic)
            
            tmp_key = f'LoraLoader{self.lora_num}'
            self.workflow_api[tmp_key] = copy.deepcopy(lora_loader_node)
            self.set_exists_workflow(tmp_key, 'model', h_model_conn)
            self.set_exists_workflow(tmp_key, 'clip', h_clip_conn)
            # self.set_exists_workflow(tmp_key, 'seed', seed_int())
            self.set_exists_workflow(tmp_key, 'lora_name', self.get_now('LoraFileDics', lora))
            # 추가된 LoRA 경로들 기록
            self.add_exists_workflow('PrimitiveStringMultilineInfo', 'value', str(self.lora_kind) + " \n")
            self.add_exists_workflow('PrimitiveStringMultilineInfo', 'value', str(self.get_now('LoraFileDics', lora)) + " \n")
            
            self.apply_workflow_settings(tmp_key, ['strength_model', 'strength_clip', 'A', 'B'], value_func=self.set_lora_sub)
            self.apply_workflow_settings(tmp_key, ['preset', 'block_vector'], value_func=self.set_lora_sub, random_func=random_weight)
            
            model_conn, clip_conn = [tmp_key, 0], [tmp_key, 1]
            self.set_exists_workflow(next_key, 'model', model_conn)
            self.set_exists_workflow(next_key, 'clip', clip_conn)
            next_key = tmp_key
            # print.Info(f"{tmp_key} / model_conn: {model_conn} / clip_conn: {clip_conn}")
            # print.Info(f"{next_key} / model_conn: {model_conn} / clip_conn: {clip_conn}")

    def set_seed(self):
        
        for node_id, node_cfg in self.workflow_api.items():
            if not isinstance(node_cfg, dict): continue
            inputs = node_cfg.get('inputs', {})
            if 'seed' in inputs: inputs['seed'] = seed_int()

    def set_wildcard(self):
        
        self.positive_dics, self.negative_dics = {}, {}
        pos_f, neg_f = {}, {}

        # if self.get_config("wildcardPrint", False):
        #     print.Config('workflow_api', self.positive_dics)  

        if self.fromImg: 
            self.set_exists_workflow('PrimitiveStringMultilineP', 'value', yaml.dump(pos_f, allow_unicode=True))
            self.set_exists_workflow('PrimitiveStringMultilineN', 'value', yaml.dump(neg_f, allow_unicode=True))
            return
        
        if self.yml_checkpoint.get('Setup', True): self.set_tive('setup', self.get_now('setupWildcard', default={}))
        self.set_tive('Checkpoint', self.yml_checkpoint)
        self.set_tive('Char', self.get_now('CharWildcard') if self.no_char else self.get_now('dicLoraYml', self.char_name, default={}))
        self.set_tive('Weight', self.tive_weight)
        self.set_tive('Lora', self.tive_lora)

        for k in self.get_config("SetWildcardSort", ['setup', 'Checkpoint', 'Char', 'Weight', 'Lora']):
            print.Config(k,self.positive_dics.get(k, {}))
            update_dict(pos_f, self.positive_dics.get(k, {})); 
            update_dict(neg_f, self.negative_dics.get(k, {}))


        self.set_exists_workflow('PrimitiveStringMultilineP', 'value', yaml.dump(pos_f, allow_unicode=True))
        self.set_exists_workflow('PrimitiveStringMultilineN', 'value', yaml.dump(neg_f, allow_unicode=True))

        p_list, n_list = list(pos_f.values()), list(neg_f.values())
        if random_weight(self.get_config("shuffleWildcard", [False, True])):
            random.shuffle(p_list); random.shuffle(n_list)
            
    
        self.set_exists_workflow('positiveWildcard', 'wildcard_text', f",,,,{','.join(p_list)},,,,")
        self.set_exists_workflow('negativeWildcard', 'wildcard_text', f",,,,{','.join(n_list)},,,,")
        # self.set_exists_workflow('positiveWildcard', 'seed', seed_int())
        # self.set_exists_workflow('negativeWildcard', 'seed', seed_int())
    
        # logger.info(f"Positive Wildcard: {p_list}")
        # logger.info(f"Negative Wildcard: {n_list}")
        # print.Info(f"Positive Wildcard",p_list)
        # print.Info(f"Negative Wildcard",n_list)

    def _is_zero_strength(self, value: Any) -> bool:
        try:
            return float(value) == 0.0
        except (TypeError, ValueError):
            return False

    def _is_disabled_lora_loader(self, inputs: Dict) -> bool:
        return (
            self._is_zero_strength(inputs.get('strength_model')) or
            self._is_zero_strength(inputs.get('strength_clip'))
        )

    def _apply_from_img_char_name_for_save(self):
        if getattr(self, '_from_img_char_is_wildcard', False):
            self.char_name = 'wildcard'
            self.no_char = True
            return

        node = get_nested(self.workflow_api, 'LoraLoader')
        if isinstance(node, dict) and self._is_disabled_lora_loader(node.get('inputs', {})):
            self.char_name = 'wildcard'
            self.no_char = True

    def set_save_image(self):
        # 모델 경로 보정 (모드 상관 없이 큐 전송 전 항상 수행)
        
        ts = time.strftime('%Y%m%d-%H%M%S')
        if self.fromImg:
            self._apply_from_img_char_name_for_save()
            prefix = f"{self.checkpoint_type}/{self.checkpoint_name}/{self.char_name}/{self.checkpoint_name}-{self.char_name}-{ts}-{self.total}"
        else:
            tcp = '=' if self.yml_checkpoint.get('skip') not in (False, None) else '+'
            tch = '=' if not self.no_char and self.get_now('dicLoraYml', self.char_name, default={}).get('skip') not in (False, None) else '+'
            tfv = '#' if not self.no_char and self.get_now('dicLoraYml', self.char_name, default={}).get('favorites') not in (False, None) else tch
            cpw = self.yml_checkpoint.get('weight', '')
            chw = self.get_now('dicLoraYml', self.char_name, default={}).get('weight', '') if not self.no_char else ''
            st = ("S" if getattr(self, 'IsStyleLora', False) else "") + ("D" if getattr(self, 'IsDressLora', False) else "")
            prefix = (f"{self.checkpoint_type}/{self.checkpoint_name}{tcp}{cpw}/{self.char_name}{tfv}{chw}/"
                      f"{self.checkpoint_name}{tcp}-{self.char_name}{tch}-{st}-{len(self.loras_set)}-{ts}-{self.total}")

        for i in ['1', '2']: self.set_exists_workflow(f'SaveImage{i}', 'filename_prefix', f"{prefix}-{i}")
        self.set_exists_workflow('SaveVideo', 'filename_prefix', prefix)
        if self.get_config('noSaveImage1', False): pop_nested(self.workflow_api, 'SaveImage1') 

    def set_setup_workflow_to_workflow_api(self):
        # if self.fromImg: return
        exclude = set(self.get_config('excludeNode', []))
        for node_id in (set(self.workflow_api.keys()) - exclude):
            # self.set_exists_workflow(node_id, 'seed', seed_int())
            inputs = self.workflow_api[node_id].get("inputs", {})
            self.apply_workflow_settings(node_id, get_type_list(inputs, (int, float), (bool,)))
            self.apply_workflow_settings(node_id, get_type_list(inputs, (str, bool)), random_func=random_weight)

    def set_dic_checkpoint_yml_to_workflow_api(self):
        # if self.fromImg: return
        dic = self.get_now('dicCheckpointYml', self.checkpoint_name, default={})
        for k, v in dic.items():
            if k in self.workflow_api:
                inputs = self.workflow_api[k].get("inputs", {})
                func = lambda node, key: self.get_now('dicCheckpointYml', self.checkpoint_name, node, key)
                self.apply_workflow_settings(k, get_type_list(inputs, (int, float), (bool,)), value_func=func)
                self.apply_workflow_settings(k, get_type_list(inputs, (str, bool)), value_func=func, random_func=random_weight)
