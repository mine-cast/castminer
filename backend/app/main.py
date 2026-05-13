"""CastMiner claim signer backend.

Signs claim authorizations for the CastMiner ERC-20 contract on Base. The
deployer / claimSigner private key is loaded from the CASTMINER_DEPLOYER_PK
environment variable and never returned in any response.

Contract: 0x41909655593e331151cae645f132e28d531f28b2 (Base mainnet)
Function: claim(uint256 amount, bytes32 nonce, bytes signature)

The exact keccak preimage was determined empirically by eth_call probing
the contract on Base mainnet — the contract uses:

    keccak256(abi.encodePacked(claimer, amount, nonce, block.chainid))

wrapped in the EIP-191 personal_sign envelope ("\x19Ethereum Signed Message:\n32"
+ hash). The other formats below are kept as fallback variants in case the
contract is ever upgraded.

Supported formats:
  - "packed_msg_amount_nonce_chainid":  keccak(msg.sender, amount, nonce, chainid)  ← confirmed working
  - "packed_msg_amount_nonce":          keccak(msg.sender, amount, nonce)
  - "packed_msg_amount_nonce_contract": keccak(msg.sender, amount, nonce, address(this))
  - "packed_contract_msg_amount_nonce": keccak(address(this), msg.sender, amount, nonce)
  - "encode_msg_amount_nonce":          keccak(abi.encode(msg.sender, amount, nonce))
  - "encode_msg_amount_nonce_chainid":  keccak(abi.encode(msg.sender, amount, nonce, chainid))
"""

from __future__ import annotations

import os
import secrets as pysecrets
import time
from collections import defaultdict, deque
from typing import Annotated, Literal

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import is_checksum_address, to_bytes, to_checksum_address, to_hex
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# ----------------------------- Configuration ------------------------------- #

CAST_CONTRACT = to_checksum_address("0x41909655593e331151cae645f132e28d531f28b2")
CAST_DECIMALS = 18
CAST_CHAIN_ID = int(os.environ.get("CAST_CHAIN_ID", "8453"))  # Base mainnet

DEPLOYER_PK = os.environ.get("CASTMINER_DEPLOYER_PK", "").strip()
if DEPLOYER_PK and not DEPLOYER_PK.startswith("0x"):
    DEPLOYER_PK = "0x" + DEPLOYER_PK

SIGNER_ACCOUNT = Account.from_key(DEPLOYER_PK) if DEPLOYER_PK else None
SIGNER_ADDRESS = SIGNER_ACCOUNT.address if SIGNER_ACCOUNT else None

CLAIM_HASH_FORMAT = os.environ.get(
    "CLAIM_HASH_FORMAT", "packed_msg_amount_nonce_chainid"
).strip()
CLAIM_ENVELOPE = os.environ.get("CLAIM_ENVELOPE", "eip191").strip()

# Rate-limits — tuned for an MVP, NOT a hardened production deployment.
# Anyone who can hit this endpoint can claim up to MAX_CAST_PER_REQUEST tokens
# (subject to per-address daily cap). The right long-term fix is to verify a
# Farcaster auth signature from the frontend before signing.
MAX_CAST_PER_REQUEST = float(os.environ.get("MAX_CAST_PER_REQUEST", "5"))
MAX_CAST_PER_ADDRESS_PER_DAY = float(
    os.environ.get("MAX_CAST_PER_ADDRESS_PER_DAY", "100")
)
MIN_SECONDS_BETWEEN_CLAIMS = int(os.environ.get("MIN_SECONDS_BETWEEN_CLAIMS", "30"))

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://castminer-dyydywlt.devinapps.com,http://localhost:8765",
    ).split(",")
    if o.strip()
]

# In-memory rate-limit state. Resets on every container restart; for a single
# replica MVP that is acceptable. Swap for Redis when scaling beyond one box.
_last_claim_at: dict[str, float] = {}
_daily_total: dict[str, list[tuple[float, float]]] = defaultdict(list)


# --------------------------------- Models ---------------------------------- #


HashFormat = Literal[
    "packed_msg_amount_nonce_chainid",
    "packed_msg_amount_nonce",
    "packed_msg_amount_nonce_contract",
    "packed_contract_msg_amount_nonce",
    "encode_msg_amount_nonce",
    "encode_msg_amount_nonce_chainid",
]
EnvelopeKind = Literal["eip191", "raw"]


class SignClaimRequest(BaseModel):
    address: str = Field(
        ..., description="Recipient address (the EOA that will call claim())."
    )
    amount: float = Field(
        ...,
        gt=0,
        description="Token amount to authorize, in CAST (will be scaled by 1e18).",
    )
    format: HashFormat | None = Field(
        default=None,
        description=(
            "Override the keccak preimage layout. Leave unset to use the "
            "server default (CLAIM_HASH_FORMAT env var)."
        ),
    )
    envelope: EnvelopeKind | None = Field(
        default=None,
        description=(
            "Override the message envelope. 'eip191' wraps the digest with "
            "\"\\x19Ethereum Signed Message:\\n32\" before signing. 'raw' "
            "signs the keccak digest directly."
        ),
    )

    @field_validator("address")
    @classmethod
    def _validate_address(cls, v: str) -> str:
        if not isinstance(v, str) or len(v) != 42 or not v.startswith("0x"):
            raise ValueError("address must be a 0x-prefixed 20-byte hex string")
        try:
            return to_checksum_address(v)
        except Exception as exc:
            raise ValueError("invalid address") from exc


class SignClaimResponse(BaseModel):
    claimer: str
    contract: str = CAST_CONTRACT
    amount_wei: str
    amount_cast: float
    nonce: str
    signature: str
    signer: str
    hash_format: str
    envelope: str
    valid_until_epoch: int
    # All four format/envelope variants for the same (address, amount, nonce).
    # The frontend can try each one against on-chain claim() if the default
    # reverts, without round-tripping back to the signer.
    variants: dict[str, str]


class HealthResponse(BaseModel):
    ok: bool
    signer_loaded: bool
    signer_address: str | None
    contract: str
    hash_format: str
    limits: dict[str, float | int]


# -------------------------------- FastAPI ---------------------------------- #

app = FastAPI(
    title="CastMiner Claim Signer",
    version="0.1.0",
    description=(
        "Signs claim authorizations for the CastMiner ERC-20 contract on Base. "
        "Private key lives only in this process — never leaves and is never "
        "returned in responses."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ------------------------------- Endpoints --------------------------------- #


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(
        ok=True,
        signer_loaded=SIGNER_ACCOUNT is not None,
        signer_address=SIGNER_ADDRESS,
        contract=CAST_CONTRACT,
        hash_format=CLAIM_HASH_FORMAT,
        limits={
            "max_cast_per_request": MAX_CAST_PER_REQUEST,
            "max_cast_per_address_per_day": MAX_CAST_PER_ADDRESS_PER_DAY,
            "min_seconds_between_claims": MIN_SECONDS_BETWEEN_CLAIMS,
        },
    )


@app.post("/sign-claim", response_model=SignClaimResponse)
def sign_claim(body: SignClaimRequest) -> SignClaimResponse:
    if SIGNER_ACCOUNT is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signer not configured on the server (CASTMINER_DEPLOYER_PK missing).",
        )

    if body.amount > MAX_CAST_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"amount exceeds per-request cap ({MAX_CAST_PER_REQUEST} CAST).",
        )

    addr = body.address
    now = time.time()
    _enforce_rate_limit(addr, body.amount, now)

    amount_wei = int(body.amount * (10**CAST_DECIMALS))
    nonce = pysecrets.token_bytes(32)

    selected_format = body.format or CLAIM_HASH_FORMAT
    selected_envelope = body.envelope or CLAIM_ENVELOPE
    signature_hex = _sign_for_variant(
        addr, amount_wei, nonce, selected_format, selected_envelope
    )

    # Pre-compute every (format, envelope) combination so the frontend can try
    # alternates without another round trip if the default reverts on-chain.
    variants: dict[str, str] = {}
    for fmt in (
        "packed_msg_amount_nonce_chainid",
        "packed_msg_amount_nonce",
        "packed_msg_amount_nonce_contract",
        "packed_contract_msg_amount_nonce",
        "encode_msg_amount_nonce",
        "encode_msg_amount_nonce_chainid",
    ):
        for env in ("eip191", "raw"):
            key = f"{fmt}__{env}"
            variants[key] = _sign_for_variant(addr, amount_wei, nonce, fmt, env)

    _record_claim(addr, body.amount, now)

    return SignClaimResponse(
        claimer=addr,
        amount_wei=str(amount_wei),
        amount_cast=body.amount,
        nonce=to_hex(nonce),
        signature=signature_hex,
        signer=SIGNER_ACCOUNT.address,
        hash_format=selected_format,
        envelope=selected_envelope,
        valid_until_epoch=int(now) + 600,
        variants=variants,
    )


# ------------------------------- Helpers ----------------------------------- #


def _build_claim_digest(
    claimer: str, amount_wei: int, nonce: bytes, fmt: str | None = None
) -> bytes:
    from eth_utils import keccak

    addr_bytes = to_bytes(hexstr=claimer)  # 20 bytes
    amount_bytes = amount_wei.to_bytes(32, "big")  # uint256
    contract_bytes = to_bytes(hexstr=CAST_CONTRACT)  # 20 bytes
    chainid_bytes = CAST_CHAIN_ID.to_bytes(32, "big")

    fmt = fmt or CLAIM_HASH_FORMAT
    if fmt == "packed_msg_amount_nonce_chainid":
        # Confirmed working layout for 0x4190...28b2 on Base mainnet.
        preimage = addr_bytes + amount_bytes + nonce + chainid_bytes
    elif fmt == "packed_msg_amount_nonce":
        preimage = addr_bytes + amount_bytes + nonce
    elif fmt == "packed_msg_amount_nonce_contract":
        preimage = addr_bytes + amount_bytes + nonce + contract_bytes
    elif fmt == "packed_contract_msg_amount_nonce":
        preimage = contract_bytes + addr_bytes + amount_bytes + nonce
    elif fmt == "encode_msg_amount_nonce":
        # abi.encode pads addresses to 32 bytes
        preimage = (
            b"\x00" * 12
            + addr_bytes
            + amount_bytes
            + nonce
        )
    elif fmt == "encode_msg_amount_nonce_chainid":
        preimage = (
            b"\x00" * 12
            + addr_bytes
            + amount_bytes
            + nonce
            + chainid_bytes
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown hash format: {fmt}",
        )
    return keccak(preimage)


def _sign_for_variant(
    claimer: str,
    amount_wei: int,
    nonce: bytes,
    fmt: str,
    envelope: str,
) -> str:
    assert SIGNER_ACCOUNT is not None
    digest = _build_claim_digest(claimer, amount_wei, nonce, fmt)
    if envelope == "eip191":
        msg = encode_defunct(primitive=digest)
        signed = SIGNER_ACCOUNT.sign_message(msg)
    elif envelope == "raw":
        # Sign the raw 32-byte digest directly (no "\x19..." prefix). Some
        # contracts use this pattern instead of personal_sign.
        signed = SIGNER_ACCOUNT.unsafe_sign_hash(digest)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown envelope: {envelope}",
        )
    sig = signed.signature.hex()
    return sig if sig.startswith("0x") else "0x" + sig


def _enforce_rate_limit(addr: str, amount_cast: float, now: float) -> None:
    last = _last_claim_at.get(addr, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_CLAIMS:
        wait = int(MIN_SECONDS_BETWEEN_CLAIMS - (now - last))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Slow down — try again in {wait}s.",
        )

    window_start = now - 24 * 3600
    history = [(t, a) for (t, a) in _daily_total.get(addr, []) if t >= window_start]
    _daily_total[addr] = history
    total = sum(a for _, a in history)
    if total + amount_cast > MAX_CAST_PER_ADDRESS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily cap reached for this address "
                f"(used {total:.4f} of {MAX_CAST_PER_ADDRESS_PER_DAY} CAST/day)."
            ),
        )


def _record_claim(addr: str, amount_cast: float, now: float) -> None:
    _last_claim_at[addr] = now
    _daily_total[addr].append((now, amount_cast))
