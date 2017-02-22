import os
import time
import json
import signal
import subprocess
from threading import Thread, Event

from tornado.tcpserver import TCPServer

import config
from logutils import setup_logger

logger = setup_logger()


# Ingoing message types
MESSAGE_TYPE_JOIN = "JOIN"  # props: crypto_params
MESSAGE_TYPE_SEARCH = "SEARCH"
MESSAGE_TYPE_CHAT = "CHAT"  # props: message

# Outgoing message types
MESSAGE_TYPE_PARTNER_FOUND = "PARTNER_FOUND"
MESSAGE_TYPE_PARTNER_DISCONNECTED = "PARTNER_DISCONNECTED"

# Client states
STATE_INITIAL = "STATE_INITIAL"
STATE_JOINED = "STATE_JOINED"
STATE_SEARCHING = "STATE_SEARCHING"
STATE_PARTNER_CONNECTED = "STATE_PARTNER_CONNECTED"
STATE_PARTNER_DISCONNECTED = "STATE_PARTNER_DISCONNECTED"


class Connection(object):
    """Client connection handler (one per TCP client)"""
    address = None
    state = STATE_INITIAL
    crypto_params = {}
    partner = None

    def __init__(self, stream, address, server):
        """Initialize base params and call stream reader for next line"""
        logger.info("connection - address: %s", address)
        self.state = STATE_INITIAL
        self.crypto_params = {}
        self.partner = None

        self.stream = stream
        self.address = address
        self.server = server
        self.stream.set_close_callback(self._on_disconnect)
        self.wait()

    def _on_read(self, line):
        """Called when new line received from connection"""
        # Some game logic (or magic)
        line = line.strip()
        logger.info("RCV> %s", line)
        if not line:
            self.stream.close()
            return

        try:
            message = json.loads(line)
            self.message_received(message)
        except:
            logger.error("Could not decode JSON: %s", line)

        # Wait for further input on this connection
        self.wait()

    def wait(self):
        """Read from stream until the next signed end of line"""
        self.stream.read_until("\n", self._on_read)

    def _on_disconnect(self, *args, **kwargs):
        """Called on client disconnected"""
        logger.info('Client disconnected %r', self.address)
        self.server.client_disconnected(self)
        # self.unregister()

    def __str__(self):
        """Build string representation, will be used for working with
        server identity (not only name) in future"""
        return "Connection(%s, state=%s)" % (str(self.address), self.state)

    def send_message(self, message_type, payload={}):
        """ `payload` must be a dict """
        assert isinstance(payload, dict)
        _msg = payload.copy()
        _msg["type"] = message_type
        self.stream.write("%s\n" % json.dumps(_msg))

    def message_received(self, msg):
        """ msg is a dictionary """
        logger.info("message_received: %s", msg)

        if "type" not in msg:
            logger.warn("- message does not have a 'type' property")
            return
        logger.info("type: %s", msg["type"])

        if msg["type"] == MESSAGE_TYPE_JOIN:
            logger.info("client joined %r",self.address)
            if not self.state == STATE_INITIAL:
                logger.error("already joined")
                return
            # joining includes the crypto params
            if not "crypto_params" in msg:
                logger.error("- JOIN message does not have a 'crypto_params' property")
                return

            #check for neccessary crypty params
            if not "identityString" in msg["crypto_params"]:
                logger.error("- JOIN message does not have a 'identityString' property")
                return
            if not "publicKey" in msg["crypto_params"]:
                logger.error("- JOIN message does not have a 'publicKey' property")
                return
            if not "preKeyList" in msg["crypto_params"]:
                logger.error("- JOIN message does not have a 'preKeyList' property")
                return
            if not "signedPreKeyList" in msg["crypto_params"]:
                logger.error("- JOIN message does not have a 'signedPreKeyList' property")
                return

            logger.info("client joined",self.address)
            self.crypto_params = msg["crypto_params"]
            self.state = STATE_JOINED
            return

        if msg["type"] == MESSAGE_TYPE_SEARCH:
            if not self.state == STATE_JOINED:
                logger.error("Client not joined %s", self.address)
                return
                
            self.state = STATE_SEARCHING
            self.server.search_for_partners(self)
            return

        if msg["type"] == MESSAGE_TYPE_CHAT and self.state == STATE_PARTNER_CONNECTED:
            # send message to partner
            self.partner.send_message(MESSAGE_TYPE_CHAT, msg)

    def partner_found(self, partner):
        """
        Called by server when partner is found. `partner` is a
        Connection object.
        """
        self.state = STATE_PARTNER_CONNECTED
        self.partner = partner
        self.send_message(MESSAGE_TYPE_PARTNER_FOUND, { "crypto_params": partner.crypto_params })

    def partner_disconnected(self):
        logger.info("partner has disconnected...")
        self.state = STATE_PARTNER_DISCONNECTED
        self.send_message(MESSAGE_TYPE_PARTNER_DISCONNECTED)

class Server(TCPServer):
    """TCP server for handling incoming connections from clients"""
    clients = {}

    def handle_stream(self, stream, address):
        """Called when new IOStream object is ready for usage"""
        logger.info('Incoming connection from %r', address)
        client = Connection(stream, address, server=self)
        self.clients[address] = (client)

    def client_disconnected(self, client):
        if client.state == STATE_PARTNER_CONNECTED:
            # let this clients other partner know about the disconnect
            client.partner.partner_disconnected()

        del self.clients[client.address]
        logger.info("clients after disconnect: %s", self.clients)

    def send_to_clients(self, message):
        message = message + "\n"
        for addr in self.clients:
            self.clients[addr].stream.write(message)

    def search_for_partners(self, client):
        """ `client` is the address of the client initiating this search """
        logger.info("search_for_partners: initiated by %s. %s clients connected", client.address, len(self.clients))

        for address in self.clients:
            logger.info("looking at address %s with state %s", address, self.clients[address].state)
            # Skip the initiating client
            if self.clients[address].address == client.address:
                continue

            if self.clients[address].state == STATE_SEARCHING:
                logger.info("- found a partner: %s", address)
                self.clients[address].partner_found(client)
                client.partner_found(self.clients[address])
                return
