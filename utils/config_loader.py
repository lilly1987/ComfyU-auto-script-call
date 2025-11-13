# -*- coding: utf-8 -*-
"""
설정 파일 로더
"""
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any


class ConfigLoader:
    """설정 파일을 로드하고 관리하는 클래스"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 설정 파일 경로 (None이면 스크립트 디렉토리의 config.yml 사용)
        """
        if config_path is None:
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(script_dir, 'config.yml')
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> Dict[str, Any]:
        """설정 파일을 로드합니다."""
        if not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            
            # dataPath가 상대 경로인 경우 절대 경로로 변환
            if 'dataPath' in self._config and not os.path.isabs(self._config['dataPath']):
                script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self._config['dataPath'] = os.path.normpath(
                    os.path.join(script_dir, self._config['dataPath'])
                )
            
            return self._config
        except Exception as e:
            print(f"  오류: 설정 파일 읽기 실패: {e}")
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정 값을 가져옵니다."""
        return self._config.get(key, default)
    
    def reload(self) -> Dict[str, Any]:
        """설정 파일을 다시 로드합니다."""
        return self.load()
    
    @property
    def config(self) -> Dict[str, Any]:
        """설정 딕셔너리를 반환합니다."""
        return self._config

