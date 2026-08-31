# pyright: reportMissingModuleSource=false
"""Deadman switch on Algorand TestNet, tripped by Arcron, claimed as a pull.

MBR bug class: a hook that inner-pays the full app balance fails because the
app account must keep 100_000 µALGO. That reject fails `execute`, and the
keeper backs the upkeep off. So `check()` only trips a flag. `claim()` is the
only inner pay, and it sends only the surplus above APP_BASE_MBR.

TestNet only. Unaudited. First-party demo. Not a product. Not deployed.

TRAP: a sloppy deploy that mapped every uint64 onto keeper app 769891898
would freeze a cadence at ~68 years (769891898 rounds × ~2.8 s). `create()`
takes zero arguments. Interval is an Arcron *register* field, not a
constructor arg. Do not compare the inner sender against itob(keeper_app.id)
— that is 8 bytes, not an address. Auth is Application(keeper_app).address.
"""

from algopy import (
    ARC4Contract,
    Application,
    Global,
    GlobalState,
    Txn,
    UInt64,
    gtxn,
    itxn,
)
from algopy.arc4 import abimethod

# Every Algorand account must hold this much. `claim` never sends it.
APP_BASE_MBR = 100_000


class Deadman(ARC4Contract):
    """Poke or the keeper trips the switch. Escrow is a pull above MBR.

    TestNet only. Unaudited. Not a product.
    """

    def __init__(self) -> None:
        self.keeper_app = GlobalState(UInt64(0))
        self.timeout_rounds = GlobalState(UInt64(0))
        self.last_poke_round = GlobalState(UInt64(0))
        self.tripped = GlobalState(UInt64(0))

    @abimethod(create="require")
    def create(self) -> None:
        """No-op create. Zero arguments on purpose.

        A create_arg of type uint64 is how a sloppy deploy script confused the
        keeper app id with a cadence. There is nothing to pass here.
        """
        self.keeper_app.value = UInt64(0)
        self.timeout_rounds.value = UInt64(0)
        self.last_poke_round.value = UInt64(0)
        self.tripped.value = UInt64(0)

    @abimethod()
    def configure(self, timeout_rounds: UInt64) -> None:
        """Set the silence window in rounds. Creator only, once.

        `timeout_rounds` is a round count, not wall-clock. The clock starts
        now: `last_poke_round = Global.round`.
        """
        assert Txn.sender == Global.creator_address, "Only the creator can configure"
        assert self.timeout_rounds.value == 0, "Already configured"
        assert timeout_rounds > 0, "Timeout must be > 0"
        self.timeout_rounds.value = timeout_rounds
        self.last_poke_round.value = Global.round

    @abimethod()
    def set_keeper(self, keeper: Application, payment: gtxn.PaymentTransaction) -> None:
        """Name the Arcron keeper and fund app MBR. Creator only, once.

        Pass the keeper *application*, not a raw uint64. Payment must be
        >= 100_000 µALGO to this app address so the account exists and
        holds MBR. `check` authorizes Application(keeper).address — never itob of keeper.id.
        """
        assert Txn.sender == Global.creator_address, "Only the creator can set the keeper"
        assert self.keeper_app.value == 0, "Keeper already set"
        assert keeper.id != 0, "Keeper app required"
        assert (
            payment.receiver == Global.current_application_address
        ), "Payment must fund the app account"
        assert payment.sender == Txn.sender, "Payment must come from the caller"
        assert payment.amount >= APP_BASE_MBR, "Payment must cover app MBR"
        assert payment.rekey_to == Global.zero_address, "Payment must not rekey"
        assert (
            payment.close_remainder_to == Global.zero_address
        ), "Payment must not close"
        self.keeper_app.value = keeper.id

    @abimethod()
    def poke(self) -> UInt64:
        """Check-in. Creator only. Sets last_poke_round = Global.round.

        Refused after the switch has tripped. The timeout window is measured
        from this round, not from wall-clock.
        """
        assert Txn.sender == Global.creator_address, "Only the creator can poke"
        assert self.tripped.value == 0, "Already tripped"
        assert self.timeout_rounds.value != 0, "Not configured"
        self.last_poke_round.value = Global.round
        last: UInt64 = self.last_poke_round.value
        return last

    @abimethod()
    def check(self) -> UInt64:
        """Arcron hook. Zero extra args; selector is the only app arg.

        Trips if Global.round > last_poke_round + timeout_rounds.
        NO inner payment. Fail-soft: if not overdue, return 0 rather than
        reject — a reject would fail execute and back the schedule off.
        """
        # Inner-call sender is the keeper *app account*, not itob of keeper.id.
        assert (
            Txn.sender == Application(self.keeper_app.value).address
        ), "Only the keeper app may check"
        tripped: UInt64 = self.tripped.value
        if tripped != 0:
            return UInt64(1)
        timeout: UInt64 = self.timeout_rounds.value
        if timeout == 0:
            return UInt64(0)
        last: UInt64 = self.last_poke_round.value
        if Global.round <= last + timeout:
            return UInt64(0)
        self.tripped.value = UInt64(1)
        return UInt64(1)

    @abimethod()
    def claim(self) -> UInt64:
        """Sweep surplus above 100_000 MBR after the switch has tripped.

        The only method that inner-pays. Cover the inner fee with extra_fee
        on the outer call. If nothing is payable, return 0 (do not reject).
        Permissionless: anyone may pull; the surplus goes to Txn.sender.
        """
        assert self.tripped.value != 0, "Not tripped"
        balance: UInt64 = Global.current_application_address.balance
        if balance <= APP_BASE_MBR:
            return UInt64(0)
        payable: UInt64 = balance - APP_BASE_MBR
        itxn.Payment(receiver=Txn.sender, amount=payable, fee=0).submit()
        return payable
