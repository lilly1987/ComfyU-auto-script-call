import os
import re
import time
from huggingface_hub import HfApi

# 1. 설정 정보 입력
REPO_ID = "lillyai1987/backup"
api = HfApi()

# 2. 업로드할 로컬 폴더와 허깅페이스 대상 경로 매핑
tasks = [
    {
        "local_dir": r"D:\models\loras\IL\etc",
        "repo_dir": "IL/etc"
    },
    {
        "local_dir": r"D:\models\loras\Anime\etc",
        "repo_dir": "Anime/etc"
    },
]


def get_rate_limit_wait(error):
    """
    Rate Limit 오류 메시지에서 대기 시간을 초 단위로 추출합니다.
    예: 'You can retry this action in 28 minutes'
    """
    message = str(error)

    # Rate Limit 오류인지 확인
    if not re.search(r"rate limit|too many requests", message, re.I):
        return None

    # 분, 초 단위 대기 시간 추출
    match = re.search(
        r"retry this action in\s+"
        r"(?:(\d+)\s*hours?)?\s*"
        r"(?:(\d+)\s*minutes?)?\s*"
        r"(?:(\d+)\s*seconds?)?",
        message,
        re.I
    )

    if not match:
        return None

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    wait_seconds = hours * 3600 + minutes * 60 + seconds

    return wait_seconds if wait_seconds > 0 else None


# 3. 레포지토리에 이미 존재하는 파일 목록 가져오기
print("허깅페이스 레포지토리 파일 목록 확인 중...")

try:
    repo_files = api.list_repo_files(
        repo_id=REPO_ID,
        repo_type="model"
    )
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

    for filename in os.listdir(local_dir):
        local_file_path = os.path.join(local_dir, filename)

        if not os.path.isfile(local_file_path):
            continue

        path_in_repo = f"{repo_dir}/{filename}"

        if path_in_repo in existing_files:
            print(f"⏭️ [제외] 이미 존재함: {path_in_repo}")
            continue

        print(f"🚀 [업로드 중] {filename}...")

        # Rate Limit 오류라면 대기 후 재시도
        while True:
            try:
                api.upload_file(
                    path_or_fileobj=local_file_path,
                    path_in_repo=path_in_repo,
                    repo_id=REPO_ID,
                    repo_type="model",
                    commit_message=f"Upload {filename} to {repo_dir}"
                )

                print(f"✅ [완료] {path_in_repo} 업로드 및 커밋 성공")

                # 업로드 성공 후 목록 갱신
                existing_files.add(path_in_repo)
                break

            except Exception as e:
                wait_seconds = get_rate_limit_wait(e)

                if wait_seconds is not None:
                    print(f"\n⏳ Rate Limit 오류 발생: {e}")
                    print(
                        f"🕒 {wait_seconds // 3600}시간 "
                        f"{(wait_seconds % 3600) // 60}분 "
                        f"{wait_seconds % 60}초 대기 후 재시도합니다."
                    )

                    time.sleep(wait_seconds)

                    print(f"🔄 {filename} 업로드 재시도...")
                    continue

                print(f"❌ [실패] {filename} 업로드 중 오류 발생: {e}")
                break

print("\n✨ 모든 업로드 작업이 마무리되었습니다.")