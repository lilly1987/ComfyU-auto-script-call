import json
from urllib import request
import random
import time
import os

# optional YAML support if PyYAML is available
try:
    import yaml  # type: ignore
except Exception:
    yaml = None


def check_count():
    '''
    기능 :
    http://127.0.0.1:8188/prompt 으로 GET 호출을하면
    {"exec_info": {"queue_remaining": 2}}
    값을 받게되고, queue_remaining값을 반환하기
    '''
    try:
        req = request.Request("http://127.0.0.1:8188/prompt")
        with request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode('utf-8')
            j = json.loads(data)
            return int(j.get('exec_info', {}).get('queue_remaining', 0))
    except Exception as e:
        print(f'check_count error: {e}')
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
        raise FileNotFoundError(f'video_api.yml not found: {path}')

    s = open(path, 'r', encoding='utf-8').read()

    if yaml is None:
        raise ValueError('PyYAML is required to parse video_api.yml. Please install pyyaml.')

    try:
        return yaml.safe_load(s)
    except Exception as e:
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
        return prompt

    for name, entry in prompt.items():
        if not isinstance(entry, dict):
            continue
        inputs = entry.get('inputs')
        if not isinstance(inputs, dict):
            continue

        for k in list(inputs.keys()):
            if isinstance(k, str) and 'seed' in k.lower():
                inputs[k] = random.randint(0, 2**31 - 1)

    return prompt


if __name__ == '__main__':
    try:
        while True:
            # --- 건수를 1초마다 확인하면서 1개 이상인 경우 대기하기
            q = check_count()
            while q is not None and q >= 1:
                print(f'Queue remaining: {q}, waiting...')
                time.sleep(1)
                q = check_count()
            # ---

            prompt = load_prompt()
            edit_prompt(prompt)

            queue_prompt(prompt)
            print('Prompt queued successfully.')
            time.sleep(1)
            
    except KeyboardInterrupt:
        print('Interrupted by user, exiting.')


