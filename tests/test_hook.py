"""Static checks that the deadman hook rules hold. No TestNet, no mnemonic."""

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "smart_contracts" / "deadman" / "contract.py").read_text()
README = (ROOT / "README.md").read_text()
DEPLOY = json.loads((ROOT / "docs" / "deploy.json").read_text())
INDEX = (ROOT / "docs" / "index.html").read_text()
APP_JS = (ROOT / "docs" / "app.js").read_text()
LICENSE = (ROOT / "LICENSE").read_text()


def _method(name: str) -> str:
    """Return source from `def name(` through the next top-level method or EOF."""
    start = SRC.index(f"def {name}(")
    nxt = []
    for other in ("create", "configure", "set_keeper", "poke", "check", "claim"):
        if other == name:
            continue
        needle = f"def {other}("
        pos = SRC.find(needle, start + 1)
        if pos != -1:
            nxt.append(pos)
    end = min(nxt) if nxt else len(SRC)
    return SRC[start:end]


def test_create_takes_zero_args() -> None:
    assert "def create(self) -> None:" in SRC
    assert "def create(self, " not in SRC


def test_set_keeper_takes_application_and_payment() -> None:
    body = _method("set_keeper")
    assert "def set_keeper(self, keeper: Application, payment: gtxn.PaymentTransaction) -> None:" in body
    assert "payment.amount >= APP_BASE_MBR" in body
    assert "APP_BASE_MBR = 100_000" in SRC
    assert "self.keeper_app.value = keeper.id" in body


def test_poke_is_the_check_in_pull() -> None:
    body = _method("poke")
    assert "def poke(self) -> UInt64:" in body
    assert "self.last_poke_round.value = Global.round" in body
    assert "Txn.sender == Global.creator_address" in body
    assert "itxn." not in body


def test_check_is_zero_arg_uint64() -> None:
    assert "def check(self) -> UInt64:" in SRC
    assert "def check(self, " not in SRC


def test_check_has_no_inner_pay() -> None:
    """Fail-soft hook. Inner-paying the whole balance is the total-loss class."""
    body = _method("check")
    assert "itxn." not in body
    assert "Payment" not in body


def test_check_fail_soft_when_not_overdue() -> None:
    body = _method("check")
    assert "return UInt64(0)" in body
    assert "if Global.round <= last + timeout:" in body
    assert 'assert Global.round > last' not in body
    assert "Already overdue" not in body


def test_check_auth_is_application_address_not_itob() -> None:
    body = _method("check")
    assert "Application(self.keeper_app.value).address" in body
    # Module docstring may name the itob trap. Methods must not use it.
    for name in ("create", "configure", "set_keeper", "poke", "check", "claim"):
        assert "itob(" not in _method(name)


def test_keeper_id_is_not_hardcoded_in_the_contract() -> None:
    # Module docstring may name the 68-year trap. Methods must not bake the id in.
    for name in ("create", "configure", "set_keeper", "poke", "check", "claim"):
        assert "769891898" not in _method(name)


def test_claim_pays_only_surplus_above_mbr() -> None:
    body = _method("claim")
    assert "def claim(self) -> UInt64:" in body
    assert "payable: UInt64 = balance - APP_BASE_MBR" in body
    assert "itxn.Payment(receiver=Txn.sender, amount=payable, fee=0).submit()" in body
    assert "amount=balance" not in body
    assert "if balance <= APP_BASE_MBR:" in body
    assert "return UInt64(0)" in body


def test_readme_honesty_not_deployed() -> None:
    lower = README.lower()
    assert "not deployed" in lower
    assert "unaudited" in lower
    assert "testnet only" in lower
    assert "appid" in lower.replace(" ", "").replace("`", "").replace(":", "").replace("_", "") or "app id" in lower
    assert "do not invent" in lower or "never invent" in lower
    assert "apache-2.0" in lower or "Apache-2.0" in README


def test_readme_skips_upkeep_81() -> None:
    """Upkeep 81 on keeper 769891898 is not ours."""
    assert re.search(r"upkeep\s+\*\*81\*\*|upkeep 81|skip 81", README, re.I)


def test_readme_names_skip_ahead_not_catch_up() -> None:
    assert "SKIP_AHEAD" in README
    assert "CATCH_UP" in README


def test_deploy_json_is_not_deployed() -> None:
    assert DEPLOY["appId"] == 0
    assert DEPLOY["upkeepId"] == 0
    assert DEPLOY["network"] == "testnet"
    assert "not deployed" in str(DEPLOY.get("notes", "")).lower()


def test_crt_board_defaults_to_not_deployed() -> None:
    assert "NOT DEPLOYED" in INDEX
    assert 'paint("NOT DEPLOYED"' in APP_JS
    assert "appId <= 0" in APP_JS


def test_license_is_apache_2() -> None:
    assert "Apache License" in LICENSE
    assert "Version 2.0" in LICENSE


def test_readme_has_no_fake_txid() -> None:
    """Do not invent a 52–64 char base32/hex txid in the honesty table."""
    for line in README.splitlines():
        if "not done" in line.lower() or "not deployed" in line.lower():
            continue
        assert not re.search(r"\b[A-Z2-7]{52}\b", line)
        assert not re.search(r"\b[a-f0-9]{64}\b", line)
