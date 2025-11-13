# -*- coding: utf-8 -*-
"""
JSON to XLSX 변환 유틸리티
"""
import pandas as pd
from pathlib import Path
from tinydb import TinyDB
from tinydb.storages import JSONStorage

from .print_log import print


class UTF8JSONStorage(JSONStorage):
    """UTF-8 인코딩을 지원하는 JSON 스토리지"""
    
    def __init__(self, path, **kwargs):
        super().__init__(path, encoding='utf-8', **kwargs)


def json_to_xlsx(db_path: Path):
    """
    TinyDB JSON 파일을 XLSX 파일로 변환합니다.
    
    Args:
        db_path: 데이터베이스 파일 경로
    """
    if not db_path.exists():
        print.Warn(f"데이터베이스 파일이 없습니다: {db_path}")
        return
    
    db = TinyDB(db_path, storage=UTF8JSONStorage)
    table_names = db.tables()
    
    if not table_names:
        print.Warn("테이블이 없습니다")
        return
    
    new_file = db_path.with_suffix('.xlsx')
    if new_file.exists():
        new_file.unlink()
    
    try:
        with pd.ExcelWriter(new_file, engine='openpyxl') as writer:
            for table_name in table_names:
                table = db.table(table_name)
                data = table.all()
                
                # 리스트를 문자열로 변환
                for row in data:
                    for col, value in row.items():
                        if isinstance(value, list):
                            row[col] = ', '.join(map(str, value))
                
                df = pd.DataFrame(data)
                sheet_name = str(table_name)[:31]  # Excel 시트 이름 제한
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # 열 너비 자동 조정
                for i, col in enumerate(df.columns):
                    max_len = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    max_len = min(max_len, 200)
                    writer.sheets[sheet_name].column_dimensions[
                        chr(65 + i)
                    ].width = max_len + 2
        
        print.Info("XLSX 파일 생성 완료:", new_file)
    except Exception as e:
        print.exception(show_locals=True)

