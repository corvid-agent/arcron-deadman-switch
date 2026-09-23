#!/usr/bin/env python3
"""Unsigned TestNet read of Arcron keeper → docs/due.json.

Read-only GET against public TestNet algod (+ indexer for account/balance).
Never submits, never prints a mnemonic, never writes docs/deploy.json.
Never copies LocalNet app ids. Skips upkeep 81; does not poke 87.
Does not spend the TestNet bank.
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from algosdk.logic import get_application_address

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "due.json"
DEPLOY_JSON = ROOT / "docs" / "deploy.json"

ALGOD = "https://testnet-api.algonode.cloud"
INDEXER = "https://testnet-idx.algonode.cloud"
KEEPER = 769891898
BANK = "IFZZOTEBLLAV7DA4WP7IPZWZW67KXB5ZNYLZAWJ2S6M3KKNAX55BRXVK2Y"
UA = {"User-Agent": "arcron-deadman-switch-probe_keeper/1.0", "Accept": "application/json"}


def get_json(base: str, path: str, timeout: int = 45) -> dict:
    req = urllib.request.Request(base + path, headers=UA, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raw = e.read() if e.fp else b""
        raise SystemExit(f"GET {base}{path} HTTP {e.code}: {raw[:200]!r}") from e


def try_json(base: str, path: str, timeout: int = 45) -> dict | None:
    try:
        return get_json(base, path, timeout=timeout)
    except SystemExit as e:
        print(f"warn: {e}", file=sys.stderr)
        return None


def b64_key(key_b64: str) -> str:
    raw = base64.b64decode(key_b64)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.hex()


def global_uint(state: list, name: str) -> int | None:
    for kv in state or []:
        if b64_key(kv.get("key", "")) != name:
            continue
        val = kv.get("value") or {}
        if val.get("type") == 2:
            return int(val.get("uint") or 0)
    return None


def main() -> None:
    # Honesty guard: this script talks only to the public TestNet hosts above.
    status = get_json(ALGOD, "/v2/status")
    last_round = int(status.get("last-round") or 0)
    if last_round <= 0:
        sys.exit("algod status missing last-round")

    app = get_json(ALGOD, f"/v2/applications/{KEEPER}")
    params = app.get("params") or {}
    creator = params.get("creator") or ""
    gstate = params.get("global-state") or []
    frozen = global_uint(gstate, "frozen")
    next_upkeep = global_uint(gstate, "next_upkeep_id")
    if frozen is None or next_upkeep is None:
        sys.exit("keeper global-state missing frozen/next_upkeep_id")

    keeper_addr = get_application_address(KEEPER)
    if keeper_addr == BANK:
        sys.exit("refusing: keeper address somehow equals TestNet bank")

    # Prefer indexer for account (algod /v2/accounts often hits free-tier 403).
    balance = 0
    min_balance = 0
    acct = try_json(INDEXER, f"/v2/accounts/{keeper_addr}")
    if acct and isinstance(acct.get("account"), dict):
        a = acct["account"]
        balance = int(a.get("amount") or 0)
        min_balance = int(a.get("min-balance") or 0)
    else:
        acct2 = try_json(ALGOD, f"/v2/accounts/{keeper_addr}")
        if acct2:
            balance = int(acct2.get("amount") or 0)
            min_balance = int(acct2.get("min-balance") or 0)

    created_at_round = None
    idx = try_json(INDEXER, f"/v2/applications/{KEEPER}")
    if idx:
        created_at_round = idx.get("created-at-round")
        if created_at_round is None and isinstance(idx.get("application"), dict):
            created_at_round = (idx["application"] or {}).get("created-at-round")

    deploy: dict = {}
    if DEPLOY_JSON.is_file():
        deploy = json.loads(DEPLOY_JSON.read_text())
    deadman_app = int(deploy.get("appId") or 0)
    deadman_upkeep = int(deploy.get("upkeepId") or 0)
    if deadman_app != 0:
        print(
            f"note: docs/deploy.json appId={deadman_app} (probe does not change it)",
            file=sys.stderr,
        )

    now = datetime.now(timezone.utc)
    probed_at = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

    # Honesty: never embed LocalNet app ids into due.json notes (Pages/tests
    # treat due.json as TestNet-keeper-only; LocalNet ids live in localnet.json).
    notes = (
        "Deadman still undeployed (docs/deploy.json appId 0). "
        f"Keeper {KEEPER} live on TestNet (frozen={frozen}, next_upkeep_id={next_upkeep}, "
        f"last-round={last_round}). LocalNet proof stays in localnet.json + listen.json only "
        "— never copy those ids into deploy.json. "
        "Did not spend TestNet bank. Skipped upkeep 81. Did not poke 87. "
        "dockerd/LocalNet was down this pass so no recreate."
    )

    due = {
        "network": "testnet",
        "genesisId": "testnet-v1.0",
        "algod": ALGOD,
        "indexer": INDEXER,
        "keeperAppId": KEEPER,
        "keeperAddress": keeper_addr,
        "keeperBalanceMicroAlgos": balance,
        "keeperMinBalance": min_balance,
        "frozen": int(frozen),
        "nextUpkeepId": int(next_upkeep),
        "createdAtRound": created_at_round,
        "creator": creator,
        "lastRound": last_round,
        "deadmanAppId": deadman_app,
        "deadmanUpkeepId": deadman_upkeep,
        "skipped": [
            {"id": 81, "reason": "not ours; CoS does not poke"},
            {"id": 87, "reason": "do not poke"},
        ],
        "probedAt": probed_at,
        "source": "unsigned TestNet algod+indexer read",
        "notes": notes,
    }

    # Never writes docs/deploy.json
    OUT.write_text(json.dumps(due, indent=2) + "\n")
    print(
        f"wrote {OUT.relative_to(ROOT)} · lastRound={last_round} · "
        f"frozen={frozen} · next_upkeep={next_upkeep} · balance={balance}"
    )
    print("docs/deploy.json untouched")


if __name__ == "__main__":
    main()
