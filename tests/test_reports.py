"""Missing information, version diff and alternative reports."""

import json

from linevora.model import FakeModelClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _upload(client, token, inquiry_id, content, name="t.txt"):
    return client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": (name, content.encode("utf-8"))},
        headers=_auth(token),
    )


def _process(client, token, inquiry_id, version_no):
    return client.post(
        f"/v1/inquiries/{inquiry_id}/versions/{version_no}/process",
        headers=_auth(token),
    )


def _script(app, scripts):
    app.state.model_client = FakeModelClient(
        responses={
            f"Page 1:\n{content}": json.dumps(expected, ensure_ascii=False)
            for content, expected in scripts
        }
    )


def _requirement(product_type, quote, **fields):
    requirement = {"product_type": product_type, "source": {"page": 1, "quote": quote}}
    requirement.update(fields)
    return requirement


def test_gaps_for_missing_fields(client, app, admin_token, inquiry_id):
    content = "centrifugal pump"
    _script(
        app,
        [(content, {"requirements": [_requirement("centrifugal pump", content)]})],
    )
    assert _upload(client, admin_token, inquiry_id, content).status_code == 201
    process = _process(client, admin_token, inquiry_id, 1)
    assert process.json()["status"] == "done"
    job = client.get(f"/v1/jobs/{process.json()['job_id']}", headers=_auth(admin_token))
    assert job.json()["result"]["gaps"] == 3
    gaps = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/gaps", headers=_auth(admin_token)
    )
    assert gaps.status_code == 200
    by_field = {gap["field"]: gap for gap in gaps.json()["gaps"]}
    assert set(by_field) == {"quantity", "unit", "features"}
    assert by_field["quantity"]["severity"] == "mandatory"
    assert by_field["unit"]["severity"] == "mandatory"
    assert by_field["features"]["severity"] == "info"
    assert all(gap["status"] == "open" for gap in by_field.values())
    assert all(gap["question"] for gap in by_field.values())


def test_exact_match_produces_no_alternatives(client, app, admin_token, inquiry_id):
    content = "DN50 centrifugal pump, 10 pcs"
    _script(
        app,
        [
            (
                content,
                {
                    "requirements": [
                        _requirement(
                            "centrifugal pump",
                            content,
                            features={"DN": "50"},
                            quantity=10,
                            unit="pcs",
                        )
                    ]
                },
            )
        ],
    )
    assert _upload(client, admin_token, inquiry_id, content).status_code == 201
    assert _process(client, admin_token, inquiry_id, 1).json()["status"] == "done"
    alternatives = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/alternatives",
        headers=_auth(admin_token),
    )
    assert alternatives.json() == {"alternatives": []}


def test_weak_match_produces_alternatives_with_comparison(
    client, app, admin_token, inquiry_id
):
    content = "compressor, 5 pcs"
    _script(
        app,
        [
            (
                content,
                {
                    "requirements": [
                        _requirement(
                            "compressor",
                            content,
                            features={"DN": "50"},
                            quantity=5,
                            unit="pcs",
                        )
                    ]
                },
            )
        ],
    )
    assert _upload(client, admin_token, inquiry_id, content).status_code == 201
    assert _process(client, admin_token, inquiry_id, 1).json()["status"] == "done"
    alternatives = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/alternatives",
        headers=_auth(admin_token),
    )
    items = alternatives.json()["alternatives"]
    assert len(items) == 1
    item = items[0]
    assert item["product"]["code"] == "P-001"
    assert item["score"] == 0.5
    rows = {row["criterion"]: row for row in item["comparison"]}
    assert rows["product name"]["match"] is False
    assert rows["feature:DN"] == {
        "criterion": "feature:DN",
        "wanted": "50",
        "offered": "50",
        "match": True,
    }
    assert rows["unit"]["match"] is True


def test_diff_reports_changes(client, app, admin_token, inquiry_id):
    first = "DN50 centrifugal pump, 10 pcs"
    second = "DN50 centrifugal pump, 12 pcs and 4 pcs DN80 gate valve"
    _script(
        app,
        [
            (
                first,
                {
                    "requirements": [
                        _requirement(
                            "centrifugal pump",
                            first,
                            features={"DN": "50"},
                            quantity=10,
                            unit="pcs",
                        )
                    ]
                },
            ),
            (
                second,
                {
                    "requirements": [
                        _requirement(
                            "centrifugal pump",
                            second,
                            features={"DN": "50"},
                            quantity=12,
                            unit="pcs",
                        ),
                        _requirement(
                            "gate valve",
                            second,
                            features={"DN": "80"},
                            quantity=4,
                            unit="pcs",
                        ),
                    ]
                },
            ),
        ],
    )
    assert _upload(client, admin_token, inquiry_id, first, "v1.txt").status_code == 201
    assert _upload(client, admin_token, inquiry_id, second, "v2.txt").status_code == 201
    assert _process(client, admin_token, inquiry_id, 1).json()["status"] == "done"
    assert _process(client, admin_token, inquiry_id, 2).json()["status"] == "done"
    diff = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/diff/2", headers=_auth(admin_token)
    )
    assert diff.status_code == 200
    body = diff.json()
    assert body["from_version"] == 1
    assert body["to_version"] == 2
    assert body["changes"] == [
        {
            "type": "changed",
            "product_type": "centrifugal pump",
            "field": "quantity",
            "old": 10,
            "new": 12,
        },
        {
            "type": "added",
            "product_type": "gate valve",
            "field": None,
            "old": None,
            "new": None,
        },
    ]


def test_diff_unknown_version_404(client, admin_token, inquiry_id):
    response = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/diff/9", headers=_auth(admin_token)
    )
    assert response.status_code == 404


def test_viewer_can_read_reports(client, viewer_token, inquiry_id):
    headers = _auth(viewer_token)
    gaps = client.get(f"/v1/inquiries/{inquiry_id}/versions/1/gaps", headers=headers)
    assert gaps.status_code == 404  # no version yet
    alternatives = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/alternatives", headers=headers
    )
    assert alternatives.status_code == 404


def test_viewer_reads_empty_reports_after_upload(
    client, app, admin_token, viewer_token, inquiry_id
):
    content = "DN50 centrifugal pump, 10 pcs"
    _script(
        app,
        [
            (
                content,
                {
                    "requirements": [
                        _requirement(
                            "centrifugal pump",
                            content,
                            features={"DN": "50"},
                            quantity=10,
                            unit="pcs",
                        )
                    ]
                },
            )
        ],
    )
    assert _upload(client, admin_token, inquiry_id, content).status_code == 201
    headers = _auth(viewer_token)
    assert client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/gaps", headers=headers
    ).json() == {"gaps": []}
    assert client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/alternatives", headers=headers
    ).json() == {"alternatives": []}


def test_reprocess_replaces_gaps(client, app, admin_token, inquiry_id):
    content = "centrifugal pump, 10 pcs"
    _script(
        app,
        [
            (
                content,
                {
                    "requirements": [
                        _requirement(
                            "centrifugal pump",
                            content,
                            features={"DN": "50"},
                            quantity=10,
                        )
                    ]
                },
            )
        ],
    )
    assert _upload(client, admin_token, inquiry_id, content).status_code == 201
    assert _process(client, admin_token, inquiry_id, 1).json()["status"] == "done"
    assert _process(client, admin_token, inquiry_id, 1).json()["status"] == "done"
    gaps = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/gaps", headers=_auth(admin_token)
    )
    assert [gap["field"] for gap in gaps.json()["gaps"]] == ["unit"]
