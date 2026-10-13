import os
from huggingface_hub import HfApi

# 1. 설정 정보 입력
REPO_ID = "lillyai1987/backup"  # 허깅페이스 레포지토리 ID
api = HfApi()

# 2. 업로드할 로컬 폴더와 허깅페이스 대상 경로 매핑
# (Windows 경로인 \를 허깅페이스가 인식하는 /로 자동 변환 처리합니다)
tasks = [
    # {
        # "local_dir": r"D:\models\loras\IL\char",
        # "repo_dir": "IL/char"
    # },
    {
        "local_dir": r"D:\models\loras\IL\etc",
        "repo_dir": "IL/etc"
    },
    {
        "local_dir": r"D:\models\loras\Anime\etc",
        "repo_dir": "Anime/etc"
    },
    # {
        # "local_dir": r"D:\models\loras\Anime\char",
        # "repo_dir": "Anime/char"
    # },
]

# 3. 레포지토리에 이미 존재하는 파일 목록 가져오기
print("허깅페이스 레포지토리 파일 목록 확인 중...")
try:
    repo_files = api.list_repo_files(repo_id=REPO_ID, repo_type="model")
    # 빠른 검색을 위해 set 자료형으로 변환
    existing_files = set(repo_files) 
except Exception as e:
    print(f"목록을 가져오는데 실패했습니다: {e}")
    existing_files = set()

# 4. 각 작업별 파일 순회 및 업로드
for task in tasks:
    local_dir = task["local_dir"]
    repo_dir = task["repo_dir"]
    
    if not os.path.exists(local_dir):
        print(f"❌ 로컬 폴더가 존재하지 않습니다: {local_dir}")
        continue
        
    print(f"\n📂 작업 시작: {local_dir} ➡️ {repo_dir}")
    
    # 로컬 폴더 내의 파일들을 하나씩 확인
    for filename in os.listdir(local_dir):
        local_file_path = os.path.join(local_dir, filename)
        
        # 폴더가 아닌 '파일'인 경우만 처리
        if os.path.isfile(local_file_path):
            # 허깅페이스 상의 저장 경로 생성 (예: IL/etc/filename.safetensors)
            path_in_repo = f"{repo_dir}/{filename}"
            
            # 이미 올라가 있는 파일인지 체크
            if path_in_repo in existing_files:
                print(f"⏭️  [제외] 이미 존재함: {path_in_repo}")
                continue
                
            # 존재하지 않는 새 파일인 경우 개별 업로드 및 커밋
            print(f"🚀 [업로드 중] {filename}...")
            try:
                api.upload_file(
                    path_or_fileobj=local_file_path,
                    path_in_repo=path_in_repo,
                    repo_id=REPO_ID,
                    repo_type="model",
                    commit_message=f"Upload {filename} to {repo_dir}"
                )
                print(f"✅ [완료] {path_in_repo} 업로드 및 커밋 성공")
            except Exception as e:
                print(f"❌ [실패] {filename} 업로드 중 오류 발생: {e}")

print("\n✨ 모든 업로드 작업이 마무리되었습니다.")