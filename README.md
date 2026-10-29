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

## 🔗 API — 노션 「웹사이트 명세」가 정본

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 서버 · 모델 로드 상태 |
| `GET` | `/segments?road=달구벌대로` | 구간별 도로 정보 + 모델 ① 예측 사고 건수 (위험 지도 · 역 배너) |
| `POST` | `/predict/risk` | 날짜 · 시간 · 구간 → 그 순간의 눈부심 위험도 |
| `POST` | `/predict/glare` | 화면에서 뽑은 숫자 → 정상 / 눈부심 / 심한 눈부심 + 확률 (모델 ②) |
| `GET` | `/models` | 모델 ① · ② 버전 · 검증 점수 · 중요 변수 (모델 결과 화면) |

## 📌 원칙

- 처음엔 같은 형식을 돌려주는 **가짜 모델**로 만들고, AI 저장소 Release의 파이프라인 파일로 교체합니다
- 서비스 쪽에서 **전처리를 다시 짜지 않습니다** (전처리는 파이프라인 파일 안에 있습니다)
- **scikit-learn 버전**은 AI 저장소 Release에 적힌 버전과 같게 맞춥니다
- `/segments` 결과는 같은 형식의 JSON 파일로도 내보내서 FE의 비상용 데이터로 씁니다
- 배포는 Render 무료 서버 (첫 요청이 느릴 수 있어 발표 캡처 전에 한 번 깨워 둡니다)

## 🚀 실행

```bash
pip install -r requirements.txt
```


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
