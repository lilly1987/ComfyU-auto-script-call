# -*- coding: utf-8 -*-
"""
Random utility helpers.
"""
import random
from typing import Any, Dict, List, Tuple, Union


def _positive_weight_items(d: Dict[str, Union[int, float]]) -> List[Tuple[str, Union[int, float]]]:
    """
    Return only entries that are valid for ``random.choices``.
    """
    items = []

    for k, v in d.items():
        if not isinstance(v, (int, float)):
            raise TypeError(f"{k}: {v} is not a number")
        if v > 0:
            items.append((k, v))

    return items


def random_weight_count(d: Dict[str, Union[int, float]], count: int = 1, default: List[str] = None) -> List[str]:
    """
    Select ``count`` items from a weighted dictionary.
    """
    if not isinstance(d, dict):
        return default or []

    items = _positive_weight_items(d)
    if not items:
        return default or []

    return random.choices([k for k, _ in items], weights=[v for _, v in items], k=count)


def random_min_max(v: Union[Tuple, List, set, int, float]) -> Union[int, float]:
    """
    Return a random value from a range-like input.
    """
    if isinstance(v, set):
        v = tuple(v)

    if isinstance(v, (tuple, list)):
        if any(isinstance(item, float) for item in v):
            return random.uniform(min(v), max(v))
        if all(isinstance(item, int) for item in v):
            return random.randint(min(v), max(v))
        raise ValueError(f"invalid random range: {v}")

    return v


def random_weight(i: Union[str, List, Dict]) -> Any:
    """
    Select one item from a string, list, or weighted dictionary.
    """
    if isinstance(i, str):
        return i
    if isinstance(i, list):
        return random.choice(i)
    if isinstance(i, dict):
        items = _positive_weight_items(i)
        if not items:
            return None
        return random.choices([k for k, _ in items], weights=[v for _, v in items], k=1)[0]
    return i


def random_dict_weight(d: Dict, weight_key: str, count: int = 1, default: List[str] = None) -> List[str]:
    """
    Select ``count`` keys from nested dictionaries using ``weight_key``.
    """
    weight_dict = {k: v[weight_key] for k, v in d.items() if weight_key in v}
    items = _positive_weight_items(weight_dict)

    if not items:
        return default or []

    return random.choices([k for k, _ in items], weights=[v for _, v in items], k=count)


def seed_int() -> int:
    """
    Create a random 64-bit integer seed.
    """
    return random.randint(0, 0xFFFFFFFFFFFFFFFF)


def random_items_count(items: Union[Dict, List, Tuple], count: int = 1) -> List:
    """
    Select up to ``count`` unique items from a dictionary, list, or tuple.
    """
    if isinstance(items, dict):
        items = list(items.keys())

    if not isinstance(items, (list, tuple)):
        raise ValueError(f"items must be a list or tuple: {items}")

    if len(items) > count:
        return random.sample(items, count)

    return list(items)
