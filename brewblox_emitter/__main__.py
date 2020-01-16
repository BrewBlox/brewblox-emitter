"""
Example of how to import and use the brewblox service
"""

from argparse import ArgumentParser

from brewblox_service import (brewblox_logger, events, http_client, scheduler,
                              service)

from brewblox_emitter import events_example, http_example, poll_example

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='emitter') -> ArgumentParser:
    parser: ArgumentParser = service.create_parser(default_name=default_name)

    parser.add_argument('--broadcast-exchange',
                        help='Eventbus exchange to which device services broadcast their state. [%(default)s]',
                        default='brewcast_ui')

    return parser


def main():
    app = service.create_app(parser=create_parser())

    scheduler.setup(app)
    events.setup(app)
    http_client.setup(app)

    events_example.setup(app)
    poll_example.setup(app)
    http_example.setup(app)

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
