# CastMiner Claim Signer

FastAPI service that signs claim authorizations for the CastMiner ERC-20
contract on Base (`0x41909655593e331151cae645f132e28d531f28b2`). The deployer
/ `claimSigner` private key lives only in this process (via the
`CASTMINER_DEPLOYER_PK` env var) — it never leaves and is never returned in
any response.

## Endpoints

### `GET /healthz`

Returns the signer's public address (derived from the PK), the configured
contract, default hash format/envelope, and rate-limit settings.

### `POST /sign-claim`

Body: `{ "address": "0x...", "amount": 1.5 }` (amount in CAST tokens).

Returns the canonical signature plus all 8 `(format, envelope)` variants so the
frontend can iterate on-chain without round-tripping back to this service.

```json
{
  "claimer": "0x...",
  "contract": "0x4190...f28b2",
  "amount_wei": "1500000000000000000",
  "amount_cast": 1.5,
  "nonce": "0x...",
  "signature": "0x...",
  "signer": "0x000000000...284e6",
  "hash_format": "packed_msg_amount_nonce",
  "envelope": "eip191",
  "valid_until_epoch": 1778695022,
  "variants": {
    "packed_msg_amount_nonce__eip191": "0x...",
    "packed_msg_amount_nonce__raw": "0x...",
    "packed_msg_amount_nonce_contract__eip191": "0x...",
    ...
  }
}
```

## Configuration

| Env var | Default | Notes |
| --- | --- | --- |
| `CASTMINER_DEPLOYER_PK` | _required_ | Hex private key, with or without `0x` |
| `CLAIM_HASH_FORMAT` | `packed_msg_amount_nonce` | One of the 4 supported preimage layouts |
| `CLAIM_ENVELOPE` | `eip191` | `eip191` (personal_sign) or `raw` |
| `MAX_CAST_PER_REQUEST` | `5` | Per-call cap, in CAST |
| `MAX_CAST_PER_ADDRESS_PER_DAY` | `100` | Rolling 24h cap, in CAST |
| `MIN_SECONDS_BETWEEN_CLAIMS` | `30` | Throttle between claims by the same address |
| `ALLOWED_ORIGINS` | `https://castminer-dyydywlt.devinapps.com,http://localhost:8765` | Comma-separated CORS allowlist |

## Local development

```bash
poetry install
export CASTMINER_DEPLOYER_PK=0xabc...
poetry run uvicorn app.main:app --reload --port 8001
```
