import json

import pytest

from switch_qa.config import load_topology
from switch_qa.simulated_transport import SimulatedTransport
from switch_qa.simulation import SimulatedTopologyState
from switch_qa.transport import (
    CommandExecutionError,
    CommandTransport,
    TransportNotConnectedError,
)


@pytest.fixture
def state() -> SimulatedTopologyState:
    return SimulatedTopologyState.from_config(load_topology())


@pytest.fixture
def transport(
    state: SimulatedTopologyState,
) -> SimulatedTransport:
    simulated = SimulatedTransport("switch1", state)
    simulated.connect()
    return simulated


def test_implements_command_transport_protocol(
    state: SimulatedTopologyState,
) -> None:
    simulated = SimulatedTransport("switch1", state)

    assert isinstance(simulated, CommandTransport)

    with pytest.raises(
        TransportNotConnectedError,
        match="call connect",
    ):
        simulated.run_command("bridge vlan show")


def test_nv_show_interface_returns_json_state(
    transport: SimulatedTransport,
) -> None:
    result = transport.run_command(
        "nv show interface swp1 -o json"
    )
    output = json.loads(result.stdout)

    assert result.succeeded
    assert output["swp1"]["type"] == "access"
    assert output["swp1"]["link"]["state"] == {
        "admin": "up",
        "oper": "up",
    }
    assert output["swp1"]["bridge"]["domain"]["br_default"] == {
        "untagged": 10,
        "vlan": [10],
    }


def test_bridge_vlan_show_renders_access_and_trunk_vlans(
    transport: SimulatedTransport,
) -> None:
    result = transport.run_command("bridge vlan show")

    assert "swp1              10 PVID Egress Untagged" in result.stdout
    assert "swp2              10" in result.stdout
    assert "swp2              20" in result.stdout


def test_nvue_commands_correct_injected_defects() -> None:
    state = SimulatedTopologyState.from_config(
        load_topology(),
        scenario="buggy",
    )
    switch1 = SimulatedTransport("switch1", state)
    switch2 = SimulatedTransport("switch2", state)
    switch1.connect()
    switch2.connect()

    assert not state.can_hosts_reach("host_a", "host_b")

    access_result = switch1.run_command(
        (
            "nv set interface swp1 bridge domain "
            "br_default access 10"
        ),
        check=True,
    )
    trunk_result = switch2.run_command(
        (
            "nv set interface swp1 bridge domain "
            "br_default vlan 10"
        ),
        check=True,
    )

    switch1.run_command("nv config apply", check=True)
    switch2.run_command("nv config apply", check=True)

    assert access_result.succeeded
    assert trunk_result.succeeded
    assert state.can_hosts_reach("host_a", "host_b")


def test_link_state_command_changes_operational_state(
    transport: SimulatedTransport,
    state: SimulatedTopologyState,
) -> None:
    transport.run_command(
        "nv set interface swp2 link state down",
        check=True,
    )

    result = transport.run_command(
        "ip link show dev swp2",
        check=True,
    )

    assert state.port("switch1", "swp2").admin_state == "down"
    assert "state DOWN" in result.stdout


def test_saved_configuration_survives_simulated_reload(
    transport: SimulatedTransport,
    state: SimulatedTopologyState,
) -> None:
    transport.run_command(
        (
            "nv set interface swp1 bridge domain "
            "br_default access 20"
        ),
        check=True,
    )
    transport.run_command("nv config save", check=True)

    transport.run_command(
        (
            "nv set interface swp1 bridge domain "
            "br_default access 10"
        ),
        check=True,
    )
    assert state.port("switch1", "swp1").pvid == 10

    transport.run_command("__simulate_reload__", check=True)

    assert state.port("switch1", "swp1").pvid == 20


def test_ping_reflects_topology_reachability() -> None:
    fixed_state = SimulatedTopologyState.from_config(load_topology())
    fixed_transport = SimulatedTransport("switch1", fixed_state)
    fixed_transport.connect()

    passing = fixed_transport.run_command(
        "ping -c 4 10.0.10.12"
    )

    buggy_state = SimulatedTopologyState.from_config(
        load_topology(),
        scenario="buggy",
    )
    buggy_transport = SimulatedTransport("switch1", buggy_state)
    buggy_transport.connect()

    failing = buggy_transport.run_command(
        "ping -c 4 10.0.10.12"
    )

    assert passing.exit_code == 0
    assert "0% packet loss" in passing.stdout
    assert failing.exit_code == 1
    assert "100% packet loss" in failing.stdout


def test_unsupported_checked_command_raises(
    transport: SimulatedTransport,
) -> None:
    unchecked = transport.run_command("show something invalid")

    assert unchecked.exit_code == 127
    assert "unsupported simulated command" in unchecked.stderr

    with pytest.raises(
        CommandExecutionError,
        match="status 127",
    ):
        transport.run_command(
            "show something invalid",
            check=True,
        )
