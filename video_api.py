import json
from urllib import request
import random
import time
import os
import logging
from rich.logging import RichHandler

# optional YAML support if PyYAML is available
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# Configure rich logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RichHandler()]
)
logger = logging.getLogger()


def check_count():
    '''
    기능 :
    http://127.0.0.1:8188/prompt 으로 GET 호출을하면
    {"exec_info": {"queue_remaining": 2}}
    값을 받게되고, queue_remaining값을 반환하기
    '''
    logger.debug('Checking queue remaining from /prompt')
    try:
        req = request.Request("http://127.0.0.1:8188/prompt")
        with request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode('utf-8')
            j = json.loads(data)
            q = int(j.get('exec_info', {}).get('queue_remaining', 0))
            # logger.info(f'Queue remaining read: {q}')
            return q
    except Exception as e:
        logger.error(f'check_count error: {e}', exc_info=True)
        return 0


def queue_prompt(prompt):
    '''
    수정 금지
    '''
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    req =  request.Request("http://127.0.0.1:8188/prompt", data=data)
    request.urlopen(req)


def load_prompt():
    '''
    현재 디렉토리의 `video_api.yml` 파일을 읽어옵니다. YAML 형식으로 파싱합니다.
    PyYAML이 설치되어 있지 않으면 오류를 발생시킵니다.
    '''
    path = os.path.join(os.path.dirname(__file__), 'video_api.yml')
    if not os.path.exists(path):
        logger.error(f'video_api.yml not found: {path}')
        raise FileNotFoundError(f'video_api.yml not found: {path}')

    logger.info(f'Loading prompt file: {path}')
    s = open(path, 'r', encoding='utf-8').read()

    if yaml is None:
        logger.error('PyYAML is required to parse video_api.yml. Please install pyyaml.')
        raise ValueError('PyYAML is required to parse video_api.yml. Please install pyyaml.')

    try:
        data = yaml.safe_load(s)
        if isinstance(data, dict):
            logger.info(f'Loaded prompt with {len(data)} top-level entries')
        else:
            logger.info('Loaded prompt (non-dict root)')
        return data
    except Exception as e:
        logger.error(f'Failed to parse video_api.yml as YAML: {e}', exc_info=True)
        raise ValueError(f'Failed to parse video_api.yml as YAML: {e}')


def edit_prompt(prompt):
    '''
    prompt의 구조 :
    {
        '순번 또는 텍스트' : {
            "inputs": { ... }
        }
    }

    기능 :
    prompt의 설정값 중 "inputs" 바로 밑에서 이름에 'seed'가 포함된 경우, 값을 랜덤 시드값으로 재설정
    '''
    if not isinstance(prompt, dict):
        logger.warning('edit_prompt called with non-dict prompt')
        return prompt

    total_replaced = 0
    for name, entry in prompt.items():
        if not isinstance(entry, dict):
            continue
        inputs = entry.get('inputs')
        if not isinstance(inputs, dict):
            continue

        replaced = 0
        for k in list(inputs.keys()):
            if isinstance(k, str) and 'seed' in k.lower():
                # old = inputs.get(k)
                new = random.randint(0, 2**31 - 1)
                inputs[k] = new
                replaced += 1
                logger.info(f'[{name}] {k}: {new}')

        # if replaced:
        #     logger.info(f'[{name}] seeds replaced: {replaced}')
        total_replaced += replaced

    logger.info(f'Total seeds replaced: {total_replaced}')
    return prompt


if __name__ == '__main__':
    logger.info('video_api started')
    try:
        while True:
            prompt = load_prompt()
            edit_prompt(prompt)

            # --- 건수를 1초마다 확인하면서 1개 이상인 경우 대기하기
            q = check_count()
            if q >= 1:
                logger.info(f'Queue remaining: {q}, waiting...')

            while q is not None and q >= 1:
                # logger.info(f'Queue remaining: {q}, waiting...')
                time.sleep(1)
                q = check_count()
            # ---


            try:
                queue_prompt(prompt)
                logger.info('Prompt queued successfully.')
            except Exception as e:
                logger.error(f'Failed to queue prompt: {e}', exc_info=True)

            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info('Interrupted by user, exiting.')


