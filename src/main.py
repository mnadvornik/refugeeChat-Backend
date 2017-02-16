#!/usr/bin/env python2
import os
import sys
import time
import signal
import json

# from tornado.options import options, parse_command_line, define
from tornado.ioloop import IOLoop

from server import Server
from logutils import setup_logger
import config


logger = setup_logger()


def handle_signal(sig, frame):
    logger.warning('Caught signal: %s', sig)
    IOLoop.instance().add_callback(shutdown)


def shutdown(delay=2):
    """First stop server and add callback to stop i/o loop"""
    logger.info("Shutdown initiated...")
    io_loop = IOLoop.instance()
    io_loop.stop()
    logger.info("bye")


def main():
    logger.info("Starting")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    io_loop = IOLoop.instance()

    # Create the TCP server
    io_loop.server = Server()
    logger.info('Starting TCP server on port %d', config.TCP_PORT)
    io_loop.server.listen(config.TCP_PORT)

    # main thread blocks here
    io_loop.start()


if __name__ == '__main__':
    main()
