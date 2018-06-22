import pytest
import gevent

from raiden.transfer.events import EventTransferReceivedSuccess
from raiden.utils.echo_node import EchoNode
from raiden.api.python import RaidenAPI
from raiden.tests.utils.network import CHAIN
from raiden.tests.utils.events import (
    must_contain_entry,
    get_channel_events_for_token,
)


# pylint: disable=too-many-locals


# `RaidenAPI.get_channel_events` is not supported in tester
@pytest.mark.parametrize('number_of_nodes', [4])
@pytest.mark.parametrize('number_of_tokens', [1])
@pytest.mark.parametrize('channels_per_node', [CHAIN])
@pytest.mark.parametrize('reveal_timeout', [18])
@pytest.mark.parametrize('settle_timeout', [64])
def test_event_transfer_received_success(token_addresses, raiden_chain):
    app0, app1, app2, receiver_app = raiden_chain
    token_address = token_addresses[0]

    expected = dict()

    for num, app in enumerate([app0, app1, app2]):
        amount = 1 + num
        transfer_event = RaidenAPI(app.raiden).transfer_async(
            app.raiden.default_registry.address,
            token_address,
            amount,
            receiver_app.raiden.address,
        )
        transfer_event.wait(timeout=20)
        expected[app.raiden.address] = amount

    # sleep is for the receiver's node to have time to process all events
    gevent.sleep(1)
    events = receiver_app.raiden.wal.storage.get_events_by_block(0, 'latest')
    events = [e[1] for e in events]

    assert must_contain_entry(
        events,
        EventTransferReceivedSuccess,
        {'amount': 1, 'initiator': app0.raiden.address},
    )
    assert must_contain_entry(
        events,
        EventTransferReceivedSuccess,
        {'amount': 2, 'initiator': app1.raiden.address},
    )
    assert must_contain_entry(
        events,
        EventTransferReceivedSuccess,
        {'amount': 3, 'initiator': app2.raiden.address},
    )


# `RaidenAPI.get_channel_events` is not supported in tester
@pytest.mark.skip()
@pytest.mark.parametrize('number_of_nodes', [4])
@pytest.mark.parametrize('number_of_tokens', [1])
@pytest.mark.parametrize('channels_per_node', [CHAIN])
@pytest.mark.parametrize('reveal_timeout', [18])
@pytest.mark.parametrize('settle_timeout', [64])
def test_echo_node_response(token_addresses, raiden_chain):
    app0, app1, app2, echo_app = raiden_chain
    address_to_app = {app.raiden.address: app for app in raiden_chain}
    token_address = token_addresses[0]
    echo_api = RaidenAPI(echo_app.raiden)

    echo_node = EchoNode(echo_api, token_address)
    echo_node.ready.wait(timeout=30)
    assert echo_node.ready.is_set()

    expected = list()

    # Create some transfers
    for num, app in enumerate([app0, app1, app2]):
        amount = 1 + num
        transfer_event = RaidenAPI(app.raiden).transfer_async(
            app.raiden.default_registry.address,
            token_address,
            amount,
            echo_app.raiden.address,
            10 ** (num + 1),
        )
        transfer_event.wait(timeout=20)
        expected.append(amount)

    while echo_node.num_handled_transfers < len(expected):
        gevent.sleep(.5)

    # Check that all transfers were handled correctly
    for handled_transfer in echo_node.seen_transfers:
        app = address_to_app[handled_transfer['initiator']]
        events = get_channel_events_for_token(
            app.raiden.default_registry.address,
            app,
            token_address,
            0,
        )
        received = {}

        for event in events:
            if event['event'] == 'EventTransferReceivedSuccess':
                received[repr(event)] = event

        assert len(received) == 1
        transfer = list(received.values())[0]
        assert transfer['initiator'] == echo_app.raiden.address
        assert transfer['identifier'] == (
            handled_transfer['identifier'] + transfer['amount']
        )

    echo_node.stop()


# `RaidenAPI.get_channel_events` is not supported in tester
@pytest.mark.skip()
@pytest.mark.parametrize('number_of_nodes', [8])
@pytest.mark.parametrize('number_of_tokens', [1])
@pytest.mark.parametrize('channels_per_node', [CHAIN])
@pytest.mark.parametrize('reveal_timeout', [20])
@pytest.mark.parametrize('settle_timeout', [120])
def test_echo_node_lottery(token_addresses, raiden_chain):
    app0, app1, app2, app3, echo_app, app4, app5, app6 = raiden_chain
    address_to_app = {app.raiden.address: app for app in raiden_chain}
    token_address = token_addresses[0]
    echo_api = RaidenAPI(echo_app.raiden)

    echo_node = EchoNode(echo_api, token_address)
    echo_node.ready.wait(timeout=30)
    assert echo_node.ready.is_set()

    expected = list()

    # Let 6 participants enter the pool
    amount = 7
    for num, app in enumerate([app0, app1, app2, app3, app4, app5]):
        transfer_event = RaidenAPI(app.raiden).transfer_async(
            app.raiden.default_registry.address,
            token_address,
            amount,
            echo_app.raiden.address,
            10 ** (num + 1),
        )
        transfer_event.wait(timeout=20)
        expected.append(amount)

    # test duplicated identifier + amount is ignored
    transfer_event = RaidenAPI(app5.raiden).transfer_async(
        app.raiden.default_registry.address,
        token_address,
        amount,  # same amount as before
        echo_app.raiden.address,
        10 ** 6,  # app5 used this identifier before
    ).wait(timeout=20)

    # test pool size querying
    pool_query_identifier = 77  # unused identifier different from previous one
    transfer_event = RaidenAPI(app5.raiden).transfer_async(
        app.raiden.default_registry.address,
        token_address,
        amount,
        echo_app.raiden.address,
        pool_query_identifier,
    ).wait(timeout=20)
    expected.append(amount)

    # fill the pool
    transfer_event = RaidenAPI(app6.raiden).transfer_async(
        app.raiden.default_registry.address,
        token_address,
        amount,
        echo_app.raiden.address,
        10 ** 7,
    ).wait(timeout=20)
    expected.append(amount)

    while echo_node.num_handled_transfers < len(expected):
        gevent.sleep(.5)

    received = {}
    # Check that payout was generated and pool_size_query answered
    for handled_transfer in echo_node.seen_transfers:
        app = address_to_app[handled_transfer['initiator']]
        events = get_channel_events_for_token(
            app.raiden.default_registry.address,
            app,
            token_address,
            0,
        )

        for event in events:
            if event['event'] == 'EventTransferReceivedSuccess':
                received[repr(event)] = event

    assert len(received) == 2

    received = sorted(received.values(), key=lambda transfer: transfer['amount'])

    pool_query = received[0]
    assert pool_query['amount'] == 6
    assert pool_query['identifier'] == pool_query_identifier + 6

    winning_transfer = received[1]
    assert winning_transfer['initiator'] == echo_app.raiden.address
    assert winning_transfer['amount'] == 49
    assert (winning_transfer['identifier'] - 49) % 10 == 0

    echo_node.stop()
