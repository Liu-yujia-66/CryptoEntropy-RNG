"""CryptoEntropy-RNG -- password generator prototype core library.

Pipeline: fused_stream.bin -> packbits IKM -> per password a disjoint 33-byte
block -> HKDF-Extract (32-byte PRK) -> HKDF-Expand (OKM) -> charset rejection
sampling -> 16-char password. HKDF (RFC 5869, HMAC-SHA256) is implemented from
stdlib hmac/hashlib only and self-checked against RFC 5869 App. A Test Case 1
via hkdf_selftest(). Exposes three generators for the evaluation groups:
generate_market_cell (market entropy), generate_b2_cell (salt-seeded random IKM)
and generate_b1_cell (salt-seeded uniform sampling, no HKDF); the salt-seeded
baselines reproduce bit-for-bit on re-run.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import random
import string

import numpy as np

CHARSET = (
    string.ascii_lowercase      # 26
    + string.ascii_uppercase    # 26
    + string.digits             # 10
    + "!@#$%^&*"                # 8
)
CHARSET_SIZE = len(CHARSET)
assert CHARSET_SIZE == 70, f"charset must be 70 characters, got {CHARSET_SIZE}"

# Rejection-sampling cutoff: keep a byte only if it is below the largest
# multiple of 70 that fits in one byte.  256 // 70 == 3, so MAX_VALID == 210
# and the acceptance rate is 210 / 256 = 82.0 %.
MAX_VALID = (256 // CHARSET_SIZE) * CHARSET_SIZE   # 210

# Prototype parameters
IKM_BYTES = 33                              # per-password disjoint IKM block
INFO_BASE = b"CryptoEntropy-Password-v1"    # HKDF info string (counter appended)
EXPAND_LEN = 32                             # OKM bytes produced per Expand round
MAX_EXPAND_ROUNDS = 256                     # defensive cap on the re-expand loop
PASSWORD_LENGTH = 16
SALT_BYTES = 32

_HASH = hashlib.sha256
_HASH_LEN = 32


class InsufficientIKM(Exception):
    """Raised when a fused stream cannot supply enough disjoint IKM blocks."""

    def __init__(self, have: int, need: int):
        self.have = have
        self.need = need
        super().__init__(f"insufficient IKM: have {have} bytes, need {need}")


# HKDF -- RFC 5869, HMAC-SHA256
def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """HKDF-Extract (RFC 5869 Section 2.2): PRK = HMAC-Hash(salt, IKM)."""
    if not salt:
        salt = b"\x00" * _HASH_LEN
    return hmac.new(salt, ikm, _HASH).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand (RFC 5869 Section 2.3)."""
    max_len = 255 * _HASH_LEN
    if length > max_len:
        raise ValueError(f"cannot expand to more than {max_len} bytes")
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), _HASH).digest()
        okm += block
        counter += 1
    return okm[:length]


# RFC 5869 Appendix A, Test Case 1 (SHA-256) -- used by hkdf_selftest().
_RFC5869_TC1 = {
    "ikm": bytes.fromhex("0b" * 22),
    "salt": bytes.fromhex("000102030405060708090a0b0c"),
    "info": bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"),
    "length": 42,
    "prk": bytes.fromhex(
        "077709362c2e32df0ddc3f0dc47bba63"
        "90b6c73bb50f9c3122ec844ad7c2b3e5"
    ),
    "okm": bytes.fromhex(
        "3cb25f25faacd57a90434f64d0362f2a"
        "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
        "34007208d5b887185865"
    ),
}


def hkdf_selftest() -> str:
    """Verify the HKDF implementation against RFC 5869 Test Case 1.

    Returns a short status string on success; raises AssertionError on failure.
    """
    tc = _RFC5869_TC1
    prk = hkdf_extract(tc["salt"], tc["ikm"])
    if prk != tc["prk"]:
        raise AssertionError("HKDF-Extract failed RFC 5869 Appendix A Test Case 1")
    okm = hkdf_expand(prk, tc["info"], tc["length"])
    if okm != tc["okm"]:
        raise AssertionError("HKDF-Expand failed RFC 5869 Appendix A Test Case 1")
    return "PASS (RFC 5869 Appendix A, Test Case 1, SHA-256)"


# IKM loading
def load_ikm_bytes(bin_path) -> bytes:
    """Load a fused_stream.bin and pack it into IKM bytes.

    The Exp 4 fused stream stores one bit per byte (values 0/1); ``np.packbits``
    groups 8 consecutive bits into one byte.  The number of usable IKM bytes is
    therefore file_size // 8.
    """
    raw = np.frombuffer(open(bin_path, "rb").read(), dtype=np.uint8)
    if raw.size and int(raw.max()) > 1:
        raise ValueError(
            f"{bin_path}: expected a 0/1 byte-per-bit stream, found max byte "
            f"{int(raw.max())}"
        )
    return np.packbits(raw).tobytes()


# Charset mapping and password derivation
def _accepted_chars(okm: bytes) -> list[str]:
    """Map OKM bytes to charset characters via rejection sampling."""
    return [CHARSET[b % CHARSET_SIZE] for b in okm if b < MAX_VALID]


def password_from_prk(prk: bytes, length: int = PASSWORD_LENGTH,
                      info_base: bytes = INFO_BASE,
                      expand_len: int = EXPAND_LEN) -> tuple[str, int]:
    """Derive one password from a PRK via HKDF-Expand + rejection sampling.

    ``info`` is ``info_base`` followed by a 4-byte big-endian re-expand counter.
    The counter starts at 0 (first round) and is incremented only when a round
    of OKM is exhausted before ``length`` characters have been accepted -- an
    event with probability ~1e-5 per password at the parameters used here.

    Returns ``(password, n_rounds)`` where ``n_rounds`` is the number of
    Expand rounds consumed (1 in almost every case).
    """
    chars: list[str] = []
    counter = 0
    while len(chars) < length:
        if counter >= MAX_EXPAND_ROUNDS:
            # Defensive stop: unreachable under a working PRF (failing to
            # collect `length` characters within MAX_EXPAND_ROUNDS rounds has
            # negligible probability).  The guard prevents an infinite loop
            # should a future PRF/charset change break that assumption.
            raise RuntimeError(
                f"rejection sampling failed to yield {length} characters "
                f"within {MAX_EXPAND_ROUNDS} HKDF-Expand rounds"
            )
        info = info_base + counter.to_bytes(4, "big")
        chars.extend(_accepted_chars(hkdf_expand(prk, info, expand_len)))
        counter += 1
    return "".join(chars[:length]), counter


def password_from_ikm(ikm: bytes, salt: bytes,
                      length: int = PASSWORD_LENGTH,
                      info_base: bytes = INFO_BASE) -> tuple[str, int]:
    """Full per-password pipeline: IKM -> Extract -> Expand -> charset password."""
    if len(ikm) != IKM_BYTES:
        raise ValueError(f"IKM must be exactly {IKM_BYTES} bytes, got {len(ikm)}")
    prk = hkdf_extract(salt, ikm)
    return password_from_prk(prk, length, info_base)


# Cell generators -- one "cell" is one (group, month[, n]) batch of passwords
def generate_market_cell(ikm_bytes: bytes, salt: bytes, n_passwords: int,
                         length: int = PASSWORD_LENGTH) -> list[tuple[str, int]]:
    """Market group: each password uses a disjoint 33-byte block of the stream.

    Password i consumes ikm_bytes[i*33 : (i+1)*33].  Raises InsufficientIKM if
    the stream is too short.
    """
    need = n_passwords * IKM_BYTES
    if len(ikm_bytes) < need:
        raise InsufficientIKM(have=len(ikm_bytes), need=need)
    out = []
    for i in range(n_passwords):
        block = ikm_bytes[i * IKM_BYTES:(i + 1) * IKM_BYTES]
        out.append(password_from_ikm(block, salt, length))
    return out


def _seeded_rng(salt: bytes, label: str) -> random.Random:
    """A deterministic RNG seeded from the persisted salt plus a label.

    Used for the baseline groups: given the repository-persisted salt, B1 and
    B2 regenerate identically on every run, making the whole demo reproducible.
    A standard RNG is statistically uniform far beyond what the chi-square /
    entropy evaluation can resolve; it is used here only as an ideal-uniform
    reference, not as a security primitive.
    """
    return random.Random(b"CryptoEntropy|" + label.encode() + b"|" + salt)


def generate_b2_cell(salt: bytes, tag: str, n_passwords: int,
                     length: int = PASSWORD_LENGTH) -> list[tuple[str, int]]:
    """Baseline B2: an ideal random IKM through the same HKDF pipeline.

    The 33-byte IKM is drawn from a salt-seeded RNG (so the demo is
    reproducible) -- this isolates the entropy *source* while keeping the HKDF
    conditioning pipeline identical to the market group.
    """
    rng = _seeded_rng(salt, f"B2|{tag}")
    out = []
    for _ in range(n_passwords):
        out.append(password_from_ikm(rng.randbytes(IKM_BYTES), salt, length))
    return out


def generate_b1_cell(salt: bytes, tag: str, n_passwords: int,
                     length: int = PASSWORD_LENGTH) -> list[tuple[str, int]]:
    """Baseline B1: uniform charset sampling, bypassing HKDF.

    Each character is drawn uniformly from the 70-character set by a salt-seeded
    RNG -- the deterministic, reproducible analogue of ``secrets.choice``.  B1
    bypasses HKDF and rejection sampling entirely; it is the "ideal password"
    reference.  ``n_rounds`` is reported as 0 (no HKDF-Expand was used).
    """
    rng = _seeded_rng(salt, f"B1|{tag}")
    return [
        ("".join(rng.choice(CHARSET) for _ in range(length)), 0)
        for _ in range(n_passwords)
    ]


# Salt management
def load_or_create_salt(salt_path) -> bytes:
    """Return the persisted HKDF salt, creating it once from os.urandom.

    The salt is persisted in the repository so the demo is fully reproducible.
    An HKDF salt may be public; a production deployment would rotate it per
    deployment/epoch.
    """
    if os.path.exists(salt_path):
        with open(salt_path, "rb") as fh:
            salt = fh.read()
        if len(salt) != SALT_BYTES:
            raise ValueError(
                f"{salt_path}: salt is {len(salt)} bytes, expected {SALT_BYTES}"
            )
        return salt
    salt = os.urandom(SALT_BYTES)
    os.makedirs(os.path.dirname(salt_path), exist_ok=True)
    with open(salt_path, "wb") as fh:
        fh.write(salt)
    return salt


if __name__ == "__main__":
    # Quick smoke test when run directly.
    print("HKDF self-test:", hkdf_selftest())
    _salt = os.urandom(SALT_BYTES)
    _pw, _rounds = password_from_ikm(os.urandom(IKM_BYTES), _salt)
    print(f"sample password: {_pw}  (length {len(_pw)}, {_rounds} expand round)")
    assert len(_pw) == PASSWORD_LENGTH
    assert all(c in CHARSET for c in _pw)
    print("charset / length checks: OK")
