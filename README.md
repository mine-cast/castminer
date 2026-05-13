# CastMiner

Browser-based crypto mining on **Base** network, exclusively available as a **Farcaster Mini App**.

Users mine **$CAST** by contributing browser hashrate inside Warpcast / Supercast / any Farcaster client, then claim accumulated tokens to their Farcaster embedded wallet on Base.

> Non-Farcaster visitors see a gate page that points them to install Warpcast. No mining is allowed outside Farcaster clients.

---

## Stack

- Pure static: single `index.html` (HTML + CSS + JS) — no build step
- `@farcaster/frame-sdk` via jsDelivr CDN
- Base mainnet (chainId `0x2105` / `8453`)
- Manifest hosted at `/.well-known/farcaster.json`
- Designed for Vercel static hosting

---

## Quick start (local)

```bash
# any static server works
npx --yes serve .
# or
python3 -m http.server 8000
```

Open <http://localhost:3000> (or whichever port your server uses).

> Outside Farcaster you'll see the **gate page** — that's expected. To test the mining UI, run inside Warpcast Frame Playground (see "Test in Farcaster" below).

---

## Deploy to Vercel

1. Push this repo (it's already on GitHub).
2. Go to <https://vercel.com/new>, import `mine-cast/castminer`.
3. **Framework Preset**: `Other` / `Static` — no build step. Output directory: leave default (root).
4. Deploy.
5. After deploy, replace every occurrence of `YOUR-DOMAIN-HERE` with your Vercel domain (e.g. `castminer.vercel.app` or your custom domain) in:
   - `.well-known/farcaster.json` — `homeUrl`, `iconUrl`, `splashImageUrl` (×2)
   - `index.html` — `fc:frame:image` meta tag (set to your splash image URL)
6. Add `icon.png` (200×200) and `splash.png` (1200×630) to the repo root. Redeploy.

The manifest will be served at `https://<your-domain>/.well-known/farcaster.json` directly from the file at the repo root.

---

## Test in Farcaster

1. After deploy, copy the deployment URL.
2. Open Warpcast Frame Playground: <https://warpcast.com/~/developers/frames>
3. Paste the URL → preview.
4. Register the Mini App: <https://warpcast.com/~/developers> → New Mini App → use your manifest URL.

---

## File structure

```
castminer/
├── index.html                          # Single-file app (HTML + CSS + JS)
├── .well-known/
│   └── farcaster.json                  # Mini App manifest (served at /.well-known/farcaster.json)
├── vercel.json                         # Frame-friendly headers (no rewrite needed)
├── README.md
└── .gitignore
```

---

## Pages

The app has four pages (bottom nav):

| Tab    | Purpose                                                                     |
|--------|-----------------------------------------------------------------------------|
| Mine   | Dashboard with hashrate, START/STOP button, session stats, network stats   |
| Pool   | Pool overview, your contribution %, recent blocks                          |
| Rank   | Top-10 leaderboard, your row highlighted                                   |
| Claim  | Available balance, claim button, how-it-works steps, claim history         |

---

## Roadmap (from spec)

- **Phase 1 (MVP, this repo)**: UI + Farcaster SDK integration + gate page + mining simulation + light/dark + wallet connect.
- **Phase 2 (on-chain)**: deploy `$CAST` ERC-20 on Base, real claim transactions, backend mining verification, real pool stats.
- **Phase 3**: referrals, mining-boost NFTs, daily challenges, channel integration, push notifications.
- **Phase 4**: tokenomics + halving, DEX liquidity (Aerodrome/Uniswap on Base), governance, analytics.

See [`CASTMINER-PROJECT.md`](./CASTMINER-PROJECT.md) (when added) for the full spec.

---

## Note on the smart contract

The claim flow is currently **simulated** in `index.html`. To wire it up for production:

```js
// Replace the simulated claim in handleClaim() with:
const tx = await ethProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: userAddress,
    to: CASTMINER_CONTRACT_ADDRESS,   // your $CAST contract on Base
    data: claimFunctionData,           // ABI-encoded claim() call
    chainId: '0x2105'
  }]
});
```

You'll need to deploy the `$CAST` ERC-20 contract on Base with a `claim(address miner, uint256 amount)` function and a backend that signs claim authorizations.
