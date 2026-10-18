"""Parse only explicitly submitted short-lived key text; never open files or use agents."""

from io import StringIO
import base64
import struct
from typing import Any
import paramiko  # type: ignore[import-untyped]

from easyai.domain.ssh import SshFailure


def _openssh_kind(text: str) -> str:
    """Bound KDF work before any SDK decoder can enter bcrypt.kdf.

    OpenSSH PROTOCOL.key: magic, cipher/kdf/options strings, uint32 nkeys,
    one public key string, encrypted private data. No implicit KDF algorithms.
    """
    lines = text.strip().splitlines()
    if (
        lines[0] != "-----BEGIN OPENSSH PRIVATE KEY-----"
        or lines[-1] != "-----END OPENSSH PRIVATE KEY-----"
    ):
        raise ValueError
    data = base64.b64decode("".join(lines[1:-1]), validate=True)
    magic = b"openssh-key-v1\0"
    if not data.startswith(magic):
        raise ValueError
    offset = len(magic)

    def word() -> int:
        nonlocal offset
        value = int(struct.unpack_from(">I", data, offset)[0])
        offset += 4
        return value

    def string() -> bytes:
        nonlocal offset
        length = word()
        if length > 65536 or offset + length > len(data):
            raise ValueError
        value = data[offset : offset + length]
        offset += length
        return value

    cipher, kdf, options = string(), string(), string()
    if word() != 1:
        raise ValueError
    public = string()
    if len(public) < 4:
        raise ValueError
    name_length = struct.unpack_from(">I", public)[0]
    if name_length > 64 or name_length + 4 > len(public):
        raise ValueError
    name = public[4 : 4 + name_length].decode("ascii")
    string()  # Private section must fit in the bounded envelope.
    if offset != len(data):
        raise ValueError
    if cipher == b"none":
        if kdf != b"none" or options:
            raise ValueError
    elif cipher in {b"aes256-ctr", b"aes256-cbc"} and kdf == b"bcrypt":
        if len(options) < 8:
            raise ValueError
        salt_length = struct.unpack_from(">I", options)[0]
        if not 16 <= salt_length <= 64 or len(options) != salt_length + 8:
            raise ValueError
        rounds = struct.unpack_from(">I", options, salt_length + 4)[0]
        if not 1 <= rounds <= 64:
            raise ValueError
    else:
        raise ValueError
    return name


def load_private_key(text: str, passphrase: str) -> Any:
    result: Any = None
    failure = "SSH_PRIVATE_KEY_INVALID"
    try:
        if len(text.encode("utf-8")) > 65536 or "\0" in text or "\0" in passphrase:
            raise ValueError
        if text.startswith("-----BEGIN OPENSSH PRIVATE KEY-----"):
            name = _openssh_kind(text)
            kinds = {
                "ssh-rsa": paramiko.RSAKey,
                "ssh-ed25519": paramiko.Ed25519Key,
                "ecdsa-sha2-nistp256": paramiko.ECDSAKey,
                "ecdsa-sha2-nistp384": paramiko.ECDSAKey,
                "ecdsa-sha2-nistp521": paramiko.ECDSAKey,
            }
            selected = kinds[name]
        elif text.startswith("-----BEGIN RSA PRIVATE KEY-----"):
            selected = paramiko.RSAKey
        elif text.startswith("-----BEGIN EC PRIVATE KEY-----"):
            selected = paramiko.ECDSAKey
        else:
            raise ValueError
        for kind in (selected,):
            stream = StringIO(text)
            try:
                result = kind.from_private_key(stream, password=passphrase or None)
                break
            except paramiko.PasswordRequiredException:
                failure = "SSH_KEY_PASSPHRASE_REQUIRED"
            except Exception:
                pass
            finally:
                stream.close()
    except Exception:
        result = None
    finally:
        text, passphrase = "", ""
    if result is None:
        raise SshFailure(failure) from None
    return result
