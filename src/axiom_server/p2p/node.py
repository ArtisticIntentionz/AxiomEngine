"""Defining the base unit of P2P network, a Node."""

from __future__ import annotations

import logging
import os
import select
import socket as socket_lib
import ssl
import sys
import time
from dataclasses import dataclass
from enum import Enum

# Yes, I am renaming socket.socket because type names should
# start with an uppercase character.
from socket import socket as Socket  # noqa N812
from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import TracebackType

import cryptography
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

logger = logging.getLogger(__name__)

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
    """Raised when the system can't recover from a situation."""

    __slots__ = ()


class RawMessage(BaseModel):
    """Represent a message ready to be transmitted over network.

    The main job of this layer is to check the authenticity of
    the sender.
    """

    data: bytes
    signature: bytes

    def to_bytes(self) -> bytes:
        """Encode this into a byte buffer."""
        return self.signature + self.data

    @staticmethod
    def from_bytes(data: bytes) -> RawMessage:
        """Decode a byte buffer to a raw message."""
        return RawMessage(
            signature=data[:SIGNATURE_SIZE],
            data=data[SIGNATURE_SIZE:],
        )

    def check_signature(self, public_key: rsa.RSAPublicKey) -> bool:
        """Check the validity of the signature.

        Returns True if and only if public_key is paired with
        the private key used to sign the message.
        This establishes the authenticity of the emitter.
        """
        return _verify(self.signature, self.data, public_key)


class MessageType(Enum):
    """Represent the possible message types."""

    PEERS_REQUEST = 0
    PEERS_SHARING = 1
    APPLICATION = 2


class Message(BaseModel):
    """A message carrying information."""

    message_type: MessageType
    content: PeersRequest | PeersSharing | ApplicationData

    def _to_bytes(self) -> bytes:
        return self.model_dump_json().encode(ENCODING)

    def to_raw(self, private_key: rsa.RSAPrivateKey) -> RawMessage:
        """Create a raw message, signing it."""
        data = self._to_bytes()

        return RawMessage(data=data, signature=_sign(data, private_key))

    @staticmethod
    def _from_bytes(data: bytes) -> Message:
        try:
            return Message.model_validate_json(data.decode(ENCODING))

        except (UnicodeDecodeError, ValidationError) as e:
            message = f"cannot create Message from bytes ({e})"
            logger.exception(message)
            raise P2PRuntimeError(message) from e

    @staticmethod
    def from_raw(raw: RawMessage) -> Message:
        """Decode a raw message."""
        return Message._from_bytes(raw.data)

    def check_content(self) -> bool:
        """Check the pertinence of message_type and the actual type of content."""
        if self.message_type == MessageType.PEERS_REQUEST and isinstance(
            self.content,
            PeersRequest,
        ):
            return True
        if self.message_type == MessageType.PEERS_SHARING and isinstance(
            self.content,
            PeersSharing,
        ):
            return True
        return self.message_type == MessageType.APPLICATION and isinstance(
            self.content,
            ApplicationData,
        )

    @staticmethod
    def peers_request() -> Message:
        """Build a peers request message."""
        return Message(
            message_type=MessageType.PEERS_REQUEST,
            content=PeersRequest(),
        )

    @staticmethod
    def peers_sharing(peers: list[Peer]) -> Message:
        """Build a peers sharing message."""
        return Message(
            message_type=MessageType.PEERS_SHARING,
            content=PeersSharing(
                peers=[
                    peer.to_serialized()
                    for peer in peers
                    if peer.can_be_shared()
                ],
            ),
        )

    @staticmethod
    def application_data(data: str) -> Message:
        """Build a message carrying application data."""
        return Message(
            message_type=MessageType.APPLICATION,
            content=ApplicationData(data=data),
        )


class MessageContent(BaseModel):
    """Data transmitted in a message."""


class PeersRequest(MessageContent):
    """Request for sharing of peer information."""


class PeersSharing(MessageContent):
    """Peer information sharing."""

    peers: list[SerializedPeer]


class ApplicationData(MessageContent):
    """Client code data."""

    data: str


class SerializedPeer(BaseModel):
    """Represent a peer ready to be transmitted over network."""

    ip_address: str
    port: int

    def to_peer(self) -> Peer:
        """Deserialize the peer."""
        return Peer(
            ip_address=self.ip_address,
            port=self.port,
            public_key=None,
        )


@dataclass
class Peer:
    """Represent the home address of a node."""

    ip_address: str
    port: int | None
    public_key: rsa.RSAPublicKey | None

    def can_be_shared(self) -> bool:
        """Check if the peer can be shared.

        This means checking if the peer has declared a home port and public key.
        """
        return self.public_key is not None and self.port is not None

    def to_serialized(self) -> SerializedPeer:
        """Serialize the peer."""
        assert self.port is not None
        assert self.public_key is not None
        return SerializedPeer(ip_address=self.ip_address, port=self.port)


def _deserialize_public_key(data: bytes) -> rsa.RSAPublicKey:
    try:
        key = serialization.load_pem_public_key(data)

    except (
        ValueError,
        TypeError,
        cryptography.exceptions.UnsupportedAlgorithm,
    ) as e:
        message = f"unable to load key from bytes: {e}"
        logger.exception(message)
        raise P2PRuntimeError(message) from e

    if not isinstance(key, rsa.RSAPublicKey):
        message = f"invalid key, not a public RSA key: '{key}'"
        logger.error(message)
        raise P2PRuntimeError(message)

    return key


def _serialize_public_key(key: rsa.RSAPublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


# the following is taken from https://elc.github.io/python-security/chapters/07_Asymmetric_Encryption.html#rsa-encryption


def _generate_key_pair(
    seed: str = "axiom_shared_key",
) -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate or load a shared key pair for all nodes to use the same identity."""
    # Use a shared key file to ensure all nodes have the same key pair
    shared_key_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "shared_node_key.pem",
    )

    # Check if we should use shared keys (for testing/multi-node setup)
    use_shared_keys = (
        os.environ.get("AXIOM_SHARED_KEYS", "true").lower() == "true"
    )

    if use_shared_keys and os.path.exists(shared_key_file):
        # Load existing shared key
        try:
            with open(shared_key_file, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                )
            # Add a type check to satisfy mypy and ensure we have an RSA key.
            if not isinstance(private_key, rsa.RSAPrivateKey):
                # If it's not an RSA key, we treat it as a failure to load.
                raise TypeError("Loaded key is not an RSA private key.")

            public_key = private_key.public_key()
            logger.info("Loaded shared key pair from file")
            return private_key, public_key
        except (Exception, TypeError) as e:
            logger.warning(
                f"Failed to load or validate shared key: {e}, generating new one",
            )

    # Generate new key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE,
    )
    public_key = private_key.public_key()

    # Save the key if using shared keys
    if use_shared_keys:
        try:
            with open(shared_key_file, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    ),
                )
            logger.info(f"Saved shared key pair to {shared_key_file}")
        except Exception as e:
            logger.warning(f"Failed to save shared key: {e}")

    return private_key, public_key


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
    signature: bytes,
    message: bytes,
    public_key: rsa.RSAPublicKey,
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
    """Represents an active link with a peer."""

    peer: Peer
    socket: Socket
    alive: bool
    buffer: bytes

    def fmt_addr(self) -> str:
        """Give a short description of the peer home address."""
        return f"{self.peer.ip_address}:{self.peer.port}"


@dataclass
class NodeContextManager:
    """Handle the systematic stopping of the given node."""

    node: Node

    def __enter__(self) -> Node:
        """Return the node."""
        return self.node

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Handle stopping the node."""
        self.node.stop()


def _all(item: Any) -> Literal[True]:
    return True


ALL = _all


@dataclass
class Node:
    """A P2P node, associated with a home address, and RSA keys."""

    ip_address: str
    port: int
    serialized_port: bytes
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    serialized_public_key: bytes
    peer_links: list[PeerLink]
    server_socket: Socket

    @staticmethod
    def start(ip_address: str, port: int = 0) -> Node:
        """Create a new Node by generating new public and private keys, binding the home socket to ip_address and port.

        Args:
            ip_address str: the ip_address to bind to.
            port int: the port to bind to.

        """
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

        if not NODE_CERT_FILE.exists():
            message = f"cannot load cert file {NODE_CERT_FILE}"
            logger.error(message)
            raise P2PRuntimeError(message)

        if not NODE_KEY_FILE.exists():
            message = f"cannot load key file {NODE_KEY_FILE}"
            logger.error(message)
            raise P2PRuntimeError(message)

        context.load_cert_chain(certfile=NODE_CERT_FILE, keyfile=NODE_KEY_FILE)
        server_socket = Socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM)
        # Allow quick restart without waiting for TIME_WAIT to expire
        server_socket.setsockopt(
            socket_lib.SOL_SOCKET,
            socket_lib.SO_REUSEADDR,
            1,
        )
        server_socket.bind((ip_address, port))
        server_socket.listen(NODE_BACKLOG)
        secure_server_socket = context.wrap_socket(
            server_socket,
            server_side=True,
        )
        private_key, public_key = _generate_key_pair()
        computed_ip_address, computed_port = secure_server_socket.getsockname()
        assert isinstance(computed_ip_address, str)
        assert isinstance(computed_port, int)
        logger.info(f"started node on {computed_ip_address}:{computed_port}")
        return Node(
            ip_address=computed_ip_address,
            port=computed_port,
            serialized_port=str(computed_port).encode(ENCODING),
            private_key=private_key,
            public_key=public_key,
            serialized_public_key=_serialize_public_key(public_key),
            peer_links=[],
            server_socket=secure_server_socket,
        )

    def stop(self) -> None:
        """Stop the node by closing all active peer connections and the server socket.

        This method iterates through all peer links, closes the socket for each active link,
        and then closes the main server socket.
        """
        for link in self.peer_links:
            if link.alive:
                link.socket.close()

        self.server_socket.close()
        logger.info("closed server socket")

    def update(self) -> None:
        """Handle incoming and outgoing network events for the node.

        This method performs the following tasks:
            - Monitors the server socket and all peer sockets for readability.
            - Accepts new incoming connections.
            - Receives data from connected peers.
            - Handles exceptions during connection acceptance and data reception, logging errors.
            - Removes peer links that are no longer alive from the list of active connections.

        Raises:
            Exception: If an error occurs while accepting a new connection.
            P2PRuntimeError: If an error occurs while receiving data from a peer.

        """
        sockets: list[Socket] = [self.server_socket] + [
            peer_link.socket for peer_link in self.peer_links
        ]
        readable: list[Socket]
        readable, _, _ = select.select(sockets, [], [], NODE_CHECK_TIME)

        if self.server_socket in readable:
            try:
                socket, addr = self.server_socket.accept()
                self._handle_new_connection(socket, addr)

            except Exception as e:
                logger.exception(
                    f"error while accepting incoming connection: {e}",
                )

        for link in self.peer_links:
            if link.socket in readable:
                try:
                    self._recv(link)

                except P2PRuntimeError as e:
                    logger.exception(
                        f"{link.fmt_addr()} error while receiving: {e}",
                    )

                if not link.alive:
                    logger.info(f"{link.fmt_addr()} closed connection")

        self.peer_links = [link for link in self.peer_links if link.alive]

    def search_link_by_peer(
        self,
        fun: Callable[[Peer], bool],
    ) -> PeerLink | None:
        """Search for a PeerLink in the peer_links list whose associated Peer satisfies the given predicate function.

        Args:
            fun (Callable[[Peer], bool]): A function that takes a Peer object and returns True if the Peer matches the search criteria.

        Returns:
            PeerLink | None: The first PeerLink whose associated Peer satisfies the predicate, or None if no such PeerLink is found.

        """
        for link in self.peer_links:
            if fun(link.peer):
                return link

        return None

    def iter_links_by_peer(
        self,
        fun: Callable[[Peer], bool] = ALL,
    ) -> Iterable[PeerLink]:
        """Iterate over peer links, yielding those whose associated peer satisfies a given condition.

        Args:
            fun (Callable[[Peer], bool], optional): A predicate function that takes a Peer object and returns True if the link should be yielded. Defaults to ALL (a function that always returns True).

        Yields:
            PeerLink: The peer link whose associated peer satisfies the predicate function.

        """
        for link in self.peer_links:
            if fun(link.peer):
                yield link

    def search_link(self, fun: Callable[[PeerLink], bool]) -> PeerLink | None:
        """Search for a peer link in self.peer_links that matches a given condition.

        Args:
            fun (Callable[[PeerLink], bool]): A function that takes a PeerLink object and returns True if it matches the desired condition.

        Returns:
            PeerLink | None: The first PeerLink object that satisfies the condition, or None if no such link is found.

        """
        for link in self.peer_links:
            if fun(link):
                return link

        return None

    def iter_links(
        self,
        fun: Callable[[PeerLink], bool] = ALL,
    ) -> Iterable[PeerLink]:
        """Iterate over peer links, yielding those for which the provided function returns True.

        Args:
            fun (Callable[[PeerLink], bool], optional): A predicate function that takes a PeerLink and returns True if the link should be yielded. Defaults to ALL, which yields all links.

        Yields:
            PeerLink: Each peer link for which the predicate function returns True.

        """
        for link in self.peer_links:
            if fun(link):
                yield link

    def broadcast_application_message(self, data: str) -> None:
        """Broadcast an application-level def send_application_message to all connected peers.

        This method wraps the provided data in an application-specific message format
        and sends it to all peers connected to the node.

        Args:
            data (str): The application data to be sent to peers.

        """
        message = Message.application_data(data)
        self._send_message_to_peers(message)

    def bootstrap(
        self,
        ip_addr: str = BOOTSTRAP_IP_ADDR,
        port: int = BOOTSTRAP_PORT,
    ) -> bool:
        """Attempt to connect this node to a target peer in the network.

        This method searches for an existing link to the specified peer using its IP address and port.
        If no such link exists, it tries to create a new link.
        Upon successful connection, it sends a request for the peer list of the target node.

        Args:
            ip_addr (str): The IP address of the peer to bootstrap to. Defaults to BOOTSTRAP_IP_ADDR.
            port (int): The port of the peer to bootstrap to. Defaults to BOOTSTRAP_PORT.

        Returns:
            None

        """
        logger.info(f"Bootstrapping to target: {ip_addr}:{port}")
        link = self.search_link_by_peer(
            lambda peer: peer.ip_address == ip_addr and peer.port == port,
        )

        if link is None:
            link = self._create_link(ip_addr, port)

            if link is None:
                logger.error("failed to bootstrap: can't connect to server")
                return False

        self._send_message(link, Message.peers_request())
        return True

    def _connect_to_peer(self, ip_address: str, port: int) -> Socket | None:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        socket = Socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM)
        socket.bind((self.ip_address, 0))
        socket.settimeout(NODE_CONNECTION_TIMEOUT)
        secure_socket = context.wrap_socket(socket, server_hostname=ip_address)

        try:
            secure_socket.connect((ip_address, port))

        except (
            OSError,
            socket_lib.herror,
            socket_lib.gaierror,
            socket_lib.timeout,
            TimeoutError,
            InterruptedError,
            Exception,
        ) as e:
            # just in case you want to go back to specific error catching,
            # don't delete the explicit error types
            logger.exception(
                f"error while trying to connect to {ip_address}:{port} ({e})",
            )
            return None

        return secure_socket

    def _declare_to_peer(self, link: PeerLink) -> None:
        self._send(link, self.serialized_public_key)
        self._send(link, self.serialized_port)

    def _handle_new_connection(
        self,
        socket: Socket,
        addr: socket_lib._RetAddress,
    ) -> None:
        if socket.family != socket_lib.AF_INET:
            logger.info(f"{addr} ignoring non INET socket: {socket.family}")
            return

        ip_addr, port = addr
        assert isinstance(ip_addr, str)
        assert isinstance(port, int)
        link = PeerLink(
            peer=Peer(ip_address=ip_addr, port=None, public_key=None),
            socket=socket,
            alive=True,
            buffer=b"",
        )
        self.peer_links.append(link)
        self._send(link, self.serialized_public_key)
        logger.info(f"{link.fmt_addr()} established connection")

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
        peers = [
            link.peer for link in self.peer_links if link.peer.can_be_shared()
        ]
        logger.info(
            f"{link.fmt_addr()} requested we share peers with them, sharing {len(peers)} peers",
        )

        self._send_message(link, Message.peers_sharing(peers))

    def _handle_peers_sharing(
        self,
        link: PeerLink,
        content: PeersSharing,
    ) -> None:
        logger.info(f"{link.fmt_addr()} shared {len(content.peers)} peers")

        for serialized_peer in content.peers:
            shared_peer = serialized_peer.to_peer()
            if (
                shared_peer.ip_address == self.ip_address
                and shared_peer.port == self.port
            ):
                continue
            assert shared_peer.port is not None

            def check_peer_eq(
                peer: Peer,
                shared_peer: Peer = shared_peer,
            ) -> bool:
                """Return if peers are equivalent."""
                return (
                    peer.ip_address == shared_peer.ip_address
                    and peer.port == shared_peer.port
                )

            if self.search_link_by_peer(
                check_peer_eq,
            ):
                continue
            self._create_link(shared_peer.ip_address, shared_peer.port)

    def _create_link(self, ip_address: str, port: int) -> PeerLink | None:
        socket = self._connect_to_peer(ip_address, port)

        if socket is not None:
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
                f"{link.fmt_addr()} ignoring message because the signature doesn't match content",
            )
            return

        message = Message.from_raw(raw_message)

        if not message.check_content():
            logger.error(
                f"{link.fmt_addr()} ignoring message because the content doesn't match the type indicator",
            )
            return

        logger.info(f"{link.fmt_addr()} received {message.message_type}")
        self._handle_message(link, message)

    def _handle_message(self, link: PeerLink, message: Message) -> None:
        if message.message_type == MessageType.APPLICATION:
            assert isinstance(message.content, ApplicationData)
            self._handle_application_message(link, message.content)

        if message.message_type == MessageType.PEERS_REQUEST:
            self._handle_peers_request(link)

        if message.message_type == MessageType.PEERS_SHARING:
            assert isinstance(message.content, PeersSharing)
            self._handle_peers_sharing(link, message.content)

    def _handle_application_message(
        self,
        link: PeerLink,
        content: ApplicationData,
    ) -> None:
        logger.info(f"application data: {content.data}")

    def _send_message(self, link: PeerLink, message: Message) -> None:
        raw_message = message.to_raw(self.private_key)
        data = raw_message.to_bytes()
        logger.info(f"sending {message.message_type} to {link.fmt_addr()}")
        self._send(link, data)

    def _send_message_to_peers(self, message: Message) -> None:
        raw_message = message.to_raw(self.private_key)
        data = raw_message.to_bytes()
        logger.info(f"sending {message.message_type} to peers")
        self._send_to_peers(data)

    def _send_to_peers(self, data: bytes) -> None:
        for link in self.peer_links:
            self._send(link, data)

    def _send(self, link: PeerLink, data: bytes) -> None:
        if SEPARATOR in data:
            message = f"found separator {SEPARATOR!r} in data to send, which is not permitted"
            logger.error(message)
            raise P2PRuntimeError(message)
        try:
            link.socket.sendall(data + SEPARATOR)
        except (OSError, ssl.SSLError) as e:
            logger.warning(
                f"{link.fmt_addr()} send failed: {e}; closing link",
            )
            link.alive = False
            try:
                link.socket.close()
            except Exception as close_exc:
                logger.debug(
                    f"Exception during socket cleanup for {link.fmt_addr()}: {close_exc}",
                )

    def _recv(self, link: PeerLink) -> None:
        chunk = link.socket.recv(NODE_CHUNK_SIZE)

        if not chunk:
            link.alive = False
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
        logger.info("user interrupted the node. goodbye! ^--^")
