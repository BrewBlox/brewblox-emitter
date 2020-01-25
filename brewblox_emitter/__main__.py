"""
Example of how to import and use the brewblox service
"""

from argparse import ArgumentParser

from brewblox_service import brewblox_logger, events, scheduler, service

from brewblox_emitter import relay

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='emitter') -> ArgumentParser:
    parser: ArgumentParser = service.create_parser(default_name=default_name)

    parser.add_argument('--state-exchange',
                        help='Eventbus exchange to which device services broadcast their state. [%(default)s]',
                        default='brewcast.state')

    return parser


def main():
    app = service.create_app(parser=create_parser())

    scheduler.setup(app)
    events.setup(app)
    relay.setup(app)

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
