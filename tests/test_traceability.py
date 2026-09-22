from pathlib import Path

import yaml

MATRIX_PATH = Path("configs/test_matrix.yaml")


def test_traceability_matrix_defines_thirteen_unique_cases() -> None:
    entries = yaml.safe_load(
        MATRIX_PATH.read_text(encoding="utf-8")
    )

    expected_ids = [
        f"TC-{number:02d}"
        for number in range(1, 14)
    ]
    actual_ids = [entry["id"] for entry in entries]

    assert actual_ids == expected_ids
    assert len(set(actual_ids)) == 13

    for entry in entries:
        test_path = Path(entry["test"].split("::", maxsplit=1)[0])

        assert test_path.exists()
        assert entry["requirement"]
        assert entry["category"]
        assert entry["area"]
