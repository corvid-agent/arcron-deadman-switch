# arcron-deadman-switch

TestNet deadman switch for Arcron: `poke` (check-in) or the keeper's `check`
trips the switch and `claim` releases escrow. **Unaudited. Not a product.
Not deployed.**

This is a first-party demo of the **MBR bug class**, not a vault.

## The MBR bug class

An Algorand app account must hold **100_000 µALGO**. A scheduled hook that
inner-pays its *entire* balance on trip fails that inner pay, `execute`
rejects, and the keeper backs the upkeep off. The switch never trips, the
escrow never moves, and the schedule goes quiet.

So this contract splits the work:

| method | who | what it does |
|---|---|---|
| `check()uint64` | Arcron keeper app account | trips a flag if overdue. **No inner pay.** Fail-soft if not overdue. |
| `claim()uint64` | anyone, after trip | inner-pays **only** `balance - 100_000` to `Txn.sender` |

`check` authorizes `Application(keeper).address` — the inner-call sender when
Arcron `execute()` inner-calls this app — **never** `itob(keeper.id)`.

## Live proof

**not done.** `docs/deploy.json` has `appId: 0`. No TestNet create, no upkeep,
no execute, no claim. Ids stay zero. Do not invent an app id.

| item | value |
|---|---|
| app id | **not done** |
| upkeep on keeper `769891898` | **not done** |
| execute txid | **not done** |
| claim txid | **not done** |
| Pages | https://corvid-agent.github.io/arcron-deadman-switch/ |

The CRT board reads `docs/deploy.json`. With `appId` 0 it shows **NOT DEPLOYED**.
After a real create it should show **ALIVE** or **TRIPPED** from global state.

## How a human deploys later

No mnemonic belongs in this repo, in a workflow, or in `docs/deploy.json`.
The creator of record deploys from a machine that already has the account,
when that account has a TestNet bank.

Sketch, AlgoKit / Puya, TestNet only:

```bash
# compile
algokit compile python smart_contracts/deadman/contract.py

# create with ZERO args — do not pass 769891898, a timeout, or anything else
# sign with a key that lives in the OS keychain / AlgoKit wallet / env var
# that is NOT committed.

# then, still as creator:
#   configure(timeout_rounds)          # round count, not wall-clock; once
#   set_keeper(Application(769891898), pay >= 100_000 to the app address)
# poke() to check in
# register check()uint64 on Arcron 769891898 (interval chosen at register)
# after a trip: claim() with extra_fee covering the inner pay
# write the resulting app id into docs/deploy.json (appId, still "testnet")
```

Use the TestNet dispenser for fees. Extra escrow above MBR is a payment to the
app address. `claim` leaves 100_000 µALGO in the account.

## Layout

```
smart_contracts/deadman/contract.py   ARC-4 target
docs/index.html                       CRT board (ALIVE / TRIPPED / NOT DEPLOYED)
docs/style.css                        phosphor, flaps
docs/deploy.json                      {"appId":0,...}  flip the number after deploy
.github/workflows/pages.yml           publishes docs/ from main
LICENSE                               Apache-2.0
```

## Honesty block

Unaudited. TestNet only. First-party demo. Not the [Arcron console](https://corvidlabs.xyz/arcron/console/).
Do not send MainNet funds. There is no contract on any network until someone
creates it and writes a real app id here.

## License

Apache-2.0. See [LICENSE](LICENSE).
