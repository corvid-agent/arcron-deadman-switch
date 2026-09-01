"""Contract / artifact selection for LocalNet recreate + listen scripts.

Static checks only: no algod, no mnemonic, no network calls.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEADMAN_SPEC = json.loads(
    (ROOT / "smart_contracts" / "artifacts" / "deadman" / "Deadman.arc56.json").read_text()
)
MOCK_SPEC = json.loads(
    (ROOT / "smart_contracts" / "artifacts" / "mock_keeper" / "MockKeeper.arc56.json").read_text()
)


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def recreate():
    return _load_script("localnet_recreate.py")


@pytest.fixture(scope="module")
def listen():
    return _load_script("localnet_listen.py")


def test_recreate_selects_deadman_not_mock_keeper(recreate) -> None:
    assert recreate.CONTRACT_NAME == "Deadman"
    assert recreate.CONTRACT.name == "contract.py"
    assert "deadman" in str(recreate.CONTRACT).replace("\\", "/")
    assert "deadman" in str(recreate.ARTIFACT_DIR).replace("\\", "/")
    assert "mock_keeper" not in str(recreate.CONTRACT).replace("\\", "/")
    assert recreate.OUT.name == "localnet.json"
    assert recreate.OUT.parent.name == "docs"


def test_listen_selects_mock_keeper_for_inner_check(listen) -> None:
    assert "mock_keeper" in str(listen.MOCK_SRC).replace("\\", "/")
    assert "mock_keeper" in str(listen.MOCK_ARTIFACT_DIR).replace("\\", "/")
    assert listen.LISTEN_JSON.name == "listen.json"
    assert listen.LOCALNET_JSON.name == "localnet.json"
    # Deadman app id comes from localnet.json, not a hardcoded TestNet id.
    assert "769891898" not in (ROOT / "scripts" / "localnet_listen.py").read_text()


def test_deadman_arc56_methods_match_script_create_selector(recreate) -> None:
    names = [m["name"] for m in DEADMAN_SPEC["methods"]]
    assert names == ["create", "configure", "set_keeper", "poke", "check", "claim"]
    assert DEADMAN_SPEC["name"] == "Deadman"
    assert recreate.CREATE.get_signature() == "create()void"


def test_listen_method_signatures_match_deadman_and_mock(listen) -> None:
    deadman_by_name = {m["name"]: m for m in DEADMAN_SPEC["methods"]}
    assert listen.POKE.get_signature() == "poke()uint64"
    assert listen.CLAIM.get_signature() == "claim()uint64"
    assert listen.CONFIGURE.get_signature() == "configure(uint64)void"
    # Resource-encoding value: Application becomes uint64 in the ABI call.
    assert listen.SET_KEEPER.get_signature() == "set_keeper(uint64,pay)void"
    assert "set_keeper" in deadman_by_name
    assert "check" in deadman_by_name
    # MockKeeper.check(Application) → check(uint64)void under value encoding.
    mk_names = [m["name"] for m in MOCK_SPEC["methods"]]
    assert mk_names == ["check"]
    assert MOCK_SPEC["name"] == "MockKeeper"
    assert listen.MK_CHECK.get_signature() == "check(uint64)void"


def test_refuse_wrong_network_blocks_testnet_and_mainnet(recreate, listen) -> None:
    for mod in (recreate, listen):
        with pytest.raises(SystemExit) as ei:
            mod.refuse_wrong_network("testnet-v1.0")
        assert "TestNet" in str(ei.value)
        with pytest.raises(SystemExit) as ei:
            mod.refuse_wrong_network("mainnet-v1.0")
        assert "MainNet" in str(ei.value)
        # LocalNet / dockernet must be allowed (no exit).
        mod.refuse_wrong_network("dockernet-v1")
        mod.refuse_wrong_network("devnet-v1")


def test_scripts_never_target_testnet_bank_address(recreate, listen) -> None:
    """Bank constant may be named only to refuse spending it — never as signer."""
    bank = "IFZZOTEBLLAV7DA4WP7IPZWZW67KXB5ZNYLZAWJ2S6M3KKNAX55BRXVK2Y"
    recreate_src = (ROOT / "scripts" / "localnet_recreate.py").read_text()
    listen_src = (ROOT / "scripts" / "localnet_listen.py").read_text()
    assert bank not in recreate_src
    assert getattr(listen, "BANK", None) == bank
    # Listen must not use BANK as the signing address path.
    assert "funded_account" in listen_src
    assert "addr == BANK" in listen_src or "if addr == BANK" in listen_src
