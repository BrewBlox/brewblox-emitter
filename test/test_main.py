"""
Tests brewblox_emitter.__main__.py
"""

from brewblox_service import events

from brewblox_emitter import __main__ as main
from brewblox_emitter import relay

TESTED = main.__name__


def test_main(mocker, app):
    mocker.patch(TESTED + '.service.run')
    mocker.patch(TESTED + '.service.create_app').return_value = app

    main.main()

    assert None not in [
        events.get_listener(app),
        relay.get_relay(app),
    ]
