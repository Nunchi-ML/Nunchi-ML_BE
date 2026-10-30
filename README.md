<div align="center">

<img src="https://raw.githubusercontent.com/Nunchi-ML/.github/main/profile/assets/logo.png" width="96" alt="Nunchi-ML"/>

# Nunchi-ML_BE

눈부심 예측 API — 시뮬레이터에 모델 ① · ② 예측을 줘요

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![scikit--learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white) ![LightGBM](https://img.shields.io/badge/LightGBM-2E7D32?style=flat-square) ![Render](https://img.shields.io/badge/Render-46E3B7?style=flat-square&logo=render&logoColor=black)

[![Notion](https://img.shields.io/badge/Notion-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%20%ED%99%88-000000?style=flat-square&logo=notion&logoColor=white)](https://app.notion.com/p/40554fa7e143815680c0cfb0ff414d78) [![GitHub](https://img.shields.io/badge/GitHub-Nunchi--ML-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Nunchi-ML)

</div>

---

## 👥 담당

BE · PM

## 📁 폴더

```
📂 app/       API 코드
📂 models/    AI 저장소 Release에서 받은 파이프라인 파일   ← git에 올리지 않음
```

## 🔗 API — 현재 구현

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 서버 · 모델 로드 상태 |
| `POST` | `/predict/glare` | multipart JPEG `image`, `source=camera\|game` → 3단계·모델 점수·밝은 곳 후보 |

`/health`: `{"status":"ok","model2":"ready"}`. 모델 누락·해시·버전 불일치 시 `missing`, 추론은 503.

추론 출력은 `model_version`, `status=pilot`, `level`, `label`, `scores={normal,glare,severe}`, `brightest={x,y}`. scores는 보정 전 모델 점수이며 사고 확률이 아닙니다. brightest는 전체 화면의 밝은 후보(0~1, 좌상단 원점)이며 차광 좌표가 아닙니다.

오류는 `{"error":"CODE","message":"..."}`. 400 INVALID_IMAGE, 413 IMAGE_TOO_LARGE, 415 UNSUPPORTED_IMAGE_TYPE, 422 INVALID_REQUEST, 503 MODEL_NOT_READY, 500 INFERENCE_FAILED. OpenAPI는 `/docs`.

**Swagger UI**: 로컬 `http://127.0.0.1:8765/docs`. `/health` 실행 → `model2=ready` 확인 → `/predict/glare`의 **Try it out** → JPEG 파일 선택 → source `camera` 또는 `game` → **Execute**. 입력 제약·응답 예시·오류별 예시를 함께 제공합니다. OpenAPI JSON은 `/openapi.json`, 읽기용 ReDoc은 `/redoc`이며 Render 배포 후에도 같은 경로를 씁니다.

`/segments`, `/predict/risk`, `/models`는 현재 미구현입니다. 모델①은 고속도로 구간 건수 모델로 별도 검증하며 대구 실시간 사고 확률로 제공하지 않습니다.

## 📌 원칙

- AI export의 모델·meta.json과 `nunchi-glare` wheel을 함께 사용합니다. 전처리 코드는 이 패키지만 쓰며 BE/JS에 복제하지 않습니다.
- 전체 BGR 화면 → 640×368 INTER_LINEAR resize → 특징 12개 → LightGBM. 중앙 자르기·letterbox·미러링 없음.
- FE는 전체 프레임 비율 유지, 긴 변 최대 1280(확대 없음), JPEG quality 0.95, 1MiB 이하로 보냅니다. 초과 프레임은 건너뜁니다. 브라우저 인코더와 실기기 성능은 별도 확인합니다.
- 이미지 파일 1MiB, multipart 본문 1MiB+64KiB, 펼친 이미지 800만 픽셀 상한. 사진·위치 저장 및 로깅 없음.
- **FE Vercel + BE Render**. 신천대로·달구벌대로 모두 MVP 필수이며 모든 태양 조건을 지원합니다. BE는 도로·태양 조건으로 이미지 분류 요청을 제한하지 않습니다.
- `ALLOWED_ORIGINS`에 실제 Vercel 주소를 명시합니다. preview 도메인은 필요한 것만 추가합니다. FE API 주소는 `VITE_API_BASE_URL`.
- 모델 누락 시 가짜 판정 대신 503입니다. 기준 사진은 원래 라벨과 모델 예상 판정을 구분합니다.

## 🚀 실행

```bash
pip install -r requirements.txt
pip install --no-deps ../AI/models/model2-pilot-v1/nunchi_glare-0.1.0-py3-none-any.whl
```

AI 저장소에서 먼저 export해야 합니다. 로컬 PowerShell에서 BE 폴더 기준:

```powershell
$env:MODEL_DIR = (Resolve-Path ../AI/models/model2-pilot-v1).Path
$env:ALLOWED_ORIGINS = "http://localhost:5173,https://your-project.vercel.app"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

간단한 로컬 실행은 BE 폴더에서 `./scripts/dev.ps1`입니다. AI의 wheel을 직접 읽어 사용하므로 이 경우 전역 패키지 설치는 필요 없습니다(기본 Python 의존성은 필요). 기본 주소 `http://127.0.0.1:8765`, 허용 FE origin은 localhost:5173·127.0.0.1:5173입니다. 이 PC에서 8000·8001은 Windows가 바인딩을 거부해 8765를 사용합니다. `./scripts/dev.ps1 -Port 8000`처럼 포트를 바꿀 수 있습니다.

Render 설정은 `render.yaml`을 사용합니다. 무료 단일 Python 서비스, 자동 배포 끔, build에서 의존성 설치 → 팀 bundle 다운로드/해시 검증 → wheel 설치 → 기준 사진 3장 검수 순서입니다. 시작 명령은 `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`.

배포 전 필요한 값은 `MODEL_BUNDLE_URL`(팀 AI 저장소 Release의 태그가 고정된 zip URL), `MODEL_BUNDLE_SHA256`, 실제 Vercel 주소의 `ALLOWED_ORIGINS`입니다. `MODEL_DIR=models/model2-pilot-v1`. bundle은 AI README의 명령으로 생성합니다. 임의 다운로드 URL이나 사용자 업로드 모델은 사용하지 않습니다. 모델·원본 출처/이용 조건을 확인해 팀 Release로 전달한 뒤 Blueprint를 적용합니다. 현재 실제 Render 서비스 생성·클라우드 배포는 하지 않았습니다.

공식 설정 참고: [Render Blueprint 명세](https://render.com/docs/blueprint-spec). Render CLI가 연결된 환경에서는 `render blueprints validate render.yaml`로 검증합니다. 환경 파일은 자동 로드하지 않으므로 환경 변수를 직접 지정합니다.

검수: MODEL_DIR와 `MODEL_BUNDLE_PATH=../AI/models/model2-pilot-v1.zip` 설정 후 `python -m unittest discover -s tests -v` (테스트 도구 `httpx==0.28.1` 필요). `python scripts/verify_model.py`는 실제 JPEG 3장의 예측을 검수합니다. 원본·JPEG95 시범 점수와 fold·버전·해시는 meta.json에 있습니다. 2인 독립 라벨·실기기·국내 도로·시뮬레이터 화면 검증은 아직 남아 있습니다.


<details>
<summary><b>🤝 작업 규칙</b> (펼치기)</summary>

<br/>

| 항목 | 규칙 |
|---|---|
| 🌿 브랜치 | `feat/` 기능 · 실험 · `fix/` 버그 · `docs/` 문서 · `refactor/` 정리 · `data/` 데이터 처리 + 짧은 설명 (예: `feat/lgbm-baseline`) |
| ✍️ 커밋 | `feat: 베이스라인 모델 추가`처럼 접두어 + 한 줄 |
| 🔀 병합 | `main`에 바로 올리지 않고 PR → squash 병합 |
| 💬 공유 | 착수 전 슬랙 `[작업 시작]`, 병합 후 `[작업 정리]` + 노션 카드에 PR 링크 |
| 🔍 리뷰 | 코멘트 등급 P1 꼭 고침 · P2 고치면 좋음 · P3 의견 |
| 🏷️ 라벨 | 브랜치 이름으로 자동으로 붙음 |

📘 파일 이름 규칙 · 올리면 안 되는 것 · 설치 없이 웹에서 올리는 법: [노션 「GitHub 컨벤션」](https://app.notion.com/p/c86986ef9f3a4a3caedabfc16b6ff0b7)

</details>
