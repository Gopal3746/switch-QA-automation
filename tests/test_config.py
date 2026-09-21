from pathlib import Path

import pytest

from switch_qa.config import TopologyConfigError, load_topology

TOPOLOGY_PATH = Path("configs/topology.yaml")


def test_loads_two_switch_topology() -> None:
    topology = load_topology(TOPOLOGY_PATH)

    assert set(topology.switches) == {"switch1", "switch2"}
    assert set(topology.hosts) == {"host_a", "host_b"}
    assert topology.vlans == {
        10: "engineering",
        20: "management",
    }


def test_access_ports_use_engineering_vlan() -> None:
    topology = load_topology(TOPOLOGY_PATH)

    assert topology.switches["switch1"].ports["swp1"].expected_pvid == 10
    assert topology.switches["switch2"].ports["swp2"].expected_pvid == 10
    assert topology.hosts["host_a"].expected_vlan == 10
    assert topology.hosts["host_b"].expected_vlan == 10


def test_trunk_ports_carry_required_vlans() -> None:
    topology = load_topology(TOPOLOGY_PATH)

    switch1_trunk = topology.switches["switch1"].ports["swp2"]
    switch2_trunk = topology.switches["switch2"].ports["swp1"]

    assert switch1_trunk.expected_allowed_vlans == (10, 20)
    assert switch1_trunk.peer_switch == "switch2"
    assert switch2_trunk.expected_allowed_vlans == (10, 20)
    assert switch2_trunk.peer_switch == "switch1"


def test_expands_available_ssh_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWITCH1_HOST", "192.0.2.10")
    monkeypatch.setenv("SWITCH1_USER", "cumulus")

    topology = load_topology(TOPOLOGY_PATH)

    assert topology.switches["switch1"].ssh.host == "192.0.2.10"
    assert topology.switches["switch1"].ssh.username == "cumulus"


def test_rejects_unknown_host_port(tmp_path: Path) -> None:
    original = TOPOLOGY_PATH.read_text(encoding="utf-8")
    invalid = original.replace("port: swp1", "port: swp99", 1)

    invalid_path = tmp_path / "invalid-topology.yaml"
    invalid_path.write_text(invalid, encoding="utf-8")

    with pytest.raises(TopologyConfigError, match="unknown port"):
        load_topology(invalid_path)

def test_hosts_have_test_network_addresses() -> None:
    topology = load_topology(TOPOLOGY_PATH)

    assert topology.hosts["host_a"].ip_address == "10.0.10.11"
    assert topology.hosts["host_b"].ip_address == "10.0.10.12"
