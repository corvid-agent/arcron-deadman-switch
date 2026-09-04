# arcron-deadman-switch

TestNet deadman switch for Arcron: `poke` (check-in) or the keeper's `check`
trips the switch and `claim` releases escrow. **Unaudited. Not a product.
Not deployed.**

This is a first-party demo of the **MBR bug class**, not a vault. It avoids
the upstream total-loss class: a hook that inner-pays the *entire* app
balance fails because the app account must keep 100_000 µALGO, `execute`
rejects, and the keeper backs the upkeep off.

## The MBR bug class

An Algorand app account must hold **100_000 µALGO**. A scheduled hook that
inner-pays its *entire* balance on trip fails that inner pay, `execute`
rejects, and the keeper backs the upkeep off. The switch never trips, the
escrow never moves, and the schedule goes quiet.

So this contract splits the work:

| method | who | what it does |
|---|---|---|
| `set_keeper(Application, pay>=100_000)` | creator, once | names the keeper app and funds app MBR |
| `poke()uint64` | creator | check-in pull. Sets `last_poke_round = Global.round` |
| `check()uint64` | Arcron keeper app account | trips a flag if overdue. **No inner pay.** Fail-soft if not overdue. |
| `claim()uint64` | anyone, after trip | inner-pays **only** `balance - 100_000` to `Txn.sender` |

`check` authorizes `Application(keeper).address` — the inner-call sender when
Arcron `execute()` inner-calls this app — **never** `itob(keeper.id)`.

## Live proof

**not done.** `docs/deploy.json` has `appId: 0`. No TestNet create, no upkeep,
no execute, no claim. Ids stay zero. Do not invent an app id or a txid.

| item | value |
|---|---|
| app id | **not done** (`docs/deploy.json` appId 0) |
| upkeep on keeper `769891898` | **not done** |
| execute txid | **not done** |
| claim txid | **not done** |
| Pages | https://corvid-agent.github.io/arcron-deadman-switch/ |

**Skip upkeep 81.** Upkeep 81 on keeper 769891898 is not ours. Do not cancel,
retarget, or fund it.

The CRT board reads `docs/deploy.json`. With `appId` 0 it shows **NOT DEPLOYED**.
After a real create it should show **ALIVE** or **TRIPPED** from global state.
When `appId` is 0, the board also footnotes LocalNet recreate/listen proof from
`docs/localnet.json` / `docs/listen.json` (never painted as TestNet).

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
# register check()uint64 on Arcron 769891898 with SKIP_AHEAD (1)
# Do not pass CATCH_UP=0. Cadence is a register field, not a constructor arg.
# Do not touch upkeep 81 (not ours).
# after a trip: claim() with extra_fee covering the inner pay
# write the resulting app id into docs/deploy.json (appId, still "testnet")
```

Use the TestNet dispenser for fees. Extra escrow above MBR is a payment to the
app address. `claim` leaves 100_000 µALGO in the account.



## LocalNet recreate (not TestNet)

Create, `set_keeper(Application(...), pay)`, `configure`, `poke`, a mock-keeper inner-call of `check()`, and `claim()` were proven on AlgoKit LocalNet (`dockernet-v1`). That is **not** TestNet. Do **not** copy any LocalNet app id into `docs/deploy.json` or treat it as TestNet. TestNet `appId` stays 0 until a real TestNet create.

This pass (2026-09-03 ~3:06 PM MT): recreate Deadman **appId 1230** on `dockernet-v1` (confirmed round 183). `python scripts/localnet_listen.py` created mock keeper **1231**, wired `set_keeper` + `configure(1)` + `poke`, inner-called `check` (1 inner → tripped), then `claim` pulled surplus above MBR. Global after listen: keeper_app=1231, timeout_rounds=1, last_poke_round=188, tripped=1. LocalNet last-round after listen: 192. Did not spend the TestNet bank. Did not poke upkeep 81 or 87.

LocalNet ids are ephemeral (DevMode / reset). They are not a product. They are not TestNet explorer links.
LocalNet proof for Pages lives in `docs/localnet.json` and `docs/listen.json` (CRT shows them when present). `docs/history.json` appends LocalNet listen samples for the phosphor escrow / last_poke / tripped graphs (in-page sql.js). `node scripts/append_history.mjs` appends from `listen.json` without touching `deploy.json`. `docs/deploy.json` stays honest TestNet `appId: 0`.

```bash
# Docker daemon required
algokit localnet start
# wait until localhost:4001 /v2/status answers

pip install puyapy py-algorand-sdk
python scripts/localnet_recreate.py
# writes docs/localnet.json with network:"localnet" and the new appId
python scripts/localnet_listen.py
# set_keeper + configure + poke + mock check + claim; writes docs/listen.json
```

Both scripts talk only to `localhost:4001` / `4002`, sign with the LocalNet KMD
`unencrypted-default-wallet` (never print a mnemonic), refuse TestNet/MainNet
genesis ids, and never modify `docs/deploy.json`.

DevMode holds last-round at 0 until the first tx. A successful create is a confirmed
`application-index` on genesis id `dockernet-v1`, not a TestNet explorer link.


## Tests

CI is compile + static hook tests (`tests/test_hook.py`), not a LocalNet
execute and not a TestNet deploy.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
puyapy smart_contracts/deadman/contract.py --out-dir smart_contracts/artifacts/deadman --resource-encoding value
```


## Layout

```
smart_contracts/deadman/contract.py   ARC-4 target
tests/test_hook.py                    static hook / honesty checks
docs/index.html                       CRT board (ALIVE / TRIPPED / NOT DEPLOYED)
docs/style.css                        phosphor, flaps
docs/deploy.json                      {"appId":0,...}  flip after TestNet create
docs/localnet.json                    LocalNet-only proof (network:localnet)
docs/listen.json                      LocalNet mock-keeper check proof
scripts/localnet_recreate.py          create on localhost:4001 → localnet.json
scripts/localnet_listen.py            mock keeper + check() listen → listen.json
smart_contracts/mock_keeper/          LocalNet-only inner-call of check()
.github/workflows/ci.yml              pytest + puyapy
.github/workflows/pages.yml           publishes docs/ from main
LICENSE                               Apache-2.0
```

## What does not work

- No TestNet create, no upkeep, no execute, no claim. appId stays 0.
- CRT stays **NOT DEPLOYED** until someone writes a real app id after a real create.
- Do not invent txids.
- CI does not run LocalNet or talk to TestNet.
- TestNet keeper 769891898 may be late. Interval floor 30 so ordinary lateness is not treated as a signal.
- Upkeep 81 is not ours; skip it.

## Honesty block

Unaudited. TestNet only. First-party demo, not a product. No MainNet path;
this repo will refuse one. Do not send mainnet funds. Keeper 769891898.
Throwaway dispenser. Apache-2.0. Pull pattern: `poke` is the check-in;
`check` only trips a flag (fail-soft, no inner pay); `claim` pulls surplus
above 100_000 MBR. Auth is `Application(keeper).address`, never `itob`.
Skip upkeep 81. There is no contract on any network until someone creates it
and writes a real app id here.

## License

Apache-2.0. See [LICENSE](LICENSE).
