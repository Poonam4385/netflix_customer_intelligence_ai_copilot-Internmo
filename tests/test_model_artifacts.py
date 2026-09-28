from src.models.common import MODELS

def test_model_artifacts_exist():
    for name in ["churn_pipeline.joblib","segmentation.joblib","clv_pipeline.joblib"]:
        assert (MODELS/name).exists()
