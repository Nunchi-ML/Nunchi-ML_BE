"""AI 공통 패키지에서 모델② 추론기를 불러온다 (전처리 코드는 BE에 복제하지 않음).

새 이름 nunchi_ml(AI src/nunchi_ml)을 먼저 쓰고, 첫 배포 묶음(model2-pilot-v1)의 옛 이름 nunchi_glare도 받는다.
"""
try:
    from nunchi_ml.glare.inference import GlarePredictor, sha256
except ModuleNotFoundError:
    from nunchi_glare.inference import GlarePredictor, sha256

__all__ = ["GlarePredictor", "sha256"]
