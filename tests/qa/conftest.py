import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from switch_qa.backend import (
    TransportBackend,
    build_transport,
)
from switch_qa.config import (
    DEFAULT_TOPOLOGY_PATH,
    TopologyConfig,
    load_topology,
)
from switch_qa.devices import Host, Switch
from switch_qa.diagnostics import EvidenceCollector
from switch_qa.reporter import RunReporter
from switch_qa.simulation import SimulatedTopologyState

REPORTER_KEY = pytest.StashKey[RunReporter]()


def build_switch(
    switch_name: str,
    topology: TopologyConfig,
    backend: TransportBackend,
    state: SimulatedTopologyState | None,
    *,
    accept_unknown_host_keys: bool,
) -> Switch:
    switch_config = topology.switches[switch_name]
    password_variable = f"{switch_name.upper()}_PASSWORD"

    transport = build_transport(
        switch_name,
        topology,
        backend=backend,
        state=state,
        password=os.environ.get(password_variable),
        accept_unknown_host_keys=accept_unknown_host_keys,
    )

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


@pytest.fixture(scope="session")
def backend(
    pytestconfig: pytest.Config,
) -> TransportBackend:
    return TransportBackend(pytestconfig.getoption("--backend"))


@pytest.fixture(scope="session")
def accept_unknown_host_keys(
    pytestconfig: pytest.Config,
) -> bool:
    return bool(pytestconfig.getoption("--accept-unknown-host-keys"))


@pytest.fixture(scope="session")
def topology(
    pytestconfig: pytest.Config,
) -> TopologyConfig:
    return load_topology(pytestconfig.getoption("--topology"))


@pytest.fixture
def fixed_state(
    topology: TopologyConfig,
    backend: TransportBackend,
) -> SimulatedTopologyState | None:
    if backend is TransportBackend.SSH:
        return None

    return SimulatedTopologyState.from_config(topology)


@pytest.fixture
def buggy_state(
    topology: TopologyConfig,
    backend: TransportBackend,
) -> SimulatedTopologyState | None:
    if backend is TransportBackend.SSH:
        return None

    return SimulatedTopologyState.from_config(
        topology,
        scenario="buggy",
    )


@pytest.fixture
def switch1(
    topology: TopologyConfig,
    backend: TransportBackend,
    accept_unknown_host_keys: bool,
    fixed_state: SimulatedTopologyState | None,
) -> Iterator[Switch]:
    switch = build_switch(
        "switch1",
        topology,
        backend,
        fixed_state,
        accept_unknown_host_keys=accept_unknown_host_keys,
    )
    yield switch
    switch.disconnect()


@pytest.fixture
def switch2(
    topology: TopologyConfig,
    backend: TransportBackend,
    accept_unknown_host_keys: bool,
    fixed_state: SimulatedTopologyState | None,
) -> Iterator[Switch]:
    switch = build_switch(
        "switch2",
        topology,
        backend,
        fixed_state,
        accept_unknown_host_keys=accept_unknown_host_keys,
    )
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
    topology: TopologyConfig,
    backend: TransportBackend,
    accept_unknown_host_keys: bool,
    buggy_state: SimulatedTopologyState | None,
) -> Iterator[Switch]:
    switch = build_switch(
        "switch1",
        topology,
        backend,
        buggy_state,
        accept_unknown_host_keys=accept_unknown_host_keys,
    )
    yield switch
    switch.disconnect()


@pytest.fixture
def buggy_switch2(
    topology: TopologyConfig,
    backend: TransportBackend,
    accept_unknown_host_keys: bool,
    buggy_state: SimulatedTopologyState | None,
) -> Iterator[Switch]:
    switch = build_switch(
        "switch2",
        topology,
        backend,
        buggy_state,
        accept_unknown_host_keys=accept_unknown_host_keys,
    )
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
        "--backend",
        choices=[backend.value for backend in TransportBackend],
        default=TransportBackend.SIMULATED.value,
        help="Command backend: simulated or ssh",
    )
    group.addoption(
        "--topology",
        default=str(DEFAULT_TOPOLOGY_PATH),
        help="Path to the topology YAML configuration",
    )
    group.addoption(
        "--accept-unknown-host-keys",
        action="store_true",
        default=False,
        help="Allow SSH connections to unknown host keys",
    )
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
    config.addinivalue_line(
        "markers",
        "simulation_only: test modifies simulated topology state",
    )

    config.stash[REPORTER_KEY] = RunReporter(
        matrix_path="configs/test_matrix.yaml",
        output_directory=config.getoption("--report-dir"),
        scenario=config.getoption("--backend"),
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--backend") != "ssh":
        return

    live_skip = pytest.mark.skip(reason=("simulation-only test is disabled for live SSH switches"))

    for item in items:
        if item.get_closest_marker("simulation_only"):
            item.add_marker(live_skip)


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
) -> Iterator[None]:
    outcome = yield
    report = outcome.get_result()

    # Record normal test results during the call phase.
    # Setup failures and skips never reach the call phase.
    if report.when == "setup":
        if report.passed:
            return
    elif report.when != "call":
        return

    test_id_marker = item.get_closest_marker("test_id")

    # Only include the 13 requirement-linked QA cases.
    if not test_id_marker or not test_id_marker.args:
        return

    test_id = str(test_id_marker.args[0])
    failure = str(report.longrepr) if report.failed else None
    evidence_path: str | None = None

    if report.failed:
        switches: dict[str, Switch] = {}
        hosts: dict[str, Host] = {}

        for fixture_value in item.funcargs.values():
            if isinstance(fixture_value, Switch):
                switches[fixture_value.name] = fixture_value
            elif isinstance(fixture_value, Host):
                hosts[fixture_value.name] = fixture_value

        evidence_directory = Path(item.config.getoption("--evidence-dir"))
        collector = EvidenceCollector(evidence_directory)

        collected_path = collector.collect(
            test_id,
            switches=switches,
            hosts=hosts,
            failure=failure or "Test failed without details.",
        )
        evidence_path = str(collected_path)

    reporter = item.config.stash.get(
        REPORTER_KEY,
        None,
    )

    if reporter is not None:
        reporter.record(
            test_id=test_id,
            node_id=item.nodeid,
            outcome=report.outcome,
            duration_seconds=report.duration,
            failure=failure,
            evidence_path=evidence_path,
        )
