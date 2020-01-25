"""
Tests brewblox_emitter.relay
"""

import asyncio
import json

import pytest
from aiohttp.client_exceptions import ClientPayloadError
from brewblox_service import scheduler

from brewblox_emitter import relay

TESTED = relay.__name__


@pytest.fixture
def listener_mock(mocker):
    call_mock = mocker.patch(TESTED + '.events.get_listener')
    return call_mock.return_value


@pytest.fixture
async def app(app, mocker, listener_mock):
    mocker.patch(TESTED + '.CLEANUP_INTERVAL_S', 0.0001)

    scheduler.setup(app)
    relay.setup(app)
    return app


async def test_add_queue(app, client):
    rl = relay.get_relay(app)

    await rl._on_event_message(None, 'test', {
        'key': 'testkey',
        'duration': '10s',
        'data': {'stuff': True},
        'type': 'TestFace',
    })
    q1 = asyncio.Queue()
    q2 = asyncio.Queue()

    await rl.add_queue(q1)
    await rl.add_queue(q2)
    expected = {
        'key': 'testkey',
        'type': 'TestFace',
        'data': {'stuff': True},
    }
    assert q1.get_nowait() == expected
    assert q2.get_nowait() == expected


async def test_expire(app, client):
    rl = relay.get_relay(app)
    await rl._on_event_message(None, 'test', {
        'key': 'testkey',
        'duration': '0s',
        'data': {'stuff': True},
        'type': 'TestFace',
    })

    await asyncio.sleep(0.01)
    q1 = asyncio.Queue()
    await rl.add_queue(q1)

    with pytest.raises(asyncio.QueueEmpty):
        q1.get_nowait()


async def test_subscribe(app, client):
    rl = relay.get_relay(app)

    await rl._on_event_message(None, 'test', {
        'key': 'testkey',
        'duration': '10s',
        'data': {'stuff': True},
        'type': 'TestFace',
    })
    strval = json.dumps({
        'key': 'testkey',
        'type': 'TestFace',
        'data': {'stuff': True},
    })

    async with client.get('/sse') as resp:
        chunk = await resp.content.read(6 + len(strval))
        assert chunk.decode() == 'data: ' + strval


async def test_close(app, client):
    with pytest.raises(ClientPayloadError):
        async with client.get('/sse') as resp:
            await relay.get_relay(app).before_shutdown(app)
            await resp.content.read(5)
            await resp.content.read(5)
