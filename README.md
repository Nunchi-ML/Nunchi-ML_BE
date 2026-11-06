<div align="center">

<img src="https://raw.githubusercontent.com/Nunchi-ML/.github/main/profile/assets/logo.png" width="96" alt="Nunchi-ML"/>

# Nunchi-ML_BE

눈부심 판정 API — 운전 시뮬레이터에 태양광 눈부심 분류 결과를 줘요

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![scikit--learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white) ![LightGBM](https://img.shields.io/badge/LightGBM-2E7D32?style=flat-square) ![Render](https://img.shields.io/badge/Render-46E3B7?style=flat-square&logo=render&logoColor=black)

[![Notion](https://img.shields.io/badge/Notion-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%20%ED%99%88-000000?style=flat-square&logo=notion&logoColor=white)](https://app.notion.com/p/40554fa7e143815680c0cfb0ff414d78) [![GitHub](https://img.shields.io/badge/GitHub-Nunchi--ML-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Nunchi-ML)

</div>

---

## 👥 담당

이성진

## 🧭 한눈에 보기

| API | 쓰는 모델 | 상태 |
|---|---|---|
| `POST /predict/glare` | 사진만 보는 이전 시범 모델 | 운영 (Render) · 시뮬레이터 카메라 앱이 사용 |
| `POST /predict/glare/photo-g` | 발표 선정 모델 (사진 + 해 위치·날씨) | **운영 (Render)** · 모델 묶음은 AI Release `model2-photo-g-prototype-v1` |
| `POST /predict/glare/prototype` | 같은 모델의 로컬 시제품 앱 | 로컬 검토용 |
| 통합 주행 안내 · 밝기 전환 부담 | — | 미구현 |

## 📁 폴더 — 어디에 뭘 두나

```
📂 app/                    API 코드
 ├─ main.py                앱 설정만 (문서 · CORS · 오류 · 모델 불러오기 · 라우터 연결)
 ├─ 📂 routers/            주소별 처리 — 모델마다 파일 하나
 │   ├─ health.py          GET  /health
 │   └─ glare.py           POST /predict/glare  (모델 ②)  ← 모델 ①은 risk.py, 구간 목록은 segments.py 로 추가
 ├─ predictor.py           AI 공통 패키지(nunchi_ml)에서 모델 추론기 불러오기
 ├─ image.py               받은 사진 검사 (JPEG · 1MB · 800만 픽셀)
 ├─ errors.py              오류 코드 · 한국어 안내 · Swagger 예시
 └─ middleware.py          요청 크기 제한
📂 scripts/                모델 받기 · 검수 · 배포 도구 (install_model · verify_model · deploy_render · dev.ps1)
📂 tests/                  API · 모델 묶음 · 배포 테스트 — PR마다 자동으로 돌아감
📂 deployment/model.json   서버에 올릴 모델 버전 · 주소 · 지문(sha256) — 모델 바꿀 땐 이 파일만 PR로 바꿈
📂 models/                 AI Release에서 받은 모델 파일     ← git에 안 올림
```

### 새 API를 붙일 때

1. `app/routers/<이름>.py` 에 `router = APIRouter(...)` 와 주소 함수 작성 (예시는 `glare.py`)
2. `app/main.py` 에서 `app.include_router(<이름>.router)` 한 줄 추가
3. `tests/` 에 테스트 추가 → PR

- 모델 계산 코드는 여기 복제하지 않고 AI 저장소 `src/nunchi_ml/` 에 두고 가져다 써요 (학습 · 서버가 같은 코드)
- 원본 데이터 · 모델 파일은 git에 안 올려요 — 모델은 AI 저장소 GitHub Release로 받아요

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

## 사진+G 로컬 시제품 — 승인된 별도 API

`app.prototype`는 사용자가 발표용으로 선택한 `B_geometry_aug`를 실제 JPEG와 촬영 정보로 실행하는 별도 앱입니다. 2026-11-06 사용자가 아래 사진+G API 계약과 BE·FE 코드의 푸시/PR 생성을 승인했습니다. 운영 `app.main`에는 연결하지 않았으며 운영 적용·배포는 별도 검증 대상입니다.

- `POST /predict/glare/prototype`: multipart `image`(JPEG 원본, 1MiB·800만 픽셀 이하), `context`(8KiB 이하 JSON). 사진을 축소하거나 G 값을 가정해서 보내지 않습니다.
- context 필수: `lat`, `lon`, `heading`(북=0, 시계 방향, 360 미만), `focal`(긴 변 기준 정규화 초점거리), `width`, `height`, `captured_at`(시간대 포함), `cloud`(0~10), `sunshine`(0~1), `weather_observed_at`, `weather_source`, `geometry_source`, `projection="legacy_level_assumed"`. 선택 `weather_available_at`. 원본 크기와 촬영 전 1시간 이내 기상 관측을 검사하며, 누락·오래된 기상·촬영 이후 공개 정보를 정상으로 채우지 않습니다.
- 응답: `status="prototype"`, `variant="B_geometry_aug"`, `model_version="photo-g-candidate-v1"`, 등급/점수, 두 단계 A/B 점수, 사진 SHA-256, 촬영시각·기상 관측 나이·공개시각 확인 여부. 카메라 자세/도로변/미래 경로 검증은 모두 `false`입니다. `.5/.5` 조건부 판정이므로 joint 점수 argmax와 다를 수 있습니다.
- 오류: 기존 이미지 오류에 더해 context 구조/누락 422 `INVALID_REQUEST`, 사진 크기·관측시각 불일치 400 `INVALID_CONTEXT`. 모델 누락은 503, 분석·응답 검증 실패는 500입니다. 요청 사진/촬영 정보는 저장하지 않습니다.
- `processing_ms`는 G·모델 계산 시간이며 JPEG 디코딩·업로드/네트워크·화면 표시 시간은 제외합니다. FE의 요청 시간은 사진 지문 확인부터 응답 검증까지입니다. 촬영→운전자 알림 지연으로 해석하지 않습니다.

BE 폴더 기준으로 로컬에서만 실행합니다. 모델 묶음·원본 사진·실제 촬영 정보는 공개 저장소에 넣지 않습니다.

```powershell
python -m pip install -r requirements-prototype.txt
./scripts/prototype.ps1 -Bundle '../AI/data/prototype_reference_20261106'
```

실행기는 묶음의 wheel/meta/parameters 체크섬을 확인하고 wheel을 임시 폴더에 풀어 공통 AI 코드를 불러옵니다. 기존 시범 패키지를 덮어쓰지 않습니다. API 주소는 `http://127.0.0.1:8766`, 문서는 `/docs`이며 로컬 FE origin 5173만 기본 허용합니다. 다른 origin은 `PROTOTYPE_ALLOWED_ORIGINS`로 명시합니다. 별도 FE의 `/photo-g/` 화면에서 사진과 해당 촬영 정보 JSON을 선택해 분석합니다.

테스트: `python -m unittest discover -s tests -p test_prototype.py -v`. 실제 모델 대조는 `HYBRID_TEST_BUNDLE`, `HYBRID_TEST_IMAGE`, `HYBRID_TEST_CONTEXT`를 비공개 자료 경로로 설정한 경우 실행합니다. CI의 합성 HTTP 경계 테스트와 실제 모델의 정확도 평가는 구분합니다. 도시 CCTV 연결과 미래 경로·운전자 실제 시야/사고 효과 검증은 확장 과제입니다.

## 📌 원칙

- AI export의 모델·meta.json과 공통 코드 wheel(`nunchi-ml`, 첫 묶음 `model2-pilot-v1`은 옛 이름 `nunchi-glare`)을 함께 사용합니다. 전처리 코드는 이 패키지만 쓰며 BE/JS에 복제하지 않습니다. `app/predictor.py`가 두 이름을 모두 받습니다.
- 전체 BGR 화면 → 640×368 INTER_LINEAR resize → 특징 12개 → LightGBM. 중앙 자르기·letterbox·미러링 없음.
- FE는 전체 프레임 비율 유지, 긴 변 최대 1280(확대 없음), JPEG quality 0.95, 1MiB 이하로 보냅니다. 초과 프레임은 건너뜁니다. 브라우저 인코더와 실기기 성능은 별도 확인합니다.
- 이미지 파일 1MiB, multipart 본문 1MiB+64KiB, 펼친 이미지 800만 픽셀 상한. 사진·위치 저장 및 로깅 없음.
- **FE Vercel + BE Render**. 신천대로·달구벌대로 모두 MVP 필수이며 모든 태양 조건을 지원합니다. BE는 도로·태양 조건으로 이미지 분류 요청을 제한하지 않습니다.
- `ALLOWED_ORIGINS`에 실제 Vercel 주소를 명시합니다. preview 도메인은 필요한 것만 추가합니다. FE API 주소는 `VITE_API_BASE_URL`.
- 모델 누락 시 가짜 판정 대신 503입니다. 기준 사진은 원래 라벨과 모델 예상 판정을 구분합니다.

## 🚀 실행

```bash
pip install -r requirements.txt
python scripts/install_model.py   # deployment/model.json 의 Release 묶음을 받아 확인하고 공통 코드 wheel까지 설치
```

AI 저장소에서 먼저 export해야 합니다. 로컬 PowerShell에서 BE 폴더 기준:

```powershell
$env:MODEL_DIR = (Resolve-Path ../AI/models/model2-pilot-v1).Path
$env:ALLOWED_ORIGINS = "http://localhost:5173,https://your-project.vercel.app"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

간단한 로컬 실행은 BE 폴더에서 `./scripts/dev.ps1`입니다. AI의 wheel을 직접 읽어 사용하므로 이 경우 전역 패키지 설치는 필요 없습니다(기본 Python 의존성은 필요). 기본 주소 `http://127.0.0.1:8765`, 허용 FE origin은 localhost:5173·127.0.0.1:5173입니다. 이 PC에서 8000·8001은 Windows가 바인딩을 거부해 8765를 사용합니다. `./scripts/dev.ps1 -Port 8000`처럼 포트를 바꿀 수 있습니다.

Render 설정은 `render.yaml`을 사용합니다. 무료 단일 Python 서비스, 자동 배포 끔, build에서 의존성 설치 → 팀 bundle 다운로드/해시 검증 → wheel 설치 → 기준 사진 3장 검수 순서입니다. 시작 명령은 `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`.

모델은 `deployment/model.json`의 고정 Release URL·SHA-256을 CI와 Render가 함께 사용합니다. [모델② 시범 Release](https://github.com/Nunchi-ML/Nunchi-ML_AI/releases/tag/model2-pilot-v1). `MODEL_DIR=models/model2-pilot-v1`, 운영은 `MODEL_REQUIRED=true`이며 모델 로딩 실패 시 서버 시작을 중단합니다. URL·SHA 환경 변수는 둘을 함께 지정할 때만 선택적으로 덮어씁니다. `ALLOWED_ORIGINS`에는 실제 Vercel 주소를 지정합니다. 실제 Render 계정·서비스 연결은 별도 초기 설정이 필요합니다.

공식 설정 참고: [Render Blueprint 명세](https://render.com/docs/blueprint-spec). Render CLI가 연결된 환경에서는 `render blueprints validate render.yaml`로 검증합니다. 환경 파일은 자동 로드하지 않으므로 환경 변수를 직접 지정합니다.

검수: MODEL_DIR와 `MODEL_BUNDLE_PATH=../AI/models/model2-pilot-v1.zip` 설정 후 `python -m unittest discover -s tests -v` (테스트 도구 `httpx==0.28.1` 필요). `python scripts/verify_model.py`는 실제 JPEG 3장의 예측을 검수합니다. 원본·JPEG95 시범 점수와 fold·버전·해시는 meta.json에 있습니다. 2인 독립 라벨·실기기·국내 도로·시뮬레이터 화면 검증은 아직 남아 있습니다.

## CI/CD

`.github/workflows/ci-cd.yml`:

- PR → Ubuntu/Python 3.13에서 의존성 설치, Render 스키마 검증, 고정 모델 bundle 설치·실제 JPEG 검수, 전체 단위·API·Swagger·배포 제어 테스트.
- main push 또는 main 수동 실행 → CI 통과 후 해당 **commit SHA**를 Render API로 배포. 최신 main이 아니면 오래된 배포는 건너뜁니다.
- Render의 해당 deploy가 `live`인지, 배포 commit이 같은지 확인 → 모델 ready·OpenAPI·Swagger·기준 사진 3장 실제 응답을 점검합니다. 이전 서버의 health 200만으로 성공 처리하지 않습니다.
- Render 자동 배포는 **Off**로 유지합니다. GitHub Actions만 배포를 제어하며 배포 작업은 동시에 하나씩 실행합니다.
- PR과 feature branch 수동 실행에서는 운영 배포·Render 시크릿 접근을 하지 않습니다.

처음 한 번 설정:

1. PR 검토 후 이성진이 main에 병합합니다. AI가 자동 병합하지 않습니다.
2. Render에서 이 BE 저장소의 `render.yaml`을 Blueprint로 적용합니다. 무료 Python Web Service·Singapore·main·자동 배포 Off. ALLOWED_ORIGINS에 Vercel 주소를 입력합니다.
3. GitHub BE 저장소 Actions secret **RENDER_API_KEY**, Actions variable **RENDER_SERVICE_ID**(`srv-...`)를 설정합니다. **FRONTEND_ORIGIN** variable을 지정하면 실제 CORS 응답까지 검사합니다.
4. Actions의 Backend CI and Render CD → main → Run workflow로 첫 배포 파이프라인을 검수합니다. 이후 main push 때 자동 실행됩니다.

값을 채팅이나 커밋에 넣을 필요 없이 GitHub 설정 화면 또는 다음 CLI로 등록합니다:

```bash
gh secret set RENDER_API_KEY --repo Nunchi-ML/Nunchi-ML_BE
gh variable set RENDER_SERVICE_ID --repo Nunchi-ML/Nunchi-ML_BE --body srv-YOUR_SERVICE_ID
gh variable set FRONTEND_ORIGIN --repo Nunchi-ML/Nunchi-ML_BE --body https://YOUR_PROJECT.vercel.app
```

새 모델은 새 Release 태그·bundle·SHA를 만들고 deployment/model.json을 PR로 변경합니다. CI에서 검증한 모델과 운영 모델이 같은 설정을 사용합니다. [Render API 배포 명세](https://api-docs.render.com/reference/create-deploy).


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
