# -*- coding: utf-8 -*-
"""
파일 처리 유틸리티
"""
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


def get_file_dict_list(path: Path, base_dir: Path = None) -> Tuple[Dict[str, str], List[str], List[str]]:
    """
    디렉토리에서 파일 목록을 가져옵니다.
    
    Args:
        path: 검색할 경로
        base_dir: 기준 디렉토리 (상대 경로 계산용)
    
    Returns:
        (파일명->경로 딕셔너리, 경로 리스트, 파일명 리스트) 튜플
    """
    if base_dir is None:
        base_dir = path
    
    files = list(path.rglob('*.safetensors')) if path.exists() else []
    
    names = [f.stem for f in files]
    paths_list = [str(f.relative_to(base_dir)) for f in files]
    paths_dict = dict(zip(names, paths_list))
    
    return paths_dict, paths_list, names


def get_file_list_path(path: Path, base_dir: Path = None) -> List[Path]:
    """
    경로에서 파일 목록을 가져옵니다.
    
    Args:
        path: 검색할 경로 패턴
        base_dir: 기준 디렉토리
    
    Returns:
        Path 객체 리스트
    """
    if base_dir is None:
        base_dir = Path('.')
    
    files = list(base_dir.glob(str(path)))
    return [f.relative_to(base_dir) for f in files]


class FileEventHandler(FileSystemEventHandler):
    """파일 시스템 이벤트 핸들러"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.last_event_time = 0.0
    
    def on_any_event(self, event: FileSystemEvent):
        """모든 파일 시스템 이벤트를 처리합니다."""
        if event.is_directory:
            return
        
        if self._time_check(event):
            return
        
        self.callback(event)
    
    def _time_check(self, event: FileSystemEvent) -> bool:
        """중복 이벤트를 제거합니다."""
        if event.event_type != 'modified':
            return False
        
        current_time = time.time()
        if not hasattr(self, 'last_event_time') or current_time - self.last_event_time > 1:
            self.last_event_time = current_time
            return True
        
        return False


class FileObserver:
    """파일 시스템 감시자"""
    
    def __init__(self):
        self.observer = Observer()
        self.paths = []
    
    def watch(self, path: str, event_handler: FileSystemEventHandler, recursive: bool = True):
        """
        경로를 감시합니다.
        
        Args:
            path: 감시할 경로
            event_handler: 이벤트 핸들러
            recursive: 재귀적 감시 여부
        """
        self.observer.schedule(event_handler, path, recursive=recursive)
        self.paths.append(path)
        
        if recursive:
            path_obj = Path(path)
            if path_obj.exists():
                for sub_path in path_obj.rglob("*"):
                    if sub_path.is_dir() and sub_path.is_symlink():
                        self.observer.schedule(event_handler, str(sub_path), recursive=recursive)
                        self.paths.append(str(sub_path))
    
    def start(self):
        """감시를 시작합니다."""
        self.observer.start()
        print(f"파일 감시 시작: {self.paths}")
    
    def stop(self):
        """감시를 중지합니다."""
        print(f"파일 감시 중지: {self.paths}")
        self.observer.stop()
        self.observer.join()
        print(f"파일 감시 중지 완료")

