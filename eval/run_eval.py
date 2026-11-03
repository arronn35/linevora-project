"""Eval runner: runs cases through an extractor, scores them, gates on a threshold.

Usage:
  python eval/run_eval.py --cases eval/cases --extractor perfect --min-score 0.8
  python eval/run_eval.py --cases eval/cases --extractor empty --min-score 0.8  # gate fails

The `perfect` and `empty` extractors exist for the harness to test itself.
`scripted` runs the real extractor code path (model call + schema validation)
with scripted model responses: it is a plumbing test, not an accuracy
measurement — it is circular because the model responses are generated from
the expected output. Real accuracy measurement is done with the same runner
once a managed model adapter is added.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable

Extractor = Callable[[dict[str, Any]], dict[str, Any]]


def _norm(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def _requirement_score(expected: dict[str, Any], actual: dict[str, Any]) -> float:
    parts: list[float] = []
    if _norm(expected.get("product_type")):
        parts.append(
            1.0 if _norm(expected.get("product_type")) == _norm(actual.get("product_type")) else 0.0
        )
    if "quantity" in expected:
        parts.append(1.0 if expected.get("quantity") == actual.get("quantity") else 0.0)
    if "unit" in expected:
        parts.append(
            1.0 if _norm(expected.get("unit")) == _norm(actual.get("unit")) else 0.0
        )
    expected_features = expected.get("features") or {}
    if expected_features:
        actual_features = actual.get("features") or {}
        hits = sum(
            1
            for key, value in expected_features.items()
            if key in actual_features and _norm(actual_features[key]) == _norm(value)
        )
        parts.append(hits / len(expected_features))
    source = actual.get("source") or {}
    parts.append(1.0 if source.get("page") and source.get("quote") else 0.0)
    return sum(parts) / len(parts) if parts else 0.0


def score_case(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_reqs = expected.get("requirements", [])
    actual_reqs = actual.get("requirements", []) if isinstance(actual, dict) else []
    if not expected_reqs:
        score = 1.0 if not actual_reqs else 0.0
        return {"score": score, "expected_count": 0, "actual_count": len(actual_reqs)}
    used = [False] * len(actual_reqs)
    scores: list[float] = []
    for expected_req in expected_reqs:
        best, best_index = 0.0, -1
        for index, actual_req in enumerate(actual_reqs):
            if used[index] or not isinstance(actual_req, dict):
                continue
            current = _requirement_score(expected_req, actual_req)
            if current > best:
                best, best_index = current, index
        if best_index >= 0:
            used[best_index] = True
        scores.append(best)
    return {
        "score": sum(scores) / len(scores),
        "expected_count": len(expected_reqs),
        "actual_count": len(actual_reqs),
    }


def run_eval(
    cases: list[dict[str, Any]], extractor: Extractor
) -> dict[str, Any]:
    results = []
    for case in cases:
        actual = extractor(case)
        detail = score_case(case["expected"], actual)
        results.append({"id": case["id"], **detail})
    mean_score = sum(item["score"] for item in results) / len(results) if results else 0.0
    return {"cases": results, "mean_score": mean_score, "case_count": len(results)}


def load_cases(cases_dir: str) -> list[dict[str, Any]]:
    cases = []
    for name in sorted(os.listdir(cases_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(cases_dir, name), encoding="utf-8") as handle:
            cases.append(json.load(handle))
    return cases


def perfect_extractor(case: dict[str, Any]) -> dict[str, Any]:
    return case["expected"]


def empty_extractor(case: dict[str, Any]) -> dict[str, Any]:
    _ = case
    return {"requirements": []}


def scripted_extractor(case: dict[str, Any]) -> dict[str, Any]:
    import json as _json

    from linevora.ingest.extract import Page
    from linevora.matching.extractor import extract_requirements
    from linevora.model import FakeModelClient

    pages = (Page(number=1, text=case["input_text"]),)
    prompt = f"Page 1:\n{case['input_text']}"
    client = FakeModelClient(
        responses={prompt: _json.dumps(case["expected"], ensure_ascii=False)}
    )
    return {"requirements": extract_requirements(client, pages)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Linevora eval runner")
    parser.add_argument("--cases", default="eval/cases")
    parser.add_argument(
        "--extractor", choices=["perfect", "empty", "scripted"], default="perfect"
    )
    parser.add_argument("--min-score", type=float, default=0.8)
    args = parser.parse_args(argv)
    extractors = {
        "perfect": perfect_extractor,
        "empty": empty_extractor,
        "scripted": scripted_extractor,
    }
    extractor = extractors[args.extractor]
    report = run_eval(load_cases(args.cases), extractor)
    report["min_score"] = args.min_score
    report["gate"] = "pass" if report["mean_score"] >= args.min_score else "fail"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
