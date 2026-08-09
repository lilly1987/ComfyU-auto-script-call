# -*- coding: utf-8 -*-
"""
공통 상수 정의
- config.yml 키와 type_dics 내부 키를 하드코딩 문자열 대신 상수로 관리합니다.
- 오타 방지, 키 변경 시 한 곳만 수정할 수 있게 합니다.
"""

# --- config.yml 최상위 키 ---
CONFIG_CHECKPOINT_TYPES = 'CheckpointTypes'
CONFIG_DATA_PATH = 'dataPath'
CONFIG_BASE_DIR = 'base_dir'
CONFIG_CHECKPOINT_PATH = 'CheckpointPath'
CONFIG_LORA_PATH = 'LoraPath'
CONFIG_CHAR_WILDCARD = 'CharWildcard'
CONFIG_LORA_WILDCARD = 'LoraWildcard'

# --- type_dics 내부 키 ---
KEY_DIC_LORA_YML = 'dicLoraYml'
KEY_DIC_CHECKPOINT_YML = 'dicCheckpointYml'

# --- 기타 하드코딩 문자열 ---
CONFIG_FILE_NAME = 'config.yml'
