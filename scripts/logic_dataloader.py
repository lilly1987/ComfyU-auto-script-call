# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Dict, List, Any, Tuple
from itertools import islice
from utils.dict_utils import get_nested, set_nested, update_dict
from utils.file_handler import get_file_dict_list
from utils.print_log import print

class DataLoaderMixin:
    """데이터 로딩 및 초기화를 담당하는 Mixin"""

    def init(self, delete: bool = True, db: bool = False):
        """전체 데이터를 초기화합니다."""
        if db:
            self.db.init(self.get_config('dataPath'))
        
        for checkpoint_type in self.checkpoint_types:
            self.type_dics[checkpoint_type] = {}
            self._get_safetensors_checkpoint(checkpoint_type)
            self._get_safetensors_char(checkpoint_type)
            self._get_safetensors_etc(checkpoint_type)
            self._load_wildcards()
            self._get_setup_wildcard(checkpoint_type)
            self._get_setup_workflow(checkpoint_type)
            self._get_weight_checkpoint(checkpoint_type)
            self._get_weight_lora(checkpoint_type, delete)
            self._get_weight_char(checkpoint_type)
            self._get_dic_checkpoint_yml(checkpoint_type)
            self._get_dic_lora_yml(checkpoint_type)
            self._get_workflow_api(checkpoint_type)

    def _load_wildcards(self):
        data_path = Path(self.get_config('dataPath'))
        for ct in self.checkpoint_types:
            char_w = self.get_config('CharWildcard', {})
            lora_w = self.get_config('LoraWildcard', {})
            setup_w = self.yaml_handler.load_simple(str(data_path / 'setupWildcard.yml')) or {}
            type_w = self.yaml_handler.load_simple(str(data_path / ct / 'setupWildcard.yml')) or {}
            update_dict(setup_w, type_w)
            
            char_w = setup_w.get('CharWildcard', char_w)
            lora_w = setup_w.get('LoraWildcard', lora_w)
            
            set_nested(self.type_dics, char_w, ct, 'CharWildcard')
            set_nested(self.type_dics, lora_w, ct, 'LoraWildcard')

    def _is_unet_checkpoint_type(self, checkpoint_type: str) -> bool:
        return checkpoint_type == 'Anime'

    def _get_checkpoint_model_paths(self, checkpoint_type: str) -> Tuple[Path, Path, str]:
        if self._is_unet_checkpoint_type(checkpoint_type):
            model_base = Path(self.get_config('base_dir'), self.get_config('unetPath'))
            typed_base = model_base / checkpoint_type
            search_base = typed_base if typed_base.exists() else model_base
            return search_base, model_base, 'unetPath'

        model_base = Path(self.get_config('base_dir'), self.get_config('CheckpointPath'))
        return model_base / checkpoint_type, model_base, 'CheckpointPath'

    def _get_safetensors_checkpoint(self, checkpoint_type: str):
        search_base, model_base, _ = self._get_checkpoint_model_paths(checkpoint_type)
        f_dict, f_list, f_names = get_file_dict_list(search_base, model_base)
        set_nested(self.type_dics, f_dict, checkpoint_type, 'CheckpointFileDics')
        set_nested(self.type_dics, f_list, checkpoint_type, 'CheckpointFileLists')
        set_nested(self.type_dics, f_names, checkpoint_type, 'CheckpointFileNames')
        print.Value('CheckpointFiles', checkpoint_type, len(f_names))

    def _get_safetensors_char(self, checkpoint_type: str):
        lora_base = Path(self.get_config('base_dir'), self.get_config('LoraPath'))
        char_p = lora_base / checkpoint_type / self.get_config('LoraCharPath', 'char')
        f_dict, f_list, f_names = get_file_dict_list(char_p, lora_base)
        set_nested(self.type_dics, f_dict, checkpoint_type, 'CharFileDics')
        set_nested(self.type_dics, f_list, checkpoint_type, 'CharFileLists')
        set_nested(self.type_dics, f_names, checkpoint_type, 'CharFileNames')
        print.Value('CharFiles', checkpoint_type, len(f_names))

    def _get_safetensors_etc(self, checkpoint_type: str):
        lora_base = Path(self.get_config('base_dir'), self.get_config('LoraPath'))
        etc_p = lora_base / checkpoint_type / self.get_config('LoraEtcPath', 'etc')
        f_dict, f_list, f_names = get_file_dict_list(etc_p, lora_base)
        set_nested(self.type_dics, f_dict, checkpoint_type, 'LoraFileDics')
        set_nested(self.type_dics, f_list, checkpoint_type, 'LoraFileLists')
        set_nested(self.type_dics, f_names, checkpoint_type, 'LoraFileNames')
        print.Value('LoraFiles', checkpoint_type, len(f_names))

    def _get_weight_checkpoint(self, checkpoint_type: str):
        data_path = Path(self.get_config('dataPath'))
        names = get_nested(self.type_dics, checkpoint_type, 'CheckpointFileNames', default=[])
        weight_yml = self.yaml_handler.load_simple(str(data_path / checkpoint_type / "WeightCheckpoint.yml")) or {}
        weights = {n: (get_nested(self.type_dics, checkpoint_type, 'dicCheckpointYml', n, 'weight') or weight_yml.get(n, self.get_config('CheckpointWeightDefault', 150))) for n in names}
        set_nested(self.type_dics, weights, checkpoint_type, 'WeightCheckpoint')

    def _get_weight_char(self, checkpoint_type: str):
        data_path = Path(self.get_config('dataPath'))
        names = get_nested(self.type_dics, checkpoint_type, 'CharFileNames', default=[])
        weight_yml = self.yaml_handler.load_simple(str(data_path / checkpoint_type / "WeightChar.yml")) or {}
        weights = {n: (get_nested(self.type_dics, checkpoint_type, 'dicLoraYml', n, 'weight') or weight_yml.get(n, self.get_config('CharWeightDefault', 150))) for n in names}
        set_nested(self.type_dics, weights, checkpoint_type, 'WeightChar')

    def _get_weight_lora(self, checkpoint_type: str, delete: bool = True):
        data_path = Path(self.get_config('dataPath'))
        weight_lora = self.yaml_handler.load_simple(str(data_path / checkpoint_type / "WeightLora.yml")) or {}
        set_nested(self.type_dics, weight_lora, checkpoint_type, 'WeightLora')
        if delete: self._clean_weight_lora(checkpoint_type)

    def _clean_weight_lora(self, checkpoint_type: str):
        names = get_nested(self.type_dics, checkpoint_type, 'LoraFileNames', default=[])
        weight_lora = get_nested(self.type_dics, checkpoint_type, 'WeightLora', default={})
        for k1, v1 in list(weight_lora.items()):
            if not isinstance(v1, dict): continue
            dic = v1.get('dic', {})
            for k2, v2 in list(dic.items()):
                if not v2.get('weight') and not v2.get('per'): dic.pop(k2); continue
                loras = v2.get('loras')
                if isinstance(loras, dict): v2["loras"] = {k: v for k, v in loras.items() if k in names}
                elif isinstance(loras, list): v2["loras"] = [k for k in loras if k in names]
                elif isinstance(loras, str): v2["loras"] = loras if loras in names else None
                if not v2.get('loras'): dic.pop(k2)
            if not dic: weight_lora.pop(k1)

    def _get_dic_checkpoint_yml(self, checkpoint_type: str):
        p = Path(self.get_config('dataPath')) / checkpoint_type / 'checkpoint'
        set_nested(self.type_dics, self.yaml_handler.merge_yml_files(p, '*.yml'), checkpoint_type, 'dicCheckpointYml')

    def _get_dic_lora_yml(self, checkpoint_type: str):
        p = Path(self.get_config('dataPath')) / checkpoint_type / 'lora'
        set_nested(self.type_dics, self.yaml_handler.merge_yml_files(p, '*.yml'), checkpoint_type, 'dicLoraYml')

    def _get_workflow_api(self, checkpoint_type: str):
        p = Path(self.get_config('dataPath')) / checkpoint_type / self.get_config('workflow_api', 'workflow_api.json')
        set_nested(self.type_dics, self.yaml_handler.load_simple(str(p)), checkpoint_type, 'workflow_api')

    def _get_setup_wildcard(self, checkpoint_type: str = None):
        data_path = Path(self.get_config('dataPath'))
        cts = [checkpoint_type] if checkpoint_type else self.checkpoint_types
        for ct in cts:
            base = self.yaml_handler.load_simple(str(data_path / 'setupWildcard.yml')) or {}
            spec = self.yaml_handler.load_simple(str(data_path / ct / 'setupWildcard.yml')) or {}
            update_dict(base, spec)
            set_nested(self.type_dics, base, ct, 'setupWildcard')

    def _get_setup_workflow(self, checkpoint_type: str = None):
        data_path = Path(self.get_config('dataPath'))
        cts = [checkpoint_type] if checkpoint_type else self.checkpoint_types
        for ct in cts:
            base = self.yaml_handler.load_simple(str(data_path / 'setupWorkflow.yml')) or {}
            spec = self.yaml_handler.load_simple(str(data_path / ct / 'setupWorkflow.yml')) or {}
            update_dict(base, spec)
            set_nested(self.type_dics, base, ct, 'setupWorkflow')

    def _collect_lora_tags(self) -> List[str]:
        if not self.loras_set: return []
        tags = []
        dic = self.get_now('dicLoraYml', default={})
        for lora in self.loras_set:
            t = dic.get(lora, {}).get('tag')
            if isinstance(t, list): tags.extend([str(x).strip() for x in t if str(x).strip()])
            elif isinstance(t, str) and t.strip(): tags.append(t.strip())
        return tags
