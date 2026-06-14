# -*- coding: utf-8 -*-
import fnmatch
import time
from pathlib import Path
from watchdog.events import FileSystemEvent
from utils.file_handler import FileEventHandler, FileObserver
from utils.dict_utils import get_nested, set_nested
from utils.print_log import print, logger

class ObserverMixin:
    """파일 시스템 감시 및 콜백 로직을 담당하는 Mixin"""

    def start_observers(self):
        """파일 시스템 감시를 시작합니다."""
        self.file_observer = FileObserver()
        
        # 데이터 경로 감시
        self.file_observer.watch(
            str(Path(self.get_config('dataPath'))),
            FileEventHandler(self._data_path_callback),
            recursive=True
        )
        # 체크포인트 경로 감시
        self.file_observer.watch(
            str(Path(self.get_config('base_dir'), self.get_config('CheckpointPath'))),
            FileEventHandler(self._checkpoint_path_callback),
            recursive=True
        )
        if 'Anime' in self.checkpoint_types:
            self.file_observer.watch(
                str(Path(self.get_config('base_dir'), self.get_config('unetPath'))),
                FileEventHandler(self._unet_path_callback),
                recursive=True
            )
        # LoRA 경로 감시
        self.file_observer.watch(
            str(Path(self.get_config('base_dir'), self.get_config('LoraPath'))),
            FileEventHandler(self._lora_path_callback),
            recursive=True
        )
        # 메인 설정 파일 감시
        self.file_observer.watch(
            ".",
            FileEventHandler(self._config_callback),
            recursive=False
        )
        self.file_observer.start()

    def stop_observers(self):
        """파일 시스템 감시를 중단합니다."""
        if hasattr(self, 'file_observer'):
            self.file_observer.stop()

    def update_safetensors(self, path: Path, checkpoint_type: str, event_type: str,
                          config_key: str, dics_key: str, lists_key: str, names_key: str):
        """SafeTensors 파일 목록 업데이트 공통 로직"""
        config_path = Path(self.get_config('base_dir'), self.get_config(config_key))
        try:
            rpath = path.relative_to(config_path)
        except ValueError:
            rpath = Path(path.name)
        
        name = Path(rpath).stem
        file_dics = get_nested(self.type_dics, checkpoint_type, dics_key, default={})
        file_lists = get_nested(self.type_dics, checkpoint_type, lists_key, default=[])
        file_names = get_nested(self.type_dics, checkpoint_type, names_key, default=[])
        spath = str(rpath)
        
        if event_type == 'deleted':
            file_dics.pop(name, None)
            if spath in file_lists: file_lists.remove(spath)
            if name in file_names: file_names.remove(name)
        elif event_type == 'created':
            file_dics[name] = spath
            if spath not in file_lists: file_lists.append(spath)
            if name not in file_names: file_names.append(name)
        
        set_nested(self.type_dics, file_dics, checkpoint_type, dics_key)
        set_nested(self.type_dics, file_lists, checkpoint_type, lists_key)
        set_nested(self.type_dics, file_names, checkpoint_type, names_key)

    def _wait_for_stable_file(self, path: Path, stable_time: float = 0.5, timeout: float = 5.0) -> bool:
        """파일 쓰기가 완료될 때까지 대기"""
        start = time.time()
        last_size = -1
        stable_since = None
        while time.time() - start < timeout:
            try:
                size = path.stat().st_size
                if size == last_size:
                    if stable_since is None: stable_since = time.time()
                    elif time.time() - stable_since >= stable_time: return True
                else:
                    last_size = size
                    stable_since = None
            except Exception: return False
            time.sleep(0.2)
        return False

    def _should_process_event(self, path: Path, event_type: str, debounce_seconds: float = 1.5) -> bool:
        """중복 이벤트 방지를 위한 디바운스"""
        key = f"{event_type}:{str(path)}"
        now = time.time()
        with self._recent_events_lock:
            last = self._recent_events.get(key)
            if last and now - last < debounce_seconds: return False
            self._recent_events[key] = now
            return True

    def _data_path_callback(self, event: FileSystemEvent):
        """설정 데이터 변경 시 실시간 리로드"""
        try:
            path = Path(event.src_path)
            config_path = Path(self.get_config('dataPath'))
            if not path.is_relative_to(config_path):
                return
            
            rel = path.relative_to(config_path)
            if len(rel.parts) > 0:
                r0 = rel.parts[0]
                if r0 in self.checkpoint_types:
                    if len(rel.parts) > 1:
                        r1 = rel.parts[1]
                        mapping = {
                            'setupWildcard.yml': self._get_setup_wildcard,
                            'setupWorkflow.yml': self._get_setup_workflow,
                            'WeightCheckpoint.yml': self._get_weight_checkpoint,
                            'WeightChar.yml': self._get_weight_char,
                            'WeightLora.yml': self._get_weight_lora,
                            'workflow_api.json': self._get_workflow_api
                        }
                        if r1 in mapping:
                            mapping[r1](r0)
                            return
                        if len(rel.parts) == 3:
                            if rel.parts[1] == 'checkpoint':
                                self._get_dic_checkpoint_yml(r0)
                            elif rel.parts[1] == 'lora':
                                self._get_dic_lora_yml(r0)
                                self._get_weight_char(r0)
                            return
                if r0 == 'setupWildcard.yml':
                    self._get_setup_wildcard()
                elif r0 == 'setupWorkflow.yml':
                    self._get_setup_workflow()
                elif r0 == 'config.yml':
                    self.config_loader.reload()
                    self.config = self.config_loader.config
        except Exception as e:
            print(f"Data path observer error: {e}")

    def _checkpoint_path_callback(self, event: FileSystemEvent):
        """모델 파일 추가/삭제 감지"""
        try:
            path = Path(event.src_path)
            config_path = Path(self.get_config('base_dir'), self.get_config('CheckpointPath'))
            if not fnmatch.fnmatch(str(path), str(config_path / '*.safetensors')): return
            if event.event_type not in {'created', 'deleted'}: return

            rel = path.relative_to(config_path)
            if (
                len(rel.parts) == 2
                and rel.parts[0] in self.checkpoint_types
                and not self._is_unet_checkpoint_type(rel.parts[0])
            ):
                if not self._should_process_event(path, event.event_type): return
                if event.event_type == 'created' and not self._wait_for_stable_file(path): return
                
                self.update_safetensors(path, rel.parts[0], event.event_type,
                                       'CheckpointPath', 'CheckpointFileDics', 
                                       'CheckpointFileLists', 'CheckpointFileNames')
        except Exception as e: print(f"Checkpoint observer error: {e}")
            

    def _unet_path_callback(self, event: FileSystemEvent):
        """UNET 파일 추가/삭제 감지"""
        try:
            if 'Anime' not in self.checkpoint_types:
                return
            path = Path(event.src_path)
            search_path, config_path, _ = self._get_checkpoint_model_paths('Anime')
            if not fnmatch.fnmatch(str(path), str(config_path / '*.safetensors')): return
            try:
                path.relative_to(search_path)
            except ValueError:
                return
            if event.event_type not in {'created', 'deleted'}: return
            if not self._should_process_event(path, event.event_type): return
            if event.event_type == 'created' and not self._wait_for_stable_file(path): return

            self.update_safetensors(path, 'Anime', event.event_type,
                                    'unetPath', 'CheckpointFileDics',
                                    'CheckpointFileLists', 'CheckpointFileNames')
        except Exception as e: print(f"UNET observer error: {e}")

    def _lora_path_callback(self, event: FileSystemEvent):
        """LoRA 파일 추가/삭제 감지"""
        try:
            path = Path(event.src_path)
            config_path = Path(self.get_config('base_dir'), self.get_config('LoraPath'))
            if not fnmatch.fnmatch(str(path), str(config_path / '*.safetensors')): return
            if event.event_type not in {'created', 'deleted'}: return

            rel = path.relative_to(config_path)
            if len(rel.parts) == 3 and rel.parts[0] in self.checkpoint_types:
                if not self._should_process_event(path, event.event_type): return
                if event.event_type == 'created' and not self._wait_for_stable_file(path): return

                if rel.parts[1] == 'char':
                    self.update_safetensors(path, rel.parts[0], event.event_type,
                                           'LoraPath', 'CharFileDics', 
                                           'CharFileLists', 'CharFileNames')
                elif rel.parts[1] == 'etc':
                    self.update_safetensors(path, rel.parts[0], event.event_type,
                                           'LoraPath', 'LoraFileDics', 
                                           'LoraFileLists', 'LoraFileNames')
        except Exception as e: print(f"Lora observer error: {e}")

    def _config_callback(self, event: FileSystemEvent):
        """config.yml 변경 감지"""
        if Path(event.src_path).name == 'config.yml':
            self.config_loader.reload()
            self.config = self.config_loader.config
            self.checkpoint_types = list(self.config.get('CheckpointTypes', {}).keys())
            logger.info(f"CheckpointTypes reloaded: {self.checkpoint_types}")
