"""
Subscribes to eventbus messages, and forwards them to SSE clients
"""

import asyncio
import json
import weakref
from time import time
from typing import Set

from aiohttp import hdrs, web
from aiohttp_sse import sse_response
from brewblox_service import brewblox_logger, events, features, repeater, strex
from pytimeparse import parse
from schema import Or, Schema

PUBLISH_TIMEOUT_S = 5
CLEANUP_INTERVAL_S = 10
PUBLISHED_KEYS = ['key', 'type', 'data']

_message_schema = Schema({
    'key': str,
    'type': str,
    'duration': lambda s: parse(s) is not None,
    'data': Or(dict, list),
})

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)
    features.add(app, EventRelay(app))


def get_relay(app: web.Application):
    return features.get(app, EventRelay)


def _cors_headers(request):
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods':
        request.headers.get('Access-Control-Request-Method', ','.join(hdrs.METH_ALL)),
        'Access-Control-Allow-Headers':
        request.headers.get('Access-Control-Request-Headers', '*'),
        'Access-Control-Allow-Credentials': 'true',
    }


def _pick(obj: dict) -> dict:
    return {k: obj[k] for k in PUBLISHED_KEYS}


class EventRelay(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._queues: Set[asyncio.Queue] = weakref.WeakSet()
        self._messages: dict = {}

    def __str__(self):
        return f'<{type(self).__name__} ({len(self._queues)} listeners)>'

    async def prepare(self):
        events.get_listener(self.app).subscribe(
            exchange_name=self.app['config']['state_exchange'],
            routing='#',
            on_message=self._on_event_message)

    async def before_shutdown(self, _):
        for queue in self._queues:
            await queue.put(asyncio.CancelledError())

    async def run(self):
        await asyncio.sleep(CLEANUP_INTERVAL_S)
        self.cleanup()

    def cleanup(self):
        now = time()
        expired = [k for k, v in self._messages.items() if v['expires'] < now]
        for key in expired:
            del self._messages[key]

    async def add_queue(self, queue: asyncio.Queue):
        self._queues.add(queue)
        try:
            self.cleanup()
            LOGGER.info(f'Added queue, setting messages: {self._messages.keys()}')
            for message in self._messages.values():
                await queue.put(_pick(message))

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:  # pragma: no cover
            LOGGER.info(f'Initial subscription push failed: {strex(ex)}')
            raise ex

    async def _on_event_message(self,
                                subscription: events.EventSubscription,
                                routing: str,
                                content: dict):

        message = _message_schema.validate(content)

        duration = parse(message['duration'])
        message['expires'] = time() + duration

        key = message['key']
        self._messages[key] = message

        coros = [q.put(_pick(message)) for q in self._queues]
        await asyncio.wait_for(asyncio.gather(*coros, return_exceptions=True), PUBLISH_TIMEOUT_S)


@routes.get('/sse')
async def subscribe(request: web.Request) -> web.Response:
    """
    ---
    summary: Push all events as they are received
    tags:
    - SSE
    operationId: sse.subscribe
    produces:
    - application/json
    """
    async with sse_response(request, headers=_cors_headers(request)) as resp:
        relay: EventRelay = get_relay(request.app)
        queue = asyncio.Queue()
        await relay.add_queue(queue)

        while True:
            data = await queue.get()
            if isinstance(data, (Exception, asyncio.CancelledError)):
                raise data
            await resp.send(json.dumps(data))

    # Note: we don't ever expect to return the response
    # Either the client cancels the request, or an exception is raised by publisher
