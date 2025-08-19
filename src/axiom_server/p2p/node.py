"""Defining the base unit of P2P network, a Node."""

from __future__ import annotations

import logging
import select
import socket as socket_lib
import ssl
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from socket import socket as Socket
from typing import TYPE_CHECKING, Any, Callable, Literal, Union

if TYPE_CHECKING:
    from collections.abc import Iterable

import cryptography.exceptions
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from pydantic import BaseModel, ValidationError

from axiom_server.p2p.constants import (
    BOOTSTRAP_IP_ADDR,
    BOOTSTRAP_PORT,
    ENCODING,
    KEY_SIZE,
    NODE_BACKLOG,
    NODE_CERT_FILE,
    NODE_CHECK_TIME,
    NODE_CHUNK_SIZE,
    NODE_CONNECTION_TIMEOUT,
    NODE_KEY_FILE,
    SEPARATOR,
    SIGNATURE_SIZE,
)

logger = logging.getLogger("axiom_server.p2p.node")

if not logger.handlers:
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(
        logging.Formatter(
            "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
        ),
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
            signature=data[:SIGNATURE_SIZE], data=data[SIGNATURE_SIZE:],
        )

    def check_signature(self, public_key: rsa.RSAPublicKey) -> bool:
        return _verify(self.signature, self.data, public_key)


class MessageType(Enum):
    PEERS_REQUEST, PEERS_SHARING, APPLICATION, GET_CHAIN, CHAIN_RESPONSE = (
        range(5)
    )


class Message(BaseModel):
    message_type: MessageType
    content: Union[
        PeersRequest, PeersSharing, ApplicationData, MessageContent,
    ]

    def _to_bytes(self) -> bytes:
        return self.model_dump_json().encode(ENCODING)

    def to_raw(self, private_key: rsa.RSAPrivateKey) -> RawMessage:
        data = self._to_bytes()
        return RawMessage(data=data, signature=_sign(data, private_key))

    @staticmethod
    def _from_bytes(data: bytes) -> Message:
        try:
            return Message.model_validate_json(data.decode(ENCODING))
        except (UnicodeDecodeError, ValidationError) as e:
            raise P2PRuntimeError(
                f"cannot create Message from bytes ({e})",
            ) from e

    @staticmethod
    def from_raw(raw: RawMessage) -> Message:
        return Message._from_bytes(raw.data)

    def check_content(self) -> bool:
        return (
            (
                self.message_type == MessageType.PEERS_REQUEST
                and isinstance(self.content, PeersRequest)
            )
            or (
                self.message_type == MessageType.PEERS_SHARING
                and isinstance(self.content, PeersSharing)
            )
            or (
                self.message_type == MessageType.APPLICATION
                and isinstance(self.content, ApplicationData)
            )
            or (
                self.message_type == MessageType.GET_CHAIN
                and isinstance(self.content, MessageContent)
            )
        )

    @staticmethod
    def peers_request() -> Message:
        return Message(
            message_type=MessageType.PEERS_REQUEST, content=PeersRequest(),
        )

    @staticmethod
    def peers_sharing(peers: list[Peer]) -> Message:
        return Message(
            message_type=MessageType.PEERS_SHARING,
            content=PeersSharing(
                peers=[p.to_serialized() for p in peers if p.can_be_shared()],
            ),
        )

    @staticmethod
    def application_data(data: str) -> Message:
        return Message(
            message_type=MessageType.APPLICATION,
            content=ApplicationData(data=data),
        )

    @staticmethod
    def get_chain_request() -> Message:
        return Message(
            message_type=MessageType.GET_CHAIN, content=MessageContent(),
        )


class SerializedPeer(BaseModel):
    ip_address: str
    port: int

    def to_peer(self) -> Peer:
        return Peer(
            ip_address=self.ip_address, port=self.port, public_key=None,
        )


class MessageContent(BaseModel):
    pass


class PeersRequest(MessageContent):
    pass


class PeersSharing(MessageContent):
    peers: list[SerializedPeer]


class ApplicationData(MessageContent):
    data: str


Message.update_forward_refs()


@dataclass
class Peer:
    ip_address: str
    port: int | None
    public_key: rsa.RSAPublicKey | None

    def can_be_shared(self) -> bool:
        return self.public_key is not None and self.port is not None

    def to_serialized(self) -> SerializedPeer:
        assert self.port is not None and self.public_key is not None
        return SerializedPeer(ip_address=self.ip_address, port=self.port)


def _deserialize_public_key(data: bytes) -> rsa.RSAPublicKey:
    try:
        key = serialization.load_pem_public_key(data)
    except (
        ValueError,
        TypeError,
        cryptography.exceptions.UnsupportedAlgorithm,
    ) as e:
        raise P2PRuntimeError(f"unable to load key from bytes: {e}") from e
    if not isinstance(key, rsa.RSAPublicKey):
        raise P2PRuntimeError(f"invalid key, not a public RSA key: '{key}'")
    return key


def _serialize_public_key(key: rsa.RSAPublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _generate_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=KEY_SIZE,
    )
    return private_key, private_key.public_key()


def _sign(message: bytes, private_key: rsa.RSAPrivateKey) -> bytes:
    return private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )


def _verify(
    signature: bytes, message: bytes, public_key: rsa.RSAPublicKey,
) -> bool:
    try:
        public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
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

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.node.stop()


def _all(item: Any) -> Literal[True]:
    return True


ALL = _all


@dataclass
class Node:
    ip_address: str
    port: int
    public_ip: str | None
    serialized_port: bytes
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    serialized_public_key: bytes
    peer_links: list[PeerLink]
    server_socket: Socket
    _self_ips: set[str] | None = None

    @staticmethod
    def start(
        ip_address: str, port: int = 0, public_ip: str | None = None,
    ) -> Node:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        if not NODE_CERT_FILE.exists():
            raise P2PRuntimeError(f"cannot load cert file {NODE_CERT_FILE}")
        if not NODE_KEY_FILE.exists():
            raise P2PRuntimeError(f"cannot load key file {NODE_KEY_FILE}")
        context.load_cert_chain(certfile=NODE_CERT_FILE, keyfile=NODE_KEY_FILE)
        server_socket = Socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM)
        server_socket.bind((ip_address, port))
        server_socket.listen(NODE_BACKLOG)
        secure_server_socket = context.wrap_socket(
            server_socket, server_side=True,
        )
        private_key, public_key = _generate_key_pair()
        computed_ip_address, computed_port = secure_server_socket.getsockname()
        logger.info(f"started node on {computed_ip_address}:{computed_port}")
        final_public_ip = (
            public_ip if public_ip is not None else computed_ip_address
        )
        return Node(
            ip_address=computed_ip_address,
            port=computed_port,
            public_ip=final_public_ip,
            serialized_port=str(computed_port).encode(ENCODING),
            private_key=private_key,
            public_key=public_key,
            serialized_public_key=_serialize_public_key(public_key),
            peer_links=[],
            server_socket=secure_server_socket,
        )

    def _get_self_ips(self) -> set[str]:
        """Gathers all known IP addresses for this host and caches them.
        This is a more robust method to get all local network IPs.
        """
        if self._self_ips is None:
            # Start with the known addresses
            ips = {"127.0.0.1", "localhost", self.ip_address}
            if self.public_ip:
                ips.add(self.public_ip)

            # Try to get all IPs associated with the local hostname
            try:
                hostname = socket_lib.gethostname()
                # This can return multiple IPs, including local ones like 192.168...
                _, _, local_ips = socket_lib.gethostbyname_ex(hostname)
                ips.update(local_ips)
            except socket_lib.gaierror:
                # This can fail in some network configurations, which is okay
                logger.warning(
                    "Could not resolve local hostname to get all IPs.",
                )

            # Filter out any potential None or empty string values before caching
            self._self_ips = {ip for ip in ips if ip}
        return self._self_ips

    def _is_self(self, ip_address: str, port: int) -> bool:
        if port != self.port:
            return False
        return ip_address in self._get_self_ips()

    def stop(self) -> None:
        for link in self.peer_links:
            if link.alive:
                link.socket.close()
        self.server_socket.close()
        logger.info("closed server socket")

    def update(self) -> None:
        sockets: list[Socket] = [self.server_socket] + [
            p.socket for p in self.peer_links
        ]
        try:
            readable, _, _ = select.select(sockets, [], [], NODE_CHECK_TIME)
            if self.server_socket in readable:
                try:
                    socket, addr = self.server_socket.accept()
                    self._handle_new_connection(socket, addr)
                except (ssl.SSLEOFError, ssl.SSLError) as e:
                    if "HTTP_REQUEST" in str(e):
                        logger.warning(
                            "Ignored a plain HTTP request on the secure P2P port.",
                        )
                    elif "UNEXPECTED_EOF" in str(e):
                        logger.info(f"A peer disconnected abruptly: {e}")
                    else:
                        logger.error(f"An SSL error occurred: {e}")
                except Exception as e:
                    logger.exception(f"Error accepting connection: {e}")
            for link in self.peer_links:
                if link.socket in readable:
                    try:
                        self._recv(link)
                    except P2PRuntimeError as e:
                        logger.exception(
                            f"{link.fmt_addr()} error receiving: {e}",
                        )
                    if not link.alive:
                        logger.info(f"{link.fmt_addr()} closed connection")
            self.peer_links = [link for link in self.peer_links if link.alive]
        except Exception as e:
            logger.error(f"Error during socket selection: {e}", exc_info=True)

    def search_link_by_peer(
        self, fun: Callable[[Peer], bool],
    ) -> PeerLink | None:
        for link in self.peer_links:
            if fun(link.peer):
                return link
        return None

    def iter_links_by_peer(
        self, fun: Callable[[Peer], bool] = ALL,
    ) -> Iterable[PeerLink]:
        for link in self.peer_links:
            if fun(link.peer):
                yield link

    def search_link(self, fun: Callable[[PeerLink], bool]) -> PeerLink | None:
        for link in self.peer_links:
            if fun(link):
                return link
        return None

    def iter_links(
        self, fun: Callable[[PeerLink], bool] = ALL,
    ) -> Iterable[PeerLink]:
        for link in self.peer_links:
            if fun(link):
                yield link

    def broadcast_application_message(self, data: str) -> None:
        self._send_message_to_peers(Message.application_data(data))

    def bootstrap(
        self, ip_addr: str = BOOTSTRAP_IP_ADDR, port: int = BOOTSTRAP_PORT,
    ) -> bool | None:
        logger.info(f"Bootstrapping to target: {ip_addr}:{port}")
        if self._is_self(ip_addr, port):
            logger.warning("Bootstrap target is self. Skipping.")
            return True
        link = self.search_link_by_peer(
            lambda p: p.ip_address == ip_addr and p.port == port,
        )
        if link is None:
            link = self._create_link(ip_addr, port)
            if link is None:
                logger.error("Failed to bootstrap: can't connect to server")
                return None
            logger.info(
                f"Connection to {link.fmt_addr()} successful. Requesting data...",
            )
        self._send_message(link, Message.get_chain_request())
        self._send_message(link, Message.peers_request())
        return True

    def _connect_to_peer(self, ip_address: str, port: int) -> Socket | None:
        if self._is_self(ip_address, port):
            return None
        context = ssl.create_default_context()
        context.check_hostname, context.verify_mode = False, ssl.CERT_NONE
        socket = Socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM)
        socket.bind((self.ip_address, 0))
        socket.settimeout(NODE_CONNECTION_TIMEOUT)
        secure_socket = context.wrap_socket(socket, server_hostname=ip_address)
        try:
            secure_socket.connect((ip_address, port))
        except Exception as e:
            logger.error(f"Error connecting to {ip_address}:{port} ({e})")
            return None
        return secure_socket

    def _declare_to_peer(self, link: PeerLink) -> None:
        self._send(link, self.serialized_public_key)
        self._send(link, self.serialized_port)

    def _handle_new_connection(
        self, socket: Socket, addr: socket_lib._RetAddress,
    ) -> None:
        if socket.family != socket_lib.AF_INET:
            logger.info(f"{addr} ignoring non-INET socket: {socket.family}")
            return
        ip_addr, port = addr
        link = PeerLink(
            peer=Peer(ip_address=ip_addr, port=None, public_key=None),
            socket=socket,
            alive=True,
            buffer=b"",
        )
        self.peer_links.append(link)
        self._send(link, self.serialized_public_key)
        logger.info(f"Connection established with {ip_addr}:{port}")

    def _handle_public_key_declaration(self, link: PeerLink) -> bool:
        if link.peer.public_key is None:
            try:
                key = _deserialize_public_key(link.buffer)
            except P2PRuntimeError as e:
                logger.exception(
                    f"{link.fmt_addr()} unable to parse public key ({e})",
                )
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
                logger.exception(
                    f"{link.fmt_addr()} unable to parse port ({e})",
                )
                return True
            link.peer.port = port
            logger.info(f"{link.fmt_addr()} port set")
            return True
        return False

    def _handle_peers_request(self, link: PeerLink) -> None:
        peers = [p.peer for p in self.peer_links if p.peer.can_be_shared()]
        logger.info(f"{link.fmt_addr()} requested peers, sharing {len(peers)}")
        self._send_message(link, Message.peers_sharing(peers))

    def _handle_peers_sharing(
        self, link: PeerLink, content: PeersSharing,
    ) -> None:
        logger.info(f"{link.fmt_addr()} shared {len(content.peers)} peers")
        for serialized_peer in content.peers:
            shared_peer = serialized_peer.to_peer()
            if self._is_self(shared_peer.ip_address, shared_peer.port):
                continue
            if self.search_link_by_peer(
                lambda p: p.ip_address == shared_peer.ip_address
                and p.port == shared_peer.port,
            ):
                continue
            self._create_link(shared_peer.ip_address, shared_peer.port)

    def _create_link(self, ip_address: str, port: int) -> PeerLink | None:
        socket = self._connect_to_peer(ip_address, port)
        if socket:
            link = PeerLink(
                peer=Peer(ip_address=ip_address, port=port, public_key=None),
                socket=socket,
                alive=True,
                buffer=b"",
            )
            self.peer_links.append(link)
            self._declare_to_peer(link)
            return link
        return None

    def _handle_buffer_readable(self, link: PeerLink) -> None:
        if self._handle_public_key_declaration(link):
            return
        assert link.peer.public_key is not None
        if self._handle_port_declaration(link):
            return
        assert link.peer.port is not None
        raw_message = RawMessage.from_bytes(link.buffer)
        if not raw_message.check_signature(link.peer.public_key):
            logger.error(
                f"{link.fmt_addr()} ignoring message: invalid signature",
            )
            return
        message = Message.from_raw(raw_message)
        if not message.check_content():
            logger.error(
                f"{link.fmt_addr()} ignoring message: content/type mismatch",
            )
            return
        logger.info(f"{link.fmt_addr()} received {message.message_type}")
        self._handle_message(link, message)

    def _handle_message(self, link: PeerLink, message: Message):
        if message.message_type == MessageType.GET_CHAIN:
            if hasattr(self, "get_chain_callback") and callable(
                self.get_chain_callback,
            ):
                logger.info(
                    f"Peer {link.fmt_addr()} requested blockchain. Executing callback...",
                )
                chain_data_json = self.get_chain_callback()
                self._send_message(
                    link, Message.application_data(chain_data_json),
                )
        elif message.message_type == MessageType.APPLICATION:
            assert isinstance(message.content, ApplicationData)
            self._handle_application_message(link, message.content)
        elif message.message_type == MessageType.PEERS_REQUEST:
            self._handle_peers_request(link)
        elif message.message_type == MessageType.PEERS_SHARING:
            assert isinstance(message.content, PeersSharing)
            self._handle_peers_sharing(link, message.content)

    def _handle_application_message(
        self, link: PeerLink, content: ApplicationData,
    ) -> None:
        logger.info(f"application data: {content.data}")

    def _send_message(self, link: PeerLink, message: Message) -> None:
        raw_message = message.to_raw(self.private_key)
        self._send(link, raw_message.to_bytes())
        logger.info(f"sending {message.message_type} to {link.fmt_addr()}")

    def _send_message_to_peers(self, message: Message) -> None:
        raw_message = message.to_raw(self.private_key)
        self._send_to_peers(raw_message.to_bytes())
        logger.info(f"sending {message.message_type} to peers")

    def _send_to_peers(self, data: bytes) -> None:
        for link in self.peer_links:
            self._send(link, data)

    def _send(self, link: PeerLink, data: bytes) -> None:
        if SEPARATOR in data:
            raise P2PRuntimeError(f"found separator {SEPARATOR!r} in data")
        link.socket.sendall(data + SEPARATOR)

    def _recv(self, link: PeerLink) -> None:
        chunk = link.socket.recv(NODE_CHUNK_SIZE)
        if not chunk:
            link.alive = False
            if link.socket:
                link.socket.close()
            return
        link.buffer += chunk
        while SEPARATOR in link.buffer:
            link.buffer, rest = link.buffer.split(SEPARATOR, 1)
            self._handle_buffer_readable(link)
            link.buffer = rest


if __name__ == "__main__":
    try:
        with NodeContextManager(
            Node.start("localhost", port=int(sys.argv[1])),
        ) as node:
            if "bootstrap" in sys.argv:
                node.bootstrap()
            while True:
                time.sleep(0.1)
                node.update()
    except KeyboardInterrupt:
        logger.info("user interrupted the node. goodbye! ^-^")
