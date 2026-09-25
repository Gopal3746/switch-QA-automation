import json
from pathlib import Path

from switch_qa.reporter import RunReporter


def test_writes_json_summary(
    tmp_path: Path,
) -> None:
    reporter = RunReporter(
        output_directory=tmp_path,
        scenario="unit-test",
    )

    reporter.record(
        test_id="TC-01",
        node_id=(
            "tests/qa/test_vlan.py::"
            "test_access_ports_use_expected_pvid"
        ),
        outcome="passed",
        duration_seconds=0.0123,
    )
    reporter.record(
        test_id="TC-09",
        node_id=(
            "tests/qa/test_negative.py::"
            "test_missing_trunk_vlan_is_detected"
        ),
        outcome="failed",
        duration_seconds=0.0456,
        failure="VLAN 10 was missing",
        evidence_path=(
            "reports/evidence/TC-09/evidence.json"
        ),
    )

    json_path, markdown_path = reporter.write()

    payload = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    assert json_path == tmp_path / "summary.json"
    assert markdown_path == tmp_path / "summary.md"
    assert payload["scenario"] == "unit-test"
    assert payload["totals"] == {
        "collected": 2,
        "passed": 1,
        "failed": 1,
        "skipped": 0,
    }

    first_case = payload["cases"][0]

    assert first_case["test_id"] == "TC-01"
    assert first_case["area"] == "VLAN"
    assert first_case["category"] == "functional"


def test_writes_markdown_failure_details(
    tmp_path: Path,
) -> None:
    reporter = RunReporter(output_directory=tmp_path)

    reporter.record(
        test_id="TC-10",
        node_id=(
            "tests/qa/test_negative.py::"
            "test_incorrect_access_pvid_is_detected"
        ),
        outcome="failed",
        duration_seconds=0.1,
        failure="expected PVID 10 but received 20",
        evidence_path=(
            "reports/evidence/TC-10/evidence.json"
        ),
    )

    _, markdown_path = reporter.write()
    markdown = markdown_path.read_text(encoding="utf-8")

    assert "# Switch QA Test Summary" in markdown
    assert "| TC-10 | VLAN | negative | FAILED" in markdown
    assert "## Failures" in markdown
    assert "expected PVID 10 but received 20" in markdown
    assert "reports/evidence/TC-10/evidence.json" in markdown
