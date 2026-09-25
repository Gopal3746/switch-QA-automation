from collections.abc import Generator, Iterator
from pathlib import Path

import pytest

from switch_qa.config import TopologyConfig, load_topology
from switch_qa.devices import Host, Switch
from switch_qa.diagnostics import EvidenceCollector
from switch_qa.reporter import RunReporter
from switch_qa.simulated_transport import SimulatedTransport
from switch_qa.simulation import SimulatedTopologyState

REPORTER_KEY = pytest.StashKey[RunReporter]()

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

def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("switch-qa")

    group.addoption(
        "--evidence-dir",
        default="reports/evidence",
        help="Directory for failed-test diagnostic evidence",
    )
    group.addoption(
        "--report-dir",
        default="reports",
        help="Directory for QA summary reports",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.stash[REPORTER_KEY] = RunReporter(
        matrix_path="configs/test_matrix.yaml",
        output_directory=config.getoption("--report-dir"),
        scenario="simulated",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[object],
) -> Generator[None, object, None]:
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    test_id_marker = item.get_closest_marker("test_id")

    if test_id_marker and test_id_marker.args:
        test_id = str(test_id_marker.args[0])
    else:
        test_id = item.nodeid

    evidence_path: Path | None = None

    if report.failed:
        switches: dict[str, Switch] = {}
        hosts: dict[str, Host] = {}

        for fixture_value in item.funcargs.values():
            if isinstance(fixture_value, Switch):
                switches[fixture_value.name] = fixture_value
            elif isinstance(fixture_value, Host):
                hosts[fixture_value.name] = fixture_value

        evidence_directory = Path(
            item.config.getoption("--evidence-dir")
        )
        collector = EvidenceCollector(evidence_directory)

        evidence_path = collector.collect(
            test_id,
            switches=switches,
            hosts=hosts,
            failure=str(report.longrepr),
        )

    reporter = item.config.stash[REPORTER_KEY]
    reporter.record(
        test_id=test_id,
        node_id=item.nodeid,
        outcome=report.outcome,
        duration_seconds=report.duration,
        failure=(
            str(report.longrepr)
            if report.failed
            else None
        ),
        evidence_path=(
            str(evidence_path)
            if evidence_path is not None
            else None
        ),
    )


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    del exitstatus

    reporter = session.config.stash.get(
        REPORTER_KEY,
        None,
    )

    if reporter is not None:
        reporter.write()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[object],
):
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    test_id_marker = item.get_closest_marker("test_id")

    if test_id_marker and test_id_marker.args:
        test_id = str(test_id_marker.args[0])
    else:
        test_id = item.nodeid

    switches: dict[str, Switch] = {}
    hosts: dict[str, Host] = {}

    for fixture_value in item.funcargs.values():
        if isinstance(fixture_value, Switch):
            switches[fixture_value.name] = fixture_value
        elif isinstance(fixture_value, Host):
            hosts[fixture_value.name] = fixture_value

    evidence_directory = Path(
        item.config.getoption("--evidence-dir")
    )
    collector = EvidenceCollector(evidence_directory)

    collector.collect(
        test_id,
        switches=switches,
        hosts=hosts,
        failure=str(report.longrepr),
    )
