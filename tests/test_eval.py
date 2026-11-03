"""Eval runner: scoring and gate logic."""

from eval.run_eval import (
    empty_extractor,
    perfect_extractor,
    run_eval,
    score_case,
    scripted_extractor,
)

CASE = {
    "id": "t",
    "expected": {
        "requirements": [
            {
                "product_type": "pump",
                "quantity": 10,
                "unit": "pcs",
                "source": {"page": 1, "quote": "x"},
            }
        ]
    },
}


def test_perfect_scores_one():
    report = run_eval([CASE], perfect_extractor)
    assert report["mean_score"] == 1.0


def test_empty_scores_zero():
    report = run_eval([CASE], empty_extractor)
    assert report["mean_score"] == 0.0


def test_partial_credit_for_missing_source():
    actual = {"requirements": [{"product_type": "pump", "quantity": 10, "unit": "pcs"}]}
    detail = score_case(CASE["expected"], actual)
    assert 0.0 < detail["score"] < 1.0


def test_wrong_product_type_scores_low():
    actual = {
        "requirements": [
            {
                "product_type": "valve",
                "quantity": 10,
                "unit": "pcs",
                "source": {"page": 1, "quote": "x"},
            }
        ]
    }
    detail = score_case(CASE["expected"], actual)
    assert detail["score"] < 0.8


def test_scripted_extractor_uses_real_code_path():
    case = {
        "id": "s",
        "input_text": "10 pcs pump",
        "expected": {
            "requirements": [
                {
                    "product_type": "pump",
                    "source": {"page": 1, "quote": "10 pcs pump"},
                }
            ]
        },
    }
    assert scripted_extractor(case) == case["expected"]
