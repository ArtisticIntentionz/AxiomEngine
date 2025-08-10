
from __future__ import annotations
import ssl
import asyncio
import logging
import sys
import socket
import struct
from enum import Enum
from dataclasses import dataclass
from typing import Self, Union

from pydantic import BaseModel, ValidationError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature

from p2p.constants import ENCODING, KEY_SIZE

logger = logging.getLogger("p2p")

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

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode(ENCODING)
    
    def to_raw(self, private_key: rsa.RSAPrivateKey) -> RawMessage:
        data = self.to_bytes()

        return RawMessage(
            data=data,
            signature=sign(data, private_key)
        )

    @staticmethod
    def from_bytes(raw: bytes) -> Message:
        try:
            return Message.model_validate_json(raw.decode(ENCODING))
        
        except (UnicodeDecodeError, ValidationError):
            logger.exception(f"cannot create Message from bytes")
            raise P2PRuntimeError(f"cannot create Message from bytes")

    def check_type(self) -> bool:
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
            content=PeersSharing(peers=[peer.to_serialized() for peer in peers])
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
        key = serialization.load_pem_public_key(
            self.public_key
        )

        if not isinstance(key, rsa.RSAPublicKey):
            logger.error(f"invalid key, not a public RSA key: '{key}'")
            raise P2PRuntimeError(f"invalid key, not a public RSA key: '{key}'")

        return Peer(
            ip_address=self.ip_address,
            port=self.port,
            public_key=key,
        )

class Peer(BaseModel):
    ip_address: str
    port: int
    public_key: rsa.RSAPublicKey

    def to_serialized(self) -> SerializedPeer:
        return SerializedPeer(
            ip_address=self.ip_address,
            port=self.port,
            public_key=self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
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
class PeerSocket:
    peer: Peer
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    alive: bool


@dataclass
class Node:
    ip: str
    port: int
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    sockets: list[PeerSocket]
    server: asyncio.Server

    @staticmethod
    async def start(ip: str, port: int):
        pass

    async def _handle_new_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        sock = writer.get_extra_info("socket")
        
        if not isinstance(sock, socket.socket):
            logger.error(f"refusing connection by non socket {sock}")
            return

        if sock.family != socket.AF_INET:
            logger.error((f"refusing non INET socket: {sock.family}"))
            return
        
        ip_address, port = sock.getpeername()
        assert isinstance(ip_address, str)
        assert isinstance(port, int)


async def main():
    reader, writer = await asyncio.open_connection()
