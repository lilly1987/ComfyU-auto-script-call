# -*- coding: utf-8 -*-
"""
랜덤 유틸리티
"""
import random
from typing import Dict, List, Tuple, Union, Any


def random_weight_count(d: Dict[str, Union[int, float]], count: int = 1, default: List[str] = None) -> List[str]:
    """
    가중치를 기반으로 랜덤 선택합니다.
    
    Args:
        d: {키: 가중치} 딕셔너리
        count: 선택할 개수
        default: 기본값 (딕셔너리가 아닐 때)
    
    Returns:
        선택된 키 리스트
    """
    if not isinstance(d, dict):
        return default or []
    
    for k, v in d.items():
        if not isinstance(v, (int, float)):
            raise TypeError(f'{k}: {v}는 숫자가 아닙니다')
    
    return random.choices(list(d.keys()), weights=list(d.values()), k=count)


def random_min_max(v: Union[Tuple, List, set, int, float]) -> Union[int, float]:
    """
    범위에서 랜덤 값을 선택합니다.
    
    Args:
        v: 값 또는 범위 (튜플/리스트)
    
    Returns:
        랜덤 값
    """
    if isinstance(v, set):
        v = tuple(v)
    
    if isinstance(v, (tuple, list)):
        if any(isinstance(item, float) for item in v):
            return random.uniform(min(v), max(v))
        elif all(isinstance(item, int) for item in v):
            return random.randint(min(v), max(v))
        else:
            raise ValueError(f"랜덤 값 오류: {v}")
    
    return v


def random_weight(i: Union[str, List, Dict]) -> Any:
    """
    리스트나 딕셔너리에서 가중치를 기반으로 랜덤 선택합니다.
    
    Args:
        i: 선택할 대상 (문자열, 리스트, 딕셔너리)
    
    Returns:
        선택된 값
    """
    if isinstance(i, str):
        return i
    elif isinstance(i, list):
        return random.choice(i)
    elif isinstance(i, dict):
        return random.choices(list(i.keys()), weights=list(i.values()), k=1)[0]
    else:
        return i


def random_dict_weight(d: Dict, weight_key: str, count: int = 1, default: List[str] = None) -> List[str]:
    """
    딕셔너리에서 가중치 키를 기반으로 랜덤 선택합니다.
    
    Args:
        d: 딕셔너리
        weight_key: 가중치 키
        count: 선택할 개수
        default: 기본값
    
    Returns:
        선택된 키 리스트
    """
    weight_dict = {k: v[weight_key] for k, v in d.items() if weight_key in v}
    
    if not weight_dict:
        return default or []
    
    return random.choices(list(weight_dict.keys()), weights=list(weight_dict.values()), k=count)


def seed_int() -> int:
    """
    랜덤 시드를 생성합니다.
    
    Returns:
        64비트 정수 시드
    """
    return random.randint(0, 0xffffffffffffffff)


def random_items_count(items: Union[Dict, List, Tuple], count: int = 1) -> List:
    """
    항목에서 지정된 개수만큼 랜덤 선택합니다.
    
    Args:
        items: 선택할 항목 (딕셔너리, 리스트, 튜플)
        count: 선택할 개수
    
    Returns:
        선택된 항목 리스트
    """
    if isinstance(items, dict):
        items = list(items.keys())
    
    if not isinstance(items, (list, tuple)):
        raise ValueError(f"항목이 리스트나 튜플이 아닙니다: {items}")
    
    if len(items) > count:
        return random.sample(items, count)
    
    return list(items)

