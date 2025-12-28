import json
from urllib import request


def check_count(prompt):
    '''
    기능 :
    http://127.0.0.1:8188/prompt 으로 GET 호출을하면
    {"exec_info": {"queue_remaining": 2}}
    값을 받게되고, queue_remaining값을 반환하기
    '''
    return queue_remaining


def queue_prompt(prompt):
    '''
    수정 금지
    '''
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    req =  request.Request("http://127.0.0.1:8188/prompt", data=data)
    request.urlopen(req)


def load_prompt():
    prompt = json.loads(prompt_text) # 이부분은 prompt_text 대신 'video_api.yml파일 읽어오기
    return prompt

def edit_prompt(prompt):
    '''
    prompt의 구조 :
    {
        '순번 또는 텍스트' : {
            "inputs": {
                '설정값1' : ... ,
                'seed' : ... ,
                '어쩌구_seed' : ... ,
                '설정값2' : ... ,
                'seed_저쩌구' : ... ,
                '설정값3' : ... ,
            },
            '기타 등등 1' : ... ,
            '기타 등등 2' : ... ,
        }
    }

    기능 :
    prompt의 설정값 중에서 이름에 'seed'가 포함된 경우, 값을 랜덤 시드값으로 재설정
    '''
    
    pass

while True:

    # --- 건수를 1초마다 확인하면서 1개 이상인 경우 대기하기
    check_count()
    # ---
    
    prompt=load_prompt()

    edit_prompt(prompt)

    queue_prompt(prompt)

    # sleep 1초


