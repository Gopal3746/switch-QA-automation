import json
from pathlib import Path

from switch_qa.config import load_topology
from switch_qa.devices import Host, Switch
from switch_qa.diagnostics import EvidenceCollector
from switch_qa.simulated_transport import SimulatedTransport
from switch_qa.simulation import SimulatedTopologyState


def build_switch(
    switch_name: str,
    state: SimulatedTopologyState,
) -> Switch:
    config = state.config.switches[switch_name]
    transport = SimulatedTransport(switch_name, state)

    switch = Switch(
        name=switch_name,
        display_name=config.display_name,
        transport=transport,
    )
    switch.connect()
    return switch


def build_host(
    host_name: str,
    switch: Switch,
) -> Host:
    config = switch.transport.state.config.hosts[host_name]

    return Host(
        name=host_name,
        display_name=config.display_name,
        ip_address=config.ip_address,
        transport=switch.transport,
    )


def test_collects_switch_and_ping_evidence(
    tmp_path: Path,
) -> None:
    state = SimulatedTopologyState.from_config(load_topology())
    switch1 = build_switch("switch1", state)
    switch2 = build_switch("switch2", state)
    host_a = build_host("host_a", switch1)
    host_b = build_host("host_b", switch2)

    collector = EvidenceCollector(tmp_path)
    evidence_path = collector.collect(
        "TC-07",
        switches={
            "switch1": switch1,
            "switch2": switch2,
        },
        hosts={
            "host_a": host_a,
            "host_b": host_b,
        },
        failure="forced failure for collector test",
    )

    payload = json.loads(
        evidence_path.read_text(encoding="utf-8")
    )

    assert evidence_path == tmp_path / "TC-07" / "evidence.json"
    assert payload["test_id"] == "TC-07"
    assert payload["failure"] == "forced failure for collector test"

    switch_evidence = payload["switches"]["switch1"]
    commands = switch_evidence["commands"]

    assert commands["nv_show_interfaces"]["exit_code"] == 0
    assert "swp1" in commands["nv_show_interfaces"]["stdout"]
    assert "PVID" in commands["bridge_vlan_show"]["stdout"]
    assert "default via" in commands["ip_route_show"]["stdout"]

    ping = payload["host_pings"]["host_a->host_b"]

    assert ping["received"] == 4
    assert ping["packet_loss_percent"] == 0.0


def test_collection_errors_do_not_prevent_evidence_file(
    tmp_path: Path,
) -> None:
    state = SimulatedTopologyState.from_config(load_topology())
    switch1 = build_switch("switch1", state)
    switch1.disconnect()

    collector = EvidenceCollector(tmp_path)
    evidence_path = collector.collect(
        "TC-99 invalid/name",
        switches={"switch1": switch1},
    )

    payload = json.loads(
        evidence_path.read_text(encoding="utf-8")
    )
    command_evidence = payload["switches"]["switch1"]["commands"]

    assert evidence_path.exists()
    assert evidence_path.parent.name == "TC-99_invalid_name"
    assert "collection_error" in command_evidence["ip_link_show"]
