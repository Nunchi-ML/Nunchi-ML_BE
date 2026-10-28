<div align="center">

<img src="https://raw.githubusercontent.com/Nunchi-ML/.github/main/profile/assets/logo.png" width="96" alt="Nunchi-ML"/>

# Nunchi-ML_BE

모델 결과 · 예측 API — 머신러닝 결과 웹사이트에 데이터를 줘요

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![scikit--learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)

[![Notion](https://img.shields.io/badge/Notion-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%20%ED%99%88-000000?style=flat-square&logo=notion&logoColor=white)](https://app.notion.com/p/40554fa7e143815680c0cfb0ff414d78) [![GitHub](https://img.shields.io/badge/GitHub-Nunchi--ML-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Nunchi-ML)

</div>

---

## 👥 담당

BE (1일차에 정해요)

## 📁 폴더

```
📂 app/       API 코드
📂 models/    AI 저장소 Release에서 받은 파이프라인 파일   ← git에 올리지 않음
```

## 🔗 API — 노션 「API 명세」가 정본

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 서버 · 모델 로드 상태 |
| `GET` | `/models` | 모델별 검증 점수 · 최종 모델 · 중요 변수 (모델 비교 · 중요 변수 화면) |
| `POST` | `/predict` | 입력 1건 → 예측 결과 · 확률 · 크게 작용한 변수 (예측해 보기 화면) |

## 📌 원칙

- 처음엔 같은 형식을 돌려주는 **가짜 모델**로 만들고, AI 저장소 Release의 파이프라인 파일로 교체합니다
- 서비스 쪽에서 **전처리를 다시 짜지 않습니다** (전처리는 파이프라인 파일 안에 있습니다)
- **scikit-learn 버전**은 AI 저장소 Release에 적힌 버전과 같게 맞춥니다

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
