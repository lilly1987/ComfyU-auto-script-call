# ComfyU-auto-script6

최적화 및 재설계된 ComfyUI 자동화 스크립트

## 주요 개선사항

### 1. 모듈화 개선
- 공통 기능을 `utils` 모듈로 분리
- 각 모듈의 책임을 명확히 구분
- 코드 재사용성 향상
- 유지보수 용이

### 2. 타입 힌팅 추가
- 모든 함수와 메서드에 타입 힌팅 추가
- 코드 가독성 및 IDE 지원 향상

### 3. 에러 처리 개선
- try-except 블록 추가
- 명확한 에러 메시지
- 로깅 시스템 개선

### 4. 코드 중복 제거
- 공통 로직 함수화
- 일관된 인터페이스
- DRY 원칙 준수

### 5. 문서화 개선
- 모든 모듈과 함수에 docstring 추가
- README 파일 작성
- 설정 파일 주석 개선

### 6. 설정 파일 통합
- 단일 `config.yml` 파일로 통합
- 섹션별로 구분하여 관리

## 구조

```
ComfyU-auto-script6/
├── utils/                    # 유틸리티 모듈
│   ├── __init__.py
│   ├── config_loader.py      # 설정 파일 로더
│   ├── yaml_handler.py       # YAML 파일 처리
│   ├── file_handler.py       # 파일 처리 및 감시
│   ├── dict_utils.py         # 딕셔너리 유틸리티
│   ├── random_utils.py       # 랜덤 유틸리티
│   ├── type_utils.py         # 타입 유틸리티
│   ├── print_log.py          # 로깅 및 출력
│   ├── comfy_api.py          # ComfyUI API
│   ├── db_handler.py         # 데이터베이스 핸들러
│   ├── json_to_xlsx.py       # JSON to XLSX 변환
│   └── data_init.py          # 데이터 초기화
├── scripts/                   # 실행 스크립트 (필요시)
├── log/                      # 로그 파일 디렉토리
├── main.py                   # 메인 스크립트
├── run_script.py             # 실행 스크립트
├── _run_script.cmd           # Windows 실행 배치 파일
├── config.yml                # 설정 파일
└── README.md                 # 이 파일
```

## 사용 방법

### 1. 설정 파일 수정
`config.yml` 파일을 열어서 설정을 수정합니다.

### 2. 스크립트 실행

#### Windows
```cmd
_run_script.cmd
```

#### Python 직접 실행
```bash
python run_script.py
```

또는

```bash
python main.py
```

## 설정 파일 구조

```yaml
# 경로 설정
dataPath: ../ComfyU-auto-script_data
base_dir: W:\ComfyUI_windows_portable

# 처리할 타입 리스트
CheckpointTypes:
  IL: 2
  Pony: 1

# 경로 설정
CheckpointPath: ../ComfyUI/models/checkpoints
LoraPath: ../ComfyUI/models/loras
# ... 기타 설정
```

## 유틸리티 모듈

### ConfigLoader
설정 파일을 로드하고 관리합니다.

### YAMLHandler
YAML 파일을 읽고 쓰는 기능을 제공합니다.
- 주석 보존
- 중복 키 허용 옵션

### FileHandler
파일 처리 및 파일 시스템 감시 기능을 제공합니다.

### DictUtils
딕셔너리 관련 유틸리티 함수를 제공합니다.
- 중첩 딕셔너리 접근
- 딕셔너리 병합
- Path 객체 변환

### RandomUtils
랜덤 관련 유틸리티 함수를 제공합니다.
- 가중치 기반 랜덤 선택
- 범위 내 랜덤 값 생성
- 시드 생성

### PrintLog
로깅 및 출력 기능을 제공합니다.
- Rich 라이브러리 기반 콘솔 출력
- 파일 로깅
- HTML 로그 저장

### ComfyAPI
ComfyUI API 관련 기능을 제공합니다.
- 프롬프트 큐 추가
- 큐 대기

### DatabaseHandler
데이터베이스 관련 기능을 제공합니다.
- TinyDB 기반 데이터 저장
- JSON to XLSX 변환

## 주의사항

- 스크립트 실행 전에 `config.yml` 파일을 확인하세요.
- 백업을 권장합니다.
- YAML 파일의 주석은 보존됩니다.
- Python 3.7 이상이 필요합니다.

## 의존성

필요한 Python 패키지:
- rich
- watchdog
- ruamel.yaml
- tinydb
- pandas
- openpyxl
- safetensors

스크립트 실행 시 자동으로 설치를 시도합니다.

## 버전

- 버전: 6.0.0
- 기반: ComfyU-auto-script4
- 최적화 및 재설계 완료

