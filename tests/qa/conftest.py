from collections.abc import Iterator

import pytest

from switch_qa.config import TopologyConfig, load_topology
from switch_qa.devices import Host, Switch
from switch_qa.simulated_transport import SimulatedTransport
from switch_qa.simulation import SimulatedTopologyState


def build_switch(
    switch_name: str,
    state: SimulatedTopologyState,
) -> Switch:
    switch_config = state.config.switches[switch_name]
    transport = SimulatedTransport(switch_name, state)

    switch = Switch(
        name=switch_name,
        display_name=switch_config.display_name,
        transport=transport,
    )
    switch.connect()
    return switch


def build_host(
    host_name: str,
    topology: TopologyConfig,
    switch: Switch,
) -> Host:
    host_config = topology.hosts[host_name]

    return Host(
        name=host_name,
        display_name=host_config.display_name,
        ip_address=host_config.ip_address,
        transport=switch.transport,
    )


@pytest.fixture
def topology() -> TopologyConfig:
    return load_topology()


@pytest.fixture
def fixed_state(
    topology: TopologyConfig,
) -> SimulatedTopologyState:
    return SimulatedTopologyState.from_config(topology)


@pytest.fixture
def buggy_state(
    topology: TopologyConfig,
) -> SimulatedTopologyState:
    return SimulatedTopologyState.from_config(
        topology,
        scenario="buggy",
    )


@pytest.fixture
def switch1(
    fixed_state: SimulatedTopologyState,
) -> Iterator[Switch]:
    switch = build_switch("switch1", fixed_state)
    yield switch
    switch.disconnect()


@pytest.fixture
def switch2(
    fixed_state: SimulatedTopologyState,
) -> Iterator[Switch]:
    switch = build_switch("switch2", fixed_state)
    yield switch
    switch.disconnect()


@pytest.fixture
def host_a(
    topology: TopologyConfig,
    switch1: Switch,
) -> Host:
    return build_host("host_a", topology, switch1)


@pytest.fixture
def host_b(
    topology: TopologyConfig,
    switch2: Switch,
) -> Host:
    return build_host("host_b", topology, switch2)


@pytest.fixture
def buggy_switch1(
    buggy_state: SimulatedTopologyState,
) -> Iterator[Switch]:
    switch = build_switch("switch1", buggy_state)
    yield switch
    switch.disconnect()


@pytest.fixture
def buggy_switch2(
    buggy_state: SimulatedTopologyState,
) -> Iterator[Switch]:
    switch = build_switch("switch2", buggy_state)
    yield switch
    switch.disconnect()


@pytest.fixture
def buggy_host_a(
    topology: TopologyConfig,
    buggy_switch1: Switch,
) -> Host:
    return build_host(
        "host_a",
        topology,
        buggy_switch1,
    )
