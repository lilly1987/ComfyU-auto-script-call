# -*- coding: utf-8 -*-
import yaml
import random
import time
from typing import Any, List, Dict
from utils.dict_utils import get_nested, set_exists, update_dict, pop_nested
from utils.random_utils import random_min_max, random_weight, seed_int
from utils.type_utils import get_type_list
from utils.print_log import print

class WorkflowMixin:
    """ComfyUI 워크플로우 수정을 담당하는 Mixin"""

    def apply_workflow_settings(self, node: str, keys: List[str], value_func=None, random_func=random_min_max):
        """워크플로우 노드에 설정값과 랜덤 가중치를 일괄 적용합니다."""
        setup = self.get_now('setupWorkflow', default={})
        for k in keys:
            val = self.get_workflow(node, k)
            if value_func: val = value_func(node, k) if value_func.__code__.co_argcount == 2 else value_func(k)
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

    def set_checkpoint_loader_simple(self):
        self.set_exists_workflow('CheckpointLoaderSimple', 'ckpt_name', self.checkpoint_path)
        if not self.fromImg:
            self.yml_checkpoint = self.get_now('dicCheckpointYml', self.checkpoint_name, default={})

    def set_ksampler(self):
        self.set_exists_workflow('KSampler', 'seed', seed_int())
        inputs = get_nested(self.workflow_api, 'KSampler', "inputs", default={})
        func = lambda k: self.get_now('dicCheckpointYml', self.checkpoint_name, k)
        self.apply_workflow_settings('KSampler', get_type_list(inputs, (int, float), (bool,)), value_func=func)
        self.apply_workflow_settings('KSampler', get_type_list(inputs, (str, bool)), value_func=func, random_func=random_weight)

    def set_char(self):
        self.set_exists_workflow('LoraLoader', 'lora_name', self.char_path)
        if self.fromImg: return
        self.set_exists_workflow('LoraLoader', 'seed', seed_int())
        if self.no_char:
            self.set_exists_workflow('LoraLoader', 'strength_model', 0.0)
            self.set_exists_workflow('LoraLoader', 'strength_clip', 0.0)
        else:
            func = lambda k: self.get_now('dicLoraYml', self.char_name, k, default=self.get_now('setupWorkflow', 'charDefault', k))
            self.apply_workflow_settings('LoraLoader', ['strength_model', 'strength_clip', 'A', 'B'], value_func=func)
            self.apply_workflow_settings('LoraLoader', ['preset', 'block_vector'], value_func=func, random_func=random_weight)

    def set_wildcard(self):
        if self.fromImg: return
        self.positive_dics, self.negative_dics = {}, {}
        if self.yml_checkpoint.get('Setup', True): self.set_tive('setup', self.get_now('setupWildcard', default={}))
        self.set_tive('Checkpoint', self.yml_checkpoint)
        self.set_tive('Char', self.get_now('CharWildcard') if self.no_char else self.get_now('dicLoraYml', self.char_name, default={}))
        self.set_tive('Weight', self.tive_weight)
        self.set_tive('Lora', self.tive_lora)

        pos_f, neg_f = {}, {}
        for k in self.get_config("SetWildcardSort", ['setup', 'Checkpoint', 'Char', 'Weight', 'Lora']):
            update_dict(pos_f, self.positive_dics.get(k, {})); update_dict(neg_f, self.negative_dics.get(k, {}))

        self.set_exists_workflow('PrimitiveStringMultilineP', 'value', yaml.dump(pos_f, allow_unicode=True))
        self.set_exists_workflow('PrimitiveStringMultilineN', 'value', yaml.dump(neg_f, allow_unicode=True))

        p_list, n_list = list(pos_f.values()), list(neg_f.values())
        if random_weight(self.get_config("shuffleWildcard", [False, True])):
            random.shuffle(p_list); random.shuffle(n_list)
        
        self.set_exists_workflow('positiveWildcard', 'wildcard_text', f",,,,{','.join(p_list)},,,,")
        self.set_exists_workflow('negativeWildcard', 'wildcard_text', f",,,,{','.join(n_list)},,,,")
        self.set_exists_workflow('positiveWildcard', 'seed', seed_int())
        self.set_exists_workflow('negativeWildcard', 'seed', seed_int())

    def set_save_image(self):
        ts = time.strftime('%Y%m%d-%H%M%S')
        if self.fromImg:
            prefix = f"{self.checkpoint_type}/{self.checkpoint_name}/{self.char_name}/{self.checkpoint_name}-{self.char_name}-{ts}-{self.total}"
        else:
            tcp = '=' if self.yml_checkpoint.get('skip') not in (False, None) else '+'
            tch = '=' if not self.no_char and self.get_now('dicLoraYml', self.char_name, default={}).get('skip') not in (False, None) else '+'
            cpw, chw = self.yml_checkpoint.get('weight', ''), (self.get_now('dicLoraYml', self.char_name, default={}).get('weight', '') if not self.no_char else '')
            st = ("S" if getattr(self, 'IsStyleLora', False) else "") + ("D" if getattr(self, 'IsDressLora', False) else "")
            prefix = (f"{self.checkpoint_type}/{self.checkpoint_name}{tcp}{cpw}/{self.char_name}{tch}{chw}/"
                      f"{self.checkpoint_name}{tcp}-{self.char_name}{tch}-{st}-{len(self.loras_set)}-{ts}-{self.total}")

        for i in ['1', '2']: self.set_exists_workflow(f'SaveImage{i}', 'filename_prefix', f"{prefix}-{i}")
        self.set_exists_workflow('SaveVideo', 'filename_prefix', prefix)
        if self.get_config('noSaveImage1', False): pop_nested(self.workflow_api, 'SaveImage1', "inputs", 'images')

    def set_setup_workflow_to_workflow_api(self):
        if self.fromImg: return
        exclude = set(self.get_config('excludeNode', []))
        for node_id in (set(self.workflow_api.keys()) - exclude):
            self.set_exists_workflow(node_id, 'seed', seed_int())
            inputs = self.workflow_api[node_id].get("inputs", {})
            self.apply_workflow_settings(node_id, get_type_list(inputs, (int, float), (bool,)))
            self.apply_workflow_settings(node_id, get_type_list(inputs, (str, bool)), random_func=random_weight)

    def set_dic_checkpoint_yml_to_workflow_api(self):
        if self.fromImg: return
        dic = self.get_now('dicCheckpointYml', self.checkpoint_name, default={})
        for k, v in dic.items():
            if k in self.workflow_api:
                inputs = self.workflow_api[k].get("inputs", {})
                func = lambda node, key: self.get_now('dicCheckpointYml', self.checkpoint_name, node, key)
                self.apply_workflow_settings(k, get_type_list(inputs, (int, float), (bool,)), value_func=func)
                self.apply_workflow_settings(k, get_type_list(inputs, (str, bool)), value_func=func, random_func=random_weight)