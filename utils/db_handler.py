# -*- coding: utf-8 -*-
"""
데이터베이스 핸들러
"""
from pathlib import Path
from typing import Set, Optional
from tinydb import TinyDB, Query
from tinydb.table import Table
from tinydb.storages import JSONStorage


class UTF8JSONStorage(JSONStorage):
    """UTF-8 인코딩을 지원하는 JSON 스토리지"""
    
    def __init__(self, path, **kwargs):
        super().__init__(path, encoding='utf-8', **kwargs)


class DatabaseHandler:
    """데이터베이스 핸들러 클래스"""
    
    def __init__(self):
        self.path: Optional[Path] = None
        self.db: Optional[TinyDB] = None
        self.query = Query()
    
    def init(self, data_path: str):
        """
        데이터베이스를 초기화합니다.
        
        Args:
            data_path: 데이터 경로
        """
        self.path = Path(data_path) / 'count.db'
        self.db = TinyDB(self.path, storage=UTF8JSONStorage)
    
    def update(self, checkpoint_type: str, checkpoint: str, char: str, loras: Set[str]):
        """
        데이터베이스를 업데이트합니다.
        
        Args:
            checkpoint_type: 체크포인트 타입
            checkpoint: 체크포인트 이름
            char: 캐릭터 이름
            loras: LoRA 세트
        """
        if not self.db:
            return
        
        loras_list = list(loras)
        
        # LoRA 테이블 업데이트
        lora_table = self.db.table(f'{checkpoint_type}-Lora')
        for lora in loras:
            self._update(
                lora_table,
                self.query.Lora == lora,
                {'Lora': lora, 'count': 1}
            )
        
        # 다른 필드 업데이트
        fields = {
            'Checkpoint': checkpoint,
            'Char': char,
            'Loras': loras_list
        }
        
        for key, value in fields.items():
            self._update(
                self.db.table(f'{checkpoint_type}-{key}'),
                getattr(self.query, key) == value,
                {key: value, 'count': 1}
            )
        
        # 조합 테이블 업데이트
        self._update(
            self.db.table(f'{checkpoint_type}-Combination'),
            (self.query.Checkpoint == checkpoint) &
            (self.query.Char == char) &
            (self.query.Loras == loras_list),
            {
                'Checkpoint': checkpoint,
                'Char': char,
                'Loras': loras_list,
                'count': 1
            }
        )
    
    def _update(self, table: Table, condition, new_data: dict):
        """
        테이블을 업데이트합니다.
        
        Args:
            table: 테이블 객체
            condition: 조건
            new_data: 새 데이터
        """
        result = table.get(condition)
        if result:
            new_count = result['count'] + 1
            table.update({'count': new_count}, doc_ids=[result.doc_id])
        else:
            table.insert(new_data)
    
    def get_char_counts(self, checkpoint_type: str) -> dict:
        """
        Char 사용 횟수를 가져옵니다.
        
        Args:
            checkpoint_type: 체크포인트 타입
        
        Returns:
            {char_name: count} 딕셔너리
        """
        if not self.db:
            return {}
        
        char_table = self.db.table(f'{checkpoint_type}-Char')
        char_counts = {}
        
        for doc in char_table.all():
            char_name = doc.get('Char')
            count = doc.get('count', 0)
            if char_name:
                char_counts[char_name] = count
        
        return char_counts
    
    def get_lora_counts(self, checkpoint_type: str) -> dict:
        """
        LoRA 사용 횟수를 가져옵니다.
        
        Args:
            checkpoint_type: 체크포인트 타입
        
        Returns:
            {lora_name: count} 딕셔너리
        """
        if not self.db:
            return {}
        
        lora_table = self.db.table(f'{checkpoint_type}-Lora')
        lora_counts = {}
        
        for doc in lora_table.all():
            lora_name = doc.get('Lora')
            count = doc.get('count', 0)
            if lora_name:
                lora_counts[lora_name] = count
        
        return lora_counts
    
    def json_to_xlsx(self):
        """JSON 데이터를 XLSX로 변환합니다."""
        if not self.path:
            return
        
        try:
            from .json_to_xlsx import json_to_xlsx
            json_to_xlsx(self.path)
        except Exception as e:
            print.exception(show_locals=True)

