"""Diagnostic evidence collection for failed switch QA cases."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from switch_qa.devices import Host, Switch

DIAGNOSTIC_COMMANDS = {
    "nv_show_interfaces": "nv show interface -o json",
    "bridge_vlan_show": "bridge vlan show",
    "ip_link_show": "ip link show",
    "ip_address_show": "ip addr show",
    "ip_route_show": "ip route show",
}


class EvidenceCollector:
    """Collect and persist diagnostics without masking the original failure."""

    def __init__(
        self,
        output_directory: str | Path = "reports/evidence",
    ) -> None:
        self.output_directory = Path(output_directory)

    def collect(
        self,
        test_id: str,
        *,
        switches: Mapping[str, Switch],
        hosts: Mapping[str, Host] | None = None,
        failure: str | None = None,
    ) -> Path:
        """Capture switch diagnostics and host connectivity evidence."""

        payload: dict[str, Any] = {
            "test_id": test_id,
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "failure": failure,
            "switches": {},
            "host_pings": {},
        }

        for switch_name, switch in switches.items():
            payload["switches"][switch_name] = (
                self._capture_switch(switch)
            )

        if hosts:
            payload["host_pings"] = self._capture_pings(hosts)

        evidence_directory = (
            self.output_directory / self._safe_name(test_id)
        )
        evidence_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        evidence_path = evidence_directory / "evidence.json"
        evidence_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return evidence_path

    def _capture_switch(
        self,
        switch: Switch,
    ) -> dict[str, Any]:
        commands: dict[str, Any] = {}

        for label, command in DIAGNOSTIC_COMMANDS.items():
            try:
                result = switch.run_command(command)
                commands[label] = {
                    "command": command,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            except Exception as error:  # noqa: BLE001
                commands[label] = {
                    "command": command,
                    "collection_error": (
                        f"{type(error).__name__}: {error}"
                    ),
                }

        return {
            "display_name": switch.display_name,
            "commands": commands,
        }

    @staticmethod
    def _capture_pings(
        hosts: Mapping[str, Host],
    ) -> dict[str, Any]:
        pings: dict[str, Any] = {}

        for source_name, source in hosts.items():
            for target_name, target in hosts.items():
                if source_name == target_name:
                    continue

                label = f"{source_name}->{target_name}"

                try:
                    result = source.ping(
                        target.ip_address,
                        count=4,
                    )
                    pings[label] = {
                        "source": source.ip_address,
                        "target": target.ip_address,
                        "transmitted": result.transmitted,
                        "received": result.received,
                        "packet_loss_percent": (
                            result.packet_loss_percent
                        ),
                        "exit_code": result.exit_code,
                        "output": result.output,
                    }
                # Evidence collection is best-effort and must never mask the test failure.
                except Exception as error:  # noqa: BLE001
                    pings[label] = {
                        "source": source.ip_address,
                        "target": target.ip_address,
                        "collection_error": (
                            f"{type(error).__name__}: {error}"
                        ),
                    }

        return pings

    @staticmethod
    def _safe_name(value: str) -> str:
        safe_name = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            value,
        )
        return safe_name.strip("_") or "unknown-test"
