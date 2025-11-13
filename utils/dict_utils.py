# -*- coding: utf-8 -*-
"""
딕셔너리 유틸리티
"""
import collections
from typing import Dict, Any, Optional


def get_nested(d: Dict, *keys, default: Any = None) -> Any:
    """
    중첩 딕셔너리에서 키를 안전하게 가져옵니다.
    
    Args:
        d: 딕셔너리
        *keys: 키 경로
        default: 기본값
    
    Returns:
        값 또는 기본값
    """
    current = d
    for key in keys[:-1]:
        current = current.get(key, default)
        if not isinstance(current, dict):
            return default
    
    if keys and keys[-1] in current:
        return current[keys[-1]]
    
    return default


def set_nested(d: Dict, value: Any, *keys) -> Dict:
    """
    중첩 딕셔너리에 값을 설정합니다 (키가 없으면 생성).
    
    Args:
        d: 딕셔너리
        value: 설정할 값
        *keys: 키 경로
    
    Returns:
        딕셔너리
    """
    if not keys:
        return d
    
    temp = d
    for key in keys[:-1]:
        temp = temp.setdefault(key, {})
    
    temp[keys[-1]] = value
    return d


def set_exists(d: Dict, value: Any, *keys) -> Optional[Dict]:
    """
    중첩 딕셔너리에 값을 설정합니다 (키가 존재할 때만).
    
    Args:
        d: 딕셔너리
        value: 설정할 값
        *keys: 키 경로
    
    Returns:
        업데이트된 딕셔너리 또는 None
    """
    current = d
    for key in keys[:-1]:
        current = current.get(key)
        if current is None or not isinstance(current, dict):
            return None
    
    if keys and keys[-1] in current:
        current[keys[-1]] = value
        return current
    
    return None


def pop_nested(d: Dict, *keys, default: Any = None) -> Any:
    """
    중첩 딕셔너리에서 값을 제거하고 반환합니다.
    
    Args:
        d: 딕셔너리
        *keys: 키 경로 (마지막 두 개가 딕셔너리 키와 값 키)
        default: 기본값
    
    Returns:
        제거된 값 또는 기본값
    """
    if len(keys) < 2:
        return default
    
    current = d
    for key in keys[:-2]:
        current = current.get(key)
        if current is None or not isinstance(current, dict):
            return default
    
    if keys[-2] in current:
        return current[keys[-2]].pop(keys[-1], default)
    
    return default


def update_dict(d: Dict, u: Dict) -> Dict:
    """
    딕셔너리를 재귀적으로 업데이트합니다.
    
    Args:
        d: 대상 딕셔너리
        u: 업데이트할 딕셔너리
    
    Returns:
        업데이트된 딕셔너리
    """
    if u is None:
        return d
    
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_dict(d.get(k, {}), v)
        else:
            d[k] = v
    
    return d


def update_dict_key(d: Dict, u: Dict, key: str) -> Dict:
    """
    딕셔너리에서 특정 키를 업데이트합니다.
    
    Args:
        d: 대상 딕셔너리
        u: 업데이트할 딕셔너리
        key: 업데이트할 키
    
    Returns:
        업데이트된 딕셔너리
    """
    if key in u:
        if key in d:
            update_dict(d[key], u[key])
        else:
            d[key] = u[key]
    
    return d


def convert_paths(obj: Any) -> Any:
    """
    객체 내의 Path 객체를 문자열로 변환합니다.
    
    Args:
        obj: 변환할 객체
    
    Returns:
        변환된 객체
    """
    from pathlib import Path
    
    if isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_paths(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_paths(elem) for elem in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_paths(elem) for elem in obj)
    else:
        return obj

