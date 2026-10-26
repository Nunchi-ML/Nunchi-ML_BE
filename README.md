# Nunchi-ML_BE

예측 API 저장소입니다. 담당: BE

## 폴더

```
app/       API 코드
models/    AI 저장소 Release에서 받은 파이프라인 파일 (git에 올리지 않음)
```

## 기준 (노션이 정본)

- 엔드포인트 · 입력 · 출력 형식: 노션 「API 명세」
- 처음엔 같은 형식을 돌려주는 가짜 모델로 만들고, AI 저장소 Release의 파이프라인 파일로 교체한다
- 서비스 쪽에서 전처리를 다시 짜지 않는다 (전처리는 파이프라인 파일 안에 있다)
- scikit-learn 버전은 AI 저장소 Release에 적힌 버전과 같게 맞춘다

## 실행

```bash
pip install -r requirements.txt
```

## 작업 규칙

- `main`에 바로 올리지 않고 브랜치 → PR → 1명 이상 승인 → squash 병합
- 브랜치: `feat/` 기능 · 실험, `fix/` 버그, `docs/` 문서, `refactor/` 정리, `data/` 데이터 처리 + 짧은 설명 (예: `feat/lgbm-baseline`)
- 커밋: `feat: 베이스라인 모델 추가`처럼 접두어 + 한 줄
- 착수 전 슬랙 `[작업 시작]`, 병합 후 `[작업 정리]` + 노션 카드에 PR 링크
- 리뷰 코멘트: P1 꼭 고침 · P2 고치면 좋음 · P3 의견
