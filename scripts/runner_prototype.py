"""Prototype demo runner -- CryptoEntropy-RNG password generator.

Generates the three evaluation groups:

    market   n in {2,3,5} x 6 validation months  -> 18 cells x 100 = 1,800 passwords
    B1       6 validation months                 ->  6 cells x 100 =   600 passwords
    B2       6 validation months                 ->  6 cells x 100 =   600 passwords

Market passwords use disjoint 33-byte IKM blocks of the Exp 4 fused streams;
B1 is salt-seeded uniform charset sampling (no HKDF); B2 is a salt-seeded
random IKM through the same HKDF pipeline.  Every group is seeded from one
repository-persisted salt, so the whole demo reproduces bit-for-bit.

Usage:
    python scripts/runner_prototype.py \
        --n 100 --length 16 --fusion-n 2,3,5 \
        --months 2025-10,2025-11,2025-12,2026-01,2026-02,2026-03
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
import prototype as proto  # noqa: E402

VALIDATION_DIR = REPO / "data" / "processed" / "experiment4" / "validation"
OUT_DIR = REPO / "data" / "processed" / "prototype"
DEFAULT_MONTHS = "2025-10,2025-11,2025-12,2026-01,2026-02,2026-03"
DEFAULT_FUSION_N = "2,3,5"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_cell(cell_dir: Path, pairs: list[tuple[str, int]], meta: dict) -> None:
    """Write passwords.txt (one password per line) and metadata.json for one cell."""
    cell_dir.mkdir(parents=True, exist_ok=True)
    with open(cell_dir / "passwords.txt", "w") as fh:
        fh.write("\n".join(pw for pw, _ in pairs) + "\n")
    rounds_hist = Counter(rounds for _, rounds in pairs)
    meta = dict(meta)
    meta["expand_rounds_histogram"] = {str(k): rounds_hist[k]
                                       for k in sorted(rounds_hist)}
    meta["generated_utc"] = _utc_now()
    with open(cell_dir / "metadata.json", "w") as fh:
        json.dump(meta, fh, indent=2)


def main() -> None:
    ap = argparse.ArgumentParser(description="CryptoEntropy-RNG prototype demo runner")
    ap.add_argument("--n", type=int, default=100, help="passwords per cell")
    ap.add_argument("--length", type=int, default=proto.PASSWORD_LENGTH,
                    help="password length in characters")
    ap.add_argument("--fusion-n", default=DEFAULT_FUSION_N,
                    help="comma-separated market fusion sizes")
    ap.add_argument("--months", default=DEFAULT_MONTHS,
                    help="comma-separated validation months")
    args = ap.parse_args()

    fusion_n = [int(x) for x in args.fusion_n.split(",")]
    months = [m.strip() for m in args.months.split(",")]
    n, length = args.n, args.length

    # HKDF implementation must pass the RFC 5869 vector before anything else.
    selftest = proto.hkdf_selftest()
    print(f"HKDF self-test: {selftest}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    salt = proto.load_or_create_salt(str(OUT_DIR / "salt.bin"))
    salt_sha = hashlib.sha256(salt).hexdigest()
    print(f"salt: {len(salt)} bytes (sha256 {salt_sha[:16]}...)  "
          f"-> data/processed/prototype/salt.bin")

    config = {
        "generated_utc": _utc_now(),
        "charset": proto.CHARSET,
        "charset_size": proto.CHARSET_SIZE,
        "max_valid": proto.MAX_VALID,
        "acceptance_rate": round(proto.MAX_VALID / 256, 4),
        "ikm_bytes_per_password": proto.IKM_BYTES,
        "info_base": proto.INFO_BASE.decode(),
        "expand_len": proto.EXPAND_LEN,
        "password_length": length,
        "hash": "SHA-256",
        "hkdf": "RFC 5869 (HMAC-SHA256), Extract-then-Expand, per-password Extract",
        "hkdf_selftest": selftest,
        "salt_path": "data/processed/prototype/salt.bin",
        "salt_sha256": salt_sha,
        "fusion_n": fusion_n,
        "months": months,
        "n_passwords_per_cell": n,
    }
    with open(OUT_DIR / "config.json", "w") as fh:
        json.dump(config, fh, indent=2)

    totals = Counter()

    # ---- market group: disjoint IKM blocks of the Exp 4 fused streams --------
    print("\n[market] n in", fusion_n)
    for fn in fusion_n:
        for month in months:
            bin_path = VALIDATION_DIR / f"n{fn}" / month / "fused_stream.bin"
            if not bin_path.exists():
                print(f"  n{fn} {month}: MISSING fused_stream.bin -- skipped")
                continue
            ikm_bytes = proto.load_ikm_bytes(bin_path)
            try:
                pairs = proto.generate_market_cell(ikm_bytes, salt, n, length)
            except proto.InsufficientIKM as exc:
                print(f"  n{fn} {month}: insufficient_ikm ({exc}) -- skipped")
                continue
            cell_dir = OUT_DIR / "market" / f"n{fn}" / month
            _write_cell(cell_dir, pairs, {
                "group": "market",
                "n": fn,
                "month": month,
                "n_passwords": n,
                "length": length,
                "ikm_source": str(bin_path.relative_to(REPO)),
                "ikm_bytes_available": len(ikm_bytes),
                "ikm_bytes_used": n * proto.IKM_BYTES,
            })
            totals["market"] += n
            print(f"  n{fn} {month}: {n} passwords  "
                  f"(IKM {n * proto.IKM_BYTES}/{len(ikm_bytes)} bytes)")

    # ---- baseline B1: salt-seeded uniform charset sampling, no HKDF ----------
    print("\n[baseline B1] salt-seeded uniform charset sampling (no HKDF)")
    for month in months:
        pairs = proto.generate_b1_cell(salt, month, n, length)
        _write_cell(OUT_DIR / "baseline_b1" / month, pairs, {
            "group": "baseline_b1",
            "n": None,
            "month": month,
            "n_passwords": n,
            "length": length,
            "method": "salt-seeded uniform charset sampling (no HKDF)",
        })
        totals["baseline_b1"] += n
        print(f"  {month}: {n} passwords")

    # ---- baseline B2: salt-seeded random IKM through the HKDF pipeline ------
    print("\n[baseline B2] salt-seeded random IKM -> HKDF pipeline")
    for month in months:
        pairs = proto.generate_b2_cell(salt, month, n, length)
        _write_cell(OUT_DIR / "baseline_b2" / month, pairs, {
            "group": "baseline_b2",
            "n": None,
            "month": month,
            "n_passwords": n,
            "length": length,
            "method": "salt-seeded random IKM through HKDF-Extract/Expand + charset",
        })
        totals["baseline_b2"] += n
        print(f"  {month}: {n} passwords")

    grand = sum(totals.values())
    print(f"\nDone. market={totals['market']}  "
          f"B1={totals['baseline_b1']}  B2={totals['baseline_b2']}  "
          f"total={grand} passwords")
    print(f"Output: {OUT_DIR.relative_to(REPO)}/")


if __name__ == "__main__":
    main()
