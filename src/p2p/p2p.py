
from __future__ import annotations
from ipaddress import ip_address
import ssl
import logging
import sys
import socket as socket_lib
import struct
import select
from enum import Enum
from dataclasses import dataclass
from typing import Self, Union
from socket import socket as Socket

import cryptography
import cryptography.exceptions
from pydantic import BaseModel, ValidationError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature

from p2p.constants import ENCODING, KEY_SIZE, NODE_BACKLOG, NODE_CHECK_TIME, NODE_CHUNK_SIZE, NODE_CONNECTION_TIMEOUT, SEPARATOR

logger = logging.getLogger(__name__)

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)

logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class P2PRuntimeError(BaseException):
    __slots__ = ()


class RawMessage(BaseModel):
    data: bytes
    signature: bytes

    def to_bytes(self) -> bytes:
        return self.signature + self.data

    @staticmethod
    def from_bytes(data: bytes) -> RawMessage:
        return RawMessage(
            signature=data[:KEY_SIZE],
            data=data[KEY_SIZE:]
        )
    
    def check_signature(self, public_key: rsa.RSAPublicKey) -> bool:
        return verify(self.signature, self.data, public_key)


class MessageType(Enum):
    PEERS_REQUEST = 0
    PEERS_SHARING = 1
    APPLICATION = 2


class Message(BaseModel):
    message_type: MessageType
    content: Union[PeersRequest, PeersSharing, ApplicationData]

    def _to_bytes(self) -> bytes:
        return self.model_dump_json().encode(ENCODING)
    
    def to_raw(self, private_key: rsa.RSAPrivateKey) -> RawMessage:
        data = self._to_bytes()

        return RawMessage(
            data=data,
            signature=sign(data, private_key)
        )

    @staticmethod
    def _from_bytes(data: bytes) -> Message:
        try:
            return Message.model_validate_json(data.decode(ENCODING))
        
        except (UnicodeDecodeError, ValidationError):
            message = "cannot create Message from bytes"
            logger.exception(message)
            raise P2PRuntimeError(message)

    @staticmethod
    def from_raw(raw: RawMessage) -> Message:
        return Message._from_bytes(raw.data)

    def check_content(self) -> bool:
        if self.message_type == MessageType.PEERS_REQUEST and isinstance(self.content, PeersRequest): return True
        if self.message_type == MessageType.PEERS_SHARING and isinstance(self.content, PeersSharing): return True
        if self.message_type == MessageType.APPLICATION and isinstance(self.content, ApplicationData): return True
        return False
        
    @staticmethod
    def peers_request() -> Message:
        return Message(message_type=MessageType.PEERS_REQUEST, content=PeersRequest())
    
    @staticmethod
    def peers_sharing(peers: list[Peer]) -> Message:
        return Message(
            message_type=MessageType.PEERS_SHARING,
            content=PeersSharing(peers=[peer.to_serialized() for peer in peers if peer.can_be_shared()])
        )

    @staticmethod
    def application_data(data: str) -> Message:
        return Message(message_type=MessageType.APPLICATION, content=ApplicationData(data=data))


class MessageContent(BaseModel):
    ...

class PeersRequest(MessageContent):
    ...
    
class PeersSharing(MessageContent):
    peers: list[SerializedPeer]

class ApplicationData(MessageContent):
    data: str


class SerializedPeer(BaseModel):
    ip_address: str
    port: int
    public_key: bytes

    def to_peer(self) -> Peer:
        return Peer(
            ip_address=self.ip_address,
            port=self.port,
            public_key=deserialize_public_key(self.public_key),
        )

class Peer(BaseModel):
    ip_address: str
    port: int|None
    public_key: rsa.RSAPublicKey|None

    def can_be_shared(self) -> bool:
        return self.public_key is not None and self.port is not None

    def to_serialized(self) -> SerializedPeer:
        assert self.port is not None
        assert self.public_key is not None
        return SerializedPeer(
            ip_address=self.ip_address,
            port=self.port,
            public_key=serialize_public_key(self.public_key)
        )


def deserialize_public_key(data: bytes) -> rsa.RSAPublicKey:
    try:
        key = serialization.load_pem_public_key(data)

    except (ValueError, TypeError, cryptography.exceptions.UnsupportedAlgorithm) as e:
        message = f"unable to load key from bytes: {e}"
        logger.exception(message)
        raise P2PRuntimeError(message)

    if not isinstance(key, rsa.RSAPublicKey):
        message = f"invalid key, not a public RSA key: '{key}'"
        logger.error(message)
        raise P2PRuntimeError(message)
    
    return key

def serialize_public_key(key: rsa.RSAPublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


# the following is taken from https://elc.github.io/python-security/chapters/07_Asymmetric_Encryption.html#rsa-encryption

def generate_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE,
    )

    public_key = private_key.public_key()
    return private_key, public_key

def sign(message: bytes, private_key: rsa.RSAPrivateKey):
    return private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

def verify(signature: bytes, message: bytes, public_key: rsa.RSAPublicKey):
    try:
        public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        return False


@dataclass
class PeerLink:
    peer: Peer
    socket: Socket
    alive: bool
    buffer: bytes

    def fmt_addr(self) -> str:
        return f"{self.peer.ip_address}:{self.peer.port}"


@dataclass
class NodeContextManager:
    node: Node

    def __enter__(self) -> Node:
        return self.node

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.node.stop()

@dataclass
class Node:
    ip_address: str
    port: int
    serialized_port: bytes
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    serialized_public_key: bytes
    peer_links: list[PeerLink]
    server_socket: Socket

    @staticmethod
    def start(ip_address: str, port: int) -> Node:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile="node.crt", keyfile="node.key")
        server_socket = Socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM)
        server_socket.bind((ip_address, port))
        server_socket.listen(NODE_BACKLOG)
        secure_server_socket = context.wrap_socket(server_socket, server_side=True)
        private_key, public_key = generate_key_pair()
        computed_ip_address, computed_port = server_socket.getsockname()
        assert isinstance(computed_ip_address, str)
        assert isinstance(computed_port, int)
        logger.info(f"started node on {computed_ip_address}:{computed_port}")
        return Node(
            ip_address=computed_ip_address, port=computed_port,
            serialized_port=str(computed_port).encode(ENCODING),
            private_key=private_key, public_key=public_key,
            serialized_public_key=serialize_public_key(public_key),
            peer_links=[], server_socket=secure_server_socket
        )

    def stop(self):
        for link in self.peer_links:
            if link.alive:
                link.socket.close()

        self.server_socket.close()
        logger.info("closed server socket")

    def update(self):
        sockets: list[Socket] = [self.server_socket] + [peer_link.socket for peer_link in self.peer_links]
        readable: list[Socket]
        readable, _, _ = select.select(
            sockets, [], [], NODE_CHECK_TIME
        )

        if self.server_socket in readable:
            socket, addr = self.server_socket.accept()
            self._handle_new_connection(socket, addr)

        for link in self.peer_links:
            if link.socket in readable:
                try:
                    self._recv(link)

                except P2PRuntimeError as e:
                    logger.exception(f"{link.fmt_addr()} error while receiving: {e}")

                if not link.alive:
                    logger.info(f"{link.fmt_addr()} closed connection")

        self.peer_links = [link for link in self.peer_links if link.alive]

    def has_peer(self, peer: Peer) -> bool:
        return any(
            link.peer.public_key == peer.public_key
            for link in self.peer_links
        )

    def _connect_to_peer(self, ip_address: str, port: int) -> Socket|None:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        socket = Socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM)
        socket.bind((self.ip_address, 0))
        socket.settimeout(NODE_CONNECTION_TIMEOUT)
        secure_socket = context.wrap_socket(socket, server_hostname=ip_address)

        try:
            secure_socket.connect((ip_address, port))

        except (socket_lib.error, socket_lib.herror, socket_lib.gaierror, socket_lib.timeout) as e:
            logger.exception(f"error while trying to connect to {ip_address}:{port} ({e})")
            return None
        
        return secure_socket

    def _declare_to_peer(self, link: PeerLink):
        self._send(link, self.serialized_public_key)
        self._send(link, self.serialized_port)

    def _handle_new_connection(self, socket: Socket, addr: socket_lib._RetAddress):
        if socket.family != socket_lib.AF_INET:
            logger.info(f"{addr} ignoring non INET socket: {socket.family}")
            return
        
        ip_addr, port = addr
        assert isinstance(ip_addr, str)
        assert isinstance(port, int)
        link = PeerLink(
            peer=Peer(ip_address=ip_addr, port=port, public_key=None),
            socket=socket, alive=True, buffer=b""
        )
        self.peer_links.append(link)
        logger.info(f"{link.fmt_addr()} established connection")

    def _handle_public_key_declaration(self, link: PeerLink) -> bool:
        if link.peer.public_key is None:
            try:
                key = deserialize_public_key(link.buffer)

            except P2PRuntimeError as e:
                logger.exception(f"{link.fmt_addr()} unable to parse public key ({e})")
                return True
            
            link.peer.public_key = key
            logger.info(f"{link.fmt_addr()} public key set")
            return True
        
        return False

    def _handle_port_declaration(self, link: PeerLink) -> bool:
        if link.peer.port is None:
            try:
                port = int(link.buffer.decode(ENCODING))

            except (ValueError, UnicodeDecodeError) as e:
                logger.exception(f"{link.fmt_addr()} unable to parse port ({e})")
                return True

            link.peer.port = port
            logger.info(f"{link.fmt_addr()} port set")
            return True
        
        return False

    def _handle_peers_request(self, link: PeerLink):
        self._send_message(
            link,
            Message.peers_sharing(
                [link.peer for link in self.peer_links if link.peer.can_be_shared()]
            )
        )

    def _handle_peer_sharing(self, link: PeerLink, content: PeersSharing):
        for serialized_peer in content.peers:
            peer = serialized_peer.to_peer()
            assert peer.public_key is not None
            assert peer.port is not None
            if self.has_peer(peer): continue
            socket = self._connect_to_peer(peer.ip_address, peer.port)

            if socket is not None:
                link = PeerLink(
                    peer=peer,
                    socket=socket, alive=True, buffer=b""
                )
                self.peer_links.append(link)
                self._declare_to_peer(link)

    def _handle_ready_to_recv(self, link: PeerLink):
        if self._handle_public_key_declaration(link): return
        assert link.peer.public_key is not None
        if self._handle_port_declaration(link): return
        assert link.peer.port is not None

        message = RawMessage.from_bytes(link.buffer)

        if not message.check_signature(link.peer.public_key):
            logger.error(f"{link.fmt_addr()} ignoring message because the signature doesn't match content")
            return
        
        message = Message.from_raw(message)

        if not message.check_content():
            logger.error(f"{link.fmt_addr()} ignoring message because the content doesn't match the type indicator")
            return
        
        logger.info(f"{link.fmt_addr()} received {message.message_type}")
        self._handle_message(link, message)

    def _handle_message(self, link: PeerLink, message: Message):
        if message.message_type == MessageType.APPLICATION:
            self._handle_application_message(message)

        if message.message_type == MessageType.PEERS_REQUEST:
            self._handle_peers_request(link)

        if message.message_type == MessageType.PEERS_SHARING:
            assert isinstance(message.content, PeersSharing)
            self._handle_peer_sharing(link, message.content)
        
    def _handle_application_message(self, message: Message):
        ...

    def _send_message(self, link: PeerLink, message: Message):
        raw_message = message.to_raw(self.private_key)
        data = raw_message.to_bytes()
        logger.info(f"sending {message.message_type} to {link.fmt_addr()}")
        self._send(link, data)

    def _send_message_to_peers(self, message: Message):
        raw_message = message.to_raw(self.private_key)
        data = raw_message.to_bytes()
        logger.info(f"sending {message.message_type} to peers")
        self._send_to_peers(data)

    def _send_to_peers(self, data: bytes):
        for link in self.peer_links:
            self._send(link, data)

    def _send(self, link: PeerLink, data: bytes):
        if SEPARATOR in data:
            message = f"found separator {SEPARATOR} in data to send, which is not permitted"
            logger.error(message)
            raise P2PRuntimeError(message)
        
        link.socket.sendall(data + SEPARATOR)

    def _recv(self, link: PeerLink):
        chunk = link.socket.recv(NODE_CHUNK_SIZE)

        if not chunk:
            link.alive = False
            link.socket.close()
            return
        
        link.buffer += chunk

        if SEPARATOR in chunk:
            link.buffer, rest = link.buffer.split(SEPARATOR, 1)
            self._handle_ready_to_recv(link)
            link.buffer = rest
