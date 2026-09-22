import pytest

from switch_qa.devices import Host


@pytest.mark.test_id("TC-07")
def test_host_a_reaches_host_b(
    host_a: Host,
    host_b: Host,
) -> None:
    result = host_a.ping(
        host_b.ip_address,
        count=4,
    )

    assert result.reachable
    assert result.transmitted == 4
    assert result.received == 4
    assert result.packet_loss_percent == 0.0


@pytest.mark.test_id("TC-08")
def test_packet_loss_remains_below_threshold(
    host_a: Host,
    host_b: Host,
) -> None:
    maximum_packet_loss = 1.0

    result = host_a.ping(
        host_b.ip_address,
        count=10,
    )

    assert result.transmitted == 10
    assert result.packet_loss_percent <= maximum_packet_loss
