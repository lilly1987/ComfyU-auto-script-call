# -*- coding: utf-8 -*-
import random
import json
from pathlib import Path
from urllib import request as urllib_request
from typing import List, Optional, Set, Dict, Any
from PIL import Image
from utils.random_utils import random_weight_count, random_min_max, random_weight, random_dict_weight, random_items_count
from utils.dict_utils import update_dict_key
from utils.print_log import print, logger

class SelectorMixin:
    """모델 및 리소스 선택 로직을 담당하는 Mixin"""

    def checkpoint_change(self):
        """Checkpoint를 선택합니다."""
        checkpoint_types = self.get_config('CheckpointTypes', {})
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            if self.is_first:
                self.is_first = False
                safetensors_start = self.get_config('safetensorsStart')
                if safetensors_start:
                    p = Path(safetensors_start)
                    if len(p.parts) >= 2 and p.parts[0] in checkpoint_types:
                        self.checkpoint_type = p.parts[0]
                        self.checkpoint_name = p.stem
                        self.checkpoint_path = self.get_now('CheckpointFileDics', self.checkpoint_name)
                        if self.checkpoint_path: return

            get_kind = self.get_config('GetCheckpointKind', {'Weight': 1, 'Random': 1})
            self.checkpoint_kind = random_weight_count(get_kind)[0]
            
            self.fromImg = False
            if self.checkpoint_kind == 'fromImg':
                self.fromImg = True
                temp_kinds = dict(get_kind)
                temp_kinds.pop('fromImg', None)
                self.checkpoint_kind = random_weight_count(temp_kinds)[0] if temp_kinds else 'Weight'

            self.checkpoint_type = random_weight_count(checkpoint_types)[0]
            names = self.get_now('CheckpointFileNames', default=[])
            
            if not names:
                retry_count += 1
                continue

            if self.checkpoint_kind == 'DB' and self.db:
                counts = self.db.get_checkpoint_counts(self.checkpoint_type)
                max_w, min_w = self.get_config('CheckpointDbWeightMax', 100), self.get_config('CheckpointDbWeightMin', 1)
                db_weights = {n: max(min_w, min(max_w - counts.get(n, 0), max_w)) for n in names}
                self.checkpoint_name = random_weight_count(db_weights)[0]
            elif self.checkpoint_kind == 'Cycle':
                selected = self._cycle_sample('CheckpointCyclePool', names, 1)
                self.checkpoint_name = selected[0] if selected else random.choice(names)
            else: # Weight / Random
                weight_map = self.get_now('WeightCheckpoint', default={})
                if self.get_config('CheckpointWeightPer', 0.5) > random.random() and weight_map:
                    self.checkpoint_name = random_weight_count(weight_map)[0]
                else:
                    self.checkpoint_name = random.choice(names)

            self.checkpoint_path = self.get_now('CheckpointFileDics', self.checkpoint_name)
            if self.checkpoint_path: return
            retry_count += 1

    def char_change(self):
        """캐릭터(Character)를 선택합니다."""
        if self.fromImg:
            if self._handle_from_img_mode(): return
            self.fromImg = False # 실패 시 일반 모드로 전환

        get_kind = self.get_config('GetCharKind', {'Weight': 1, 'Random': 1})
        self.char_kind = random_weight_count(get_kind)[0]
        names = self.get_now('CharFileNames', default=[])
        
        selected_name = None
        if self.char_kind == 'Wildcard' or not names:
            self._apply_selected_char(None, use_wildcard=True)
            return

        if self.char_kind == 'Favorites':
            favs = [n for n in names if self.get_now('dicLoraYml', n, default={}).get('favorites')]
            selected_name = random.choice(favs) if favs else None
        elif self.char_kind == 'DB' and self.db:
            counts = self.db.get_char_counts(self.checkpoint_type)
            max_w, min_w = self.get_config('CharDbWeightMax', 100), self.get_config('CharDbWeightMin', 1)
            db_weights = {n: max(min_w, min(max_w - counts.get(n, 0), max_w)) for n in names}
            selected_name = random_weight_count(db_weights)[0]
        elif self.char_kind == 'Cycle':
            selected = self._cycle_sample('CharCyclePool', names, 1)
            selected_name = selected[0] if selected else None
        
        if not selected_name: # Fallback
            weight_char = self.get_now('WeightChar', default={})
            if self.get_config('CharWeightPer', 0.5) > random.random() and weight_char:
                selected_name = random_weight_count(weight_char)[0]
            else:
                selected_name = random.choice(names) if names else None

        self._apply_selected_char(selected_name)

    def _apply_selected_char(self, name: Optional[str], use_wildcard: bool = False):
        if use_wildcard or not name:
            self.no_char = True
            self.char_name = 'Wildcard'
            all_chars = self.get_now('CharFileNames', default=[])
            self.char_path = self.get_now('CharFileDics', random.choice(all_chars)) if all_chars else None
        else:
            self.no_char = False
            self.char_name = name
            self.char_path = self.get_now('CharFileDics', name)

    def lora_change(self):
        """LoRA 목록을 선택합니다."""
        if self.fromImg: return
        
        self.tive_weight = {}
        self.loras_set = set()
        self.lora_kind = random_weight_count(self.get_config('GetLoraKind', {'Weight': 1, 'Random': 1}))[0]

        if self.lora_kind == 'Wildcard':
            self.tive_lora = self.get_now('LoraWildcard', default={})
            return

        names = self.get_now('LoraFileNames', default=[])
        if not names: return

        if self.lora_kind == 'DB' and self.db:
            counts = self.db.get_lora_counts(self.checkpoint_type)
            max_w, min_w = self.get_config('LoraDbWeightMax', 100), self.get_config('LoraDbWeightMin', 1)
            db_weights = {n: max(min_w, min(max_w - counts.get(n, 0), max_w)) for n in names}
            cnt = random_min_max(self.get_config('LoraDbCnt', [1, 3]))
            self.loras_set = set(random_weight_count(db_weights, count=min(cnt, len(db_weights))))
        elif self.lora_kind in ['Random', 'Cycle']:
            cnt = random_min_max(self.get_config('LoraRandomCnt', [1, 3]))
            if self.lora_kind == 'Random':
                self.loras_set = set(random.sample(list(names), min(cnt, len(names))))
            else:
                self.loras_set = set(self._cycle_sample('LoraCyclePool', names, cnt))
        elif self.lora_kind == 'Weight':
            self._lora_change_weight()

        for lora in self.loras_set:
            dic = self.get_now('dicLoraYml', lora, default={})
            update_dict_key(self.tive_weight, dic, 'positive')
            update_dict_key(self.tive_weight, dic, 'negative')

    def _lora_change_weight(self):
        weight_lora = self.get_now('WeightLora', default={})
        for g_name, g_cfg in weight_lora.items():
            dic = g_cfg.get('dic', {})
            temp_map = {}
            if g_cfg.get('per'):
                limit = random_min_max(g_cfg.get('perMax', 0))
                count = 0
                for k, v in dic.items():
                    if g_cfg.get('perFirsts') and count >= limit: break
                    if v.get('per', 0) > random.random():
                        count += 1
                        lora = random_weight(v.get('loras')) if v.get('loras') else f"{g_name}-{k}"
                        temp_map[lora] = v
            
            if g_cfg.get('weight'):
                limit = random_min_max(g_cfg.get('weightMax', 0))
                for k in random_dict_weight(dic, 'weight', limit):
                    v = dic[k]
                    lora = random_weight(v.get('loras')) if v.get('loras') else f"{g_name}-{k}"
                    temp_map[lora] = v

            selected = set(random_items_count(temp_map, random_min_max(g_cfg.get('totalMax', 0)))) if g_cfg.get('total') else set(temp_map.keys())
            self.loras_set.update(selected)

    def _handle_from_img_mode(self) -> bool:
        max_retries = self.get_config('fromImgMaxRetries', 50)
        for _ in range(max_retries):
            img_path = self._select_from_img()
            if not img_path: continue
            prompt = self._extract_prompt_from_png(img_path)
            if not prompt or 'CheckpointLoaderSimple' not in prompt: continue
            
            lora_list = self._get_loras_model_list()
            all_valid = True
            for node in prompt.values():
                if isinstance(node, dict) and str(node.get('class_type')).startswith('LoraLoader'):
                    inputs = node.get('inputs', {})
                    lname = inputs.get('lora_name')
                    if lname and not self._validate_lora_file(lname):
                        matches = [m for m in lora_list if Path(m).name == Path(lname).name]
                        if matches: inputs['lora_name'] = matches[0]
                        else: all_valid = False; break
            
            if all_valid:
                self.workflow_api = prompt
                self.from_img_path = img_path
                _, _, char_name = self._extract_checkpoint_and_char_from_workflow(prompt)
                if char_name: self.char_name, self.no_char = char_name, False
                else: self.char_name, self.no_char = 'fromImg', True
                return True
        return False

    def _select_from_img(self, exclude: Optional[Set[str]] = None) -> Optional[str]:
        path = Path(self.get_config('fromImg', ''))
        if not path.exists(): return None
        ex = {str(Path(p)) for p in exclude} if exclude else set()
        files = [p for p in path.rglob('*.png') if str(p) not in ex]
        return str(random.choice(files)) if files else None

    def _extract_prompt_from_png(self, image_path: str) -> Optional[Dict]:
        try:
            with Image.open(image_path) as img:
                if 'prompt' in img.info:
                    p = img.info['prompt']
                    return json.loads(p) if isinstance(p, str) else p
        except Exception as e: logger.error(f"Prompt extract error: {e}")
        return None

    def _validate_lora_file(self, lora_name: str) -> bool:
        p = Path(self.get_config('base_dir'), self.get_config('LoraPath'), lora_name)
        return p.exists()

    def _get_loras_model_list(self) -> List[str]:
        return self._get_model_list('/models/loras')

    def _get_model_list(self, endpoint: str) -> List[str]:
        url = f"{self.get_config('url2', 'http://127.0.0.1:8188').rstrip('/')}{endpoint}"
        try:
            with urllib_request.urlopen(url, timeout=5) as res:
                data = json.loads(res.read().decode('utf-8'))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get('models', list(data.values()))
        except Exception as e:
            logger.warning(f"Failed to fetch model list from {url}: {e}")
        return []

    def _extract_checkpoint_and_char_from_workflow(self, workflow: Dict) -> tuple:
        ct, cn, chn = None, None, None
        for node in workflow.values():
            if not isinstance(node, dict): continue
            inputs = node.get('inputs', {})
            if 'ckpt_name' in inputs and not ct:
                p = Path(inputs['ckpt_name'].replace('\\', '/'))
                if len(p.parts) >= 2: ct, cn = p.parts[0], p.stem
            if 'lora_name' in inputs and not chn:
                ln = inputs['lora_name'].lower()
                if 'char' in ln:
                    p = Path(ln.replace('\\', '/'))
                    idx = p.parts.index('char')
                    if idx + 1 < len(p.parts): chn = Path(p.parts[idx+1]).stem
        return ct, cn, chn

    def _sync_model_names(self, workflow: Dict):
        """워크플로우 내의 특정 노드 모델 경로를 실제 API 목록과 동기화합니다."""
        endpoints = {'UltralyticsDetectorProvider': '/models/ultralytics', 'SAMLoader': '/models/sams'}
        model_cache = {}
        
        for node in workflow.values():
            if not isinstance(node, dict): continue
            class_type = node.get('class_type')
            
            if class_type in endpoints:
                endpoint = endpoints[class_type]
                if endpoint not in model_cache:
                    model_cache[endpoint] = self._get_model_list(endpoint)
                
                m_list = model_cache[endpoint]
                inputs = node.get('inputs', {})
                name = Path(inputs.get('model_name', '')).name
                matches = [m for m in m_list if Path(m).name == name]
                if matches: inputs['model_name'] = matches[0]
