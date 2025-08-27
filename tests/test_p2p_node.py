from axiom_server.p2p.node import RawMessage, _generate_key_pair, _sign


def test_rawmessage_sign_and_verify() -> None:
    # Generate key pair
    private_key, public_key = _generate_key_pair()
    data = b"hello world"
    # Sign data
    signature = _sign(data, private_key)
    # Create RawMessage
    raw = RawMessage(data=data, signature=signature)
    # Check signature with correct key
    assert raw.check_signature(public_key)
    # Tamper with data
    tampered = RawMessage(data=b"goodbye", signature=signature)
    assert not tampered.check_signature(public_key)


def test_rawmessage_to_bytes_and_from_bytes() -> None:
    private_key, _ = _generate_key_pair()
    data = b"test bytes"
    signature = _sign(data, private_key)
    raw = RawMessage(data=data, signature=signature)
    # Convert to bytes and back
    raw_bytes = raw.to_bytes()
    raw2 = RawMessage.from_bytes(raw_bytes)
    assert raw2.signature == signature
    assert raw2.data == data
