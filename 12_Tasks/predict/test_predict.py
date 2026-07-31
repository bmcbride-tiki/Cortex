# Copyright 2025 Brian McBride at Tiki-1 Studio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import predict as mod


def test_missing_model_fails():
    result = mod.Predict().run("", '{"x": 1}')
    assert result["success"] is False


def test_missing_input_dataset_fails():
    result = mod.Predict().run("churn-model", "")
    assert result["success"] is False


def test_run_returns_honest_mock_prediction():
    result = mod.Predict().run("churn-model", '{"x": 1}')
    assert result["success"] is True
    assert result["response"]["model"] == "churn-model"
    assert "MOCK" in result["response"]["prediction"]
    assert result["response"]["confidence"] is None


if __name__ == "__main__":
    test_missing_model_fails()
    test_missing_input_dataset_fails()
    test_run_returns_honest_mock_prediction()
    print("All predict self-checks passed.")
