"""Human-readable and machine-readable QA test reporting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Requirement:
    """Requirement metadata for one QA test case."""

    test_id: str
    node_id: str
    category: str
    area: str
    requirement: str


@dataclass(frozen=True)
class CaseResult:
    """Execution result for one requirement-linked test case."""

    test_id: str
    node_id: str
    outcome: str
    duration_seconds: float
    category: str
    area: str
    requirement: str
    failure: str | None = None
    evidence_path: str | None = None


class RunReporter:
    """Collect QA case results and write summary reports."""

    def __init__(
        self,
        *,
        matrix_path: str | Path = "configs/test_matrix.yaml",
        output_directory: str | Path = "reports",
        scenario: str = "simulated",
    ) -> None:
        self.matrix_path = Path(matrix_path)
        self.output_directory = Path(output_directory)
        self.scenario = scenario
        self.requirements = self._load_requirements()
        self.results: list[CaseResult] = []

    def _load_requirements(self) -> dict[str, Requirement]:
        entries = yaml.safe_load(
            self.matrix_path.read_text(encoding="utf-8")
        )

        return {
            entry["id"]: Requirement(
                test_id=entry["id"],
                node_id=entry["test"],
                category=entry["category"],
                area=entry["area"],
                requirement=entry["requirement"],
            )
            for entry in entries
        }

    def record(
        self,
        *,
        test_id: str,
        node_id: str,
        outcome: str,
        duration_seconds: float,
        failure: str | None = None,
        evidence_path: str | None = None,
    ) -> None:
        """Record the result of one QA case."""

        requirement = self.requirements.get(test_id)

        if requirement is None:
            requirement = Requirement(
                test_id=test_id,
                node_id=node_id,
                category="unmapped",
                area="unmapped",
                requirement="No traceability entry found.",
            )

        self.results.append(
            CaseResult(
                test_id=test_id,
                node_id=node_id,
                outcome=outcome,
                duration_seconds=duration_seconds,
                category=requirement.category,
                area=requirement.area,
                requirement=requirement.requirement,
                failure=failure,
                evidence_path=evidence_path,
            )
        )

    def write(self) -> tuple[Path, Path]:
        """Write JSON and Markdown summaries."""

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        json_path = self.output_directory / "summary.json"
        markdown_path = self.output_directory / "summary.md"

        payload = self._build_payload()

        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        markdown_path.write_text(
            self._build_markdown(payload),
            encoding="utf-8",
        )

        return json_path, markdown_path

    def _build_payload(self) -> dict[str, object]:
        ordered_results = sorted(
            self.results,
            key=lambda result: result.test_id,
        )
        passed = sum(
            result.outcome == "passed"
            for result in ordered_results
        )
        failed = sum(
            result.outcome == "failed"
            for result in ordered_results
        )
        skipped = sum(
            result.outcome == "skipped"
            for result in ordered_results
        )

        return {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "scenario": self.scenario,
            "totals": {
                "collected": len(ordered_results),
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            },
            "cases": [
                asdict(result)
                for result in ordered_results
            ],
        }

    @staticmethod
    def _build_markdown(
        payload: dict[str, object],
    ) -> str:
        totals = payload["totals"]
        cases = payload["cases"]

        if not isinstance(totals, dict):
            raise TypeError("report totals must be a dictionary")

        if not isinstance(cases, list):
            raise TypeError("report cases must be a list")

        lines = [
            "# Switch QA Test Summary",
            "",
            f"- Scenario: `{payload['scenario']}`",
            f"- Collected: {totals['collected']}",
            f"- Passed: {totals['passed']}",
            f"- Failed: {totals['failed']}",
            f"- Skipped: {totals['skipped']}",
            "",
            "| ID | Area | Category | Result | Duration | Requirement |",
            "|---|---|---|---|---:|---|",
        ]

        for case in cases:
            if not isinstance(case, dict):
                continue

            duration = float(case["duration_seconds"])
            requirement = str(case["requirement"]).replace(
                "|",
                "\\|",
            )

            lines.append(
                f"| {case['test_id']} "
                f"| {case['area']} "
                f"| {case['category']} "
                f"| {str(case['outcome']).upper()} "
                f"| {duration:.4f}s "
                f"| {requirement} |"
            )

        failed_cases = [
            case
            for case in cases
            if isinstance(case, dict)
            and case["outcome"] == "failed"
        ]

        if failed_cases:
            lines.extend(
                [
                    "",
                    "## Failures",
                    "",
                ]
            )

            for case in failed_cases:
                lines.append(
                    f"### {case['test_id']}"
                )
                lines.append("")

                if case.get("evidence_path"):
                    lines.append(
                        f"Evidence: `{case['evidence_path']}`"
                    )
                    lines.append("")

                lines.append("```text")
                lines.append(
                    str(case.get("failure") or "No failure detail")
                )
                lines.append("```")
                lines.append("")

        return "\n".join(lines).rstrip() + "\n"
