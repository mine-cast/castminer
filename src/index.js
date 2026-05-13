// CastMiner signer Worker
//
// Mounted on the same Cloudflare Worker that serves the static frontend.
// Routes:
//   GET  /api/healthz       -> { signer_address, contract, limits, ... }
//   POST /api/sign-claim    -> { signature, variants, nonce, amount_wei, ... }
// Anything else falls through to the static assets binding.
//
// The deployer / claimSigner private key is loaded from the
// CASTMINER_DEPLOYER_PK secret (set via `wrangler secret put` or the
// Cloudflare dashboard). It NEVER appears in committed code or in any
// response payload.
//
// Verified preimage layout (determined empirically via eth_call probing
// 0x41909655593e331151cae645f132e28d531f28b2 on Base mainnet):
//
//   keccak256(abi.encodePacked(claimer, amount, nonce, block.chainid))
//
// wrapped with the EIP-191 envelope ("\x19Ethereum Signed Message:\n32" + hash).

import { keccak_256 } from '@noble/hashes/sha3';
import { secp256k1 } from '@noble/curves/secp256k1';

// --------- tiny byte helpers (no third-party deps beyond noble) ----------

function hexToBytes(hex) {
  let h = String(hex || '').toLowerCase();
  if (h.startsWith('0x')) h = h.slice(2);
  if (h.length % 2) h = '0' + h;
  const b = new Uint8Array(h.length / 2);
  for (let i = 0; i < b.length; i++) {
    b[i] = parseInt(h.slice(i * 2, i * 2 + 2), 16);
  }
  return b;
}

function bytesToHex(b) {
  let s = '';
  for (const v of b) s += v.toString(16).padStart(2, '0');
  return s;
}

function uint256ToBytes(n) {
  let x = BigInt(n);
  if (x < 0n) throw new Error('uint256ToBytes: negative');
  const b = new Uint8Array(32);
  for (let i = 31; i >= 0; i--) {
    b[i] = Number(x & 0xffn);
    x >>= 8n;
  }
  return b;
}

function concat(...arrs) {
  let len = 0;
  for (const a of arrs) len += a.length;
  const out = new Uint8Array(len);
  let o = 0;
  for (const a of arrs) {
    out.set(a, o);
    o += a.length;
  }
  return out;
}

// --------- crypto primitives ----------

function eip191Wrap(hash32) {
  // "\x19Ethereum Signed Message:\n32" + 32-byte hash, then keccak256 again.
  const prefix = new TextEncoder().encode('\x19Ethereum Signed Message:\n32');
  return keccak_256(concat(prefix, hash32));
}

function ecdsaSign(pkBytes, hash32) {
  // secp256k1.sign returns { r, s, recovery } with low-s normalized by default.
  const sig = secp256k1.sign(hash32, pkBytes);
  const r = uint256ToBytes(sig.r);
  const s = uint256ToBytes(sig.s);
  const v = new Uint8Array([27 + sig.recovery]);
  return concat(r, s, v); // 65 bytes
}

function deriveAddress(pkBytes) {
  // uncompressed pubkey (65 bytes) → drop 0x04 prefix → keccak256 → last 20 bytes
  const pub = secp256k1.getPublicKey(pkBytes, false);
  const hash = keccak_256(pub.slice(1));
  return '0x' + bytesToHex(hash.slice(12, 32));
}

// EIP-55 checksum (so signer_address in /healthz looks normal in clients).
function toChecksumAddress(addrLower) {
  const a = addrLower.replace(/^0x/, '').toLowerCase();
  const hash = bytesToHex(keccak_256(new TextEncoder().encode(a)));
  let out = '0x';
  for (let i = 0; i < a.length; i++) {
    out += parseInt(hash[i], 16) >= 8 ? a[i].toUpperCase() : a[i];
  }
  return out;
}

// --------- claim digest builder ----------

function buildPreimage(fmt, claimerBytes, amountBytes, nonce, chainIdBytes, contractBytes) {
  switch (fmt) {
    case 'packed_msg_amount_nonce_chainid':
      return concat(claimerBytes, amountBytes, nonce, chainIdBytes);
    case 'packed_msg_amount_nonce':
      return concat(claimerBytes, amountBytes, nonce);
    case 'packed_msg_amount_nonce_contract':
      return concat(claimerBytes, amountBytes, nonce, contractBytes);
    case 'packed_contract_msg_amount_nonce':
      return concat(contractBytes, claimerBytes, amountBytes, nonce);
    case 'encode_msg_amount_nonce':
      return concat(new Uint8Array(12), claimerBytes, amountBytes, nonce);
    case 'encode_msg_amount_nonce_chainid':
      return concat(new Uint8Array(12), claimerBytes, amountBytes, nonce, chainIdBytes);
    default:
      throw new Error('Unknown hash format: ' + fmt);
  }
}

const ALL_FORMATS = [
  'packed_msg_amount_nonce_chainid',
  'packed_msg_amount_nonce',
  'packed_msg_amount_nonce_contract',
  'packed_contract_msg_amount_nonce',
  'encode_msg_amount_nonce',
  'encode_msg_amount_nonce_chainid',
];

const ALL_ENVELOPES = ['eip191', 'raw'];

// --------- in-isolate rate limiting ----------

const LAST_CLAIM_AT = new Map(); // addr -> epoch seconds

// --------- handlers ----------

function corsHeaders(env, origin) {
  const allow = (env.ALLOWED_ORIGINS || '*').split(',').map((s) => s.trim());
  const allowAll = allow.includes('*');
  const allowed = allowAll || (origin && allow.includes(origin));
  return {
    'Access-Control-Allow-Origin': allowed ? (allowAll ? '*' : origin) : 'null',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

function jsonResponse(body, status, env, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...corsHeaders(env, origin),
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    },
  });
}

function getConfig(env) {
  const pk = (env.CASTMINER_DEPLOYER_PK || '').trim();
  return {
    pkBytes: pk ? hexToBytes(pk.startsWith('0x') ? pk : '0x' + pk) : null,
    contract: (env.CAST_CONTRACT || '0x41909655593e331151cae645f132e28d531f28b2').toLowerCase(),
    chainId: BigInt(env.CAST_CHAIN_ID || 8453),
    defaultFormat: env.CLAIM_HASH_FORMAT || 'packed_msg_amount_nonce_chainid',
    defaultEnvelope: env.CLAIM_ENVELOPE || 'eip191',
    maxPerReq: Number(env.MAX_CAST_PER_REQUEST || 5),
    maxPerDay: Number(env.MAX_CAST_PER_ADDRESS_PER_DAY || 100),
    minSecondsBetween: Number(env.MIN_SECONDS_BETWEEN_CLAIMS || 30),
  };
}

async function handleHealthz(request, env) {
  const origin = request.headers.get('Origin');
  const cfg = getConfig(env);
  let signer = null;
  if (cfg.pkBytes) {
    try { signer = toChecksumAddress(deriveAddress(cfg.pkBytes)); } catch (_) {}
  }
  return jsonResponse({
    ok: true,
    signer_loaded: !!cfg.pkBytes,
    signer_address: signer,
    contract: toChecksumAddress('0x' + cfg.contract.replace(/^0x/, '')),
    hash_format: cfg.defaultFormat,
    limits: {
      max_cast_per_request: cfg.maxPerReq,
      max_cast_per_address_per_day: cfg.maxPerDay,
      min_seconds_between_claims: cfg.minSecondsBetween,
    },
  }, 200, env, origin);
}

async function handleSignClaim(request, env) {
  const origin = request.headers.get('Origin');
  const cfg = getConfig(env);
  if (!cfg.pkBytes) {
    return jsonResponse({ detail: 'Signer not configured (CASTMINER_DEPLOYER_PK missing).' }, 503, env, origin);
  }

  let body;
  try { body = await request.json(); } catch { return jsonResponse({ detail: 'Invalid JSON body.' }, 400, env, origin); }

  const address = String(body.address || '');
  if (!/^0x[0-9a-fA-F]{40}$/.test(address)) {
    return jsonResponse({ detail: 'address must be a 0x-prefixed 20-byte hex string.' }, 400, env, origin);
  }
  const amount = Number(body.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return jsonResponse({ detail: 'amount must be > 0.' }, 400, env, origin);
  }
  if (amount > cfg.maxPerReq) {
    return jsonResponse({ detail: `amount exceeds per-request cap (${cfg.maxPerReq} CAST).` }, 400, env, origin);
  }
  const fmt = body.format || cfg.defaultFormat;
  const envelope = body.envelope || cfg.defaultEnvelope;
  if (!ALL_FORMATS.includes(fmt)) {
    return jsonResponse({ detail: `Unknown format: ${fmt}` }, 400, env, origin);
  }
  if (!ALL_ENVELOPES.includes(envelope)) {
    return jsonResponse({ detail: `Unknown envelope: ${envelope}` }, 400, env, origin);
  }

  const now = Date.now() / 1000;
  const addrKey = address.toLowerCase();
  const last = LAST_CLAIM_AT.get(addrKey) || 0;
  if (now - last < cfg.minSecondsBetween) {
    const wait = Math.ceil(cfg.minSecondsBetween - (now - last));
    return jsonResponse({ detail: `Slow down — try again in ${wait}s.` }, 429, env, origin);
  }
  LAST_CLAIM_AT.set(addrKey, now);

  // Convert amount CAST -> wei without precision loss for up to 9 decimals.
  const scaled9 = BigInt(Math.round(amount * 1e9));
  const amountWei = scaled9 * (10n ** 9n); // 1e18 total scaling
  const claimerBytes = hexToBytes(address);
  const amountBytes = uint256ToBytes(amountWei);
  const chainIdBytes = uint256ToBytes(cfg.chainId);
  const contractBytes = hexToBytes(cfg.contract);
  const nonce = new Uint8Array(32);
  crypto.getRandomValues(nonce);

  const variants = {};
  for (const f of ALL_FORMATS) {
    const preimage = buildPreimage(f, claimerBytes, amountBytes, nonce, chainIdBytes, contractBytes);
    const digest = keccak_256(preimage);
    for (const env_ of ALL_ENVELOPES) {
      const hashToSign = env_ === 'eip191' ? eip191Wrap(digest) : digest;
      const sig = ecdsaSign(cfg.pkBytes, hashToSign);
      variants[`${f}__${env_}`] = '0x' + bytesToHex(sig);
    }
  }
  const canonical = variants[`${fmt}__${envelope}`];

  return jsonResponse({
    claimer: address,
    contract: toChecksumAddress('0x' + cfg.contract.replace(/^0x/, '')),
    amount_wei: amountWei.toString(),
    amount_cast: amount,
    nonce: '0x' + bytesToHex(nonce),
    signature: canonical,
    signer: toChecksumAddress(deriveAddress(cfg.pkBytes)),
    hash_format: fmt,
    envelope: envelope,
    valid_until_epoch: Math.floor(now) + 600,
    variants,
  }, 200, env, origin);
}

// --------- entry ----------

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';
    const origin = request.headers.get('Origin');

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(env, origin) });
    }

    if (path === '/api/healthz' || path === '/healthz') {
      return handleHealthz(request, env);
    }
    if (path === '/api/sign-claim' || path === '/sign-claim') {
      if (request.method !== 'POST') {
        return jsonResponse({ detail: 'Use POST.' }, 405, env, origin);
      }
      return handleSignClaim(request, env);
    }

    if (env.ASSETS && typeof env.ASSETS.fetch === 'function') {
      return env.ASSETS.fetch(request);
    }
    return new Response('Not Found', { status: 404 });
  },
};
