# -*- coding: utf-8 -*-
"""
타입 유틸리티
"""
from typing import Dict, Tuple, List, Any


def get_type_list(dic: Dict, type_tuple: Tuple, exclude_tuple: Tuple = ()) -> List[str]:
    """
    딕셔너리에서 특정 타입의 값의 키를 리스트로 반환합니다.
    
    Args:
        dic: 딕셔너리
        type_tuple: 포함할 타입 튜플
        exclude_tuple: 제외할 타입 튜플
    
    Returns:
        키 리스트
    """
    if not isinstance(dic, dict):
        return []
    
    result = [
        k for k, v in dic.items()
        if isinstance(v, type_tuple) and not isinstance(v, exclude_tuple)
    ]
    
    return result

