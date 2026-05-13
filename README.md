# CastMiner

Browser-based crypto mining on **Base** network, exclusively available as a **Farcaster Mini App**.

Users mine **$CAST** by contributing browser hashrate inside Warpcast / Supercast / any Farcaster client, then claim accumulated tokens to their Farcaster embedded wallet on Base.

> Non-Farcaster visitors see a gate page that points them to install Warpcast. No mining is allowed outside Farcaster clients.

## Live deployment

This repo is currently **already deployed** at:

- App: <https://castminer-dyydywlt.devinapps.com>
- Manifest: <https://castminer-dyydywlt.devinapps.com/.well-known/farcaster.json>
- Icon: <https://castminer-dyydywlt.devinapps.com/icon.png>
- Splash: <https://castminer-dyydywlt.devinapps.com/splash.png>

The manifest already points at this URL so the Mini App is **ready to register on Warpcast** without any additional hosting setup.

To migrate to your own domain later, see the [Deploy](#deploy) section.

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

## Deploy

The repo ships **multi-host configs** so it deploys cleanly anywhere without changes:

| Host              | Config used                          | Free tier | Requires phone |
|-------------------|--------------------------------------|-----------|----------------|
| Cloudflare Pages  | `_headers`                           | yes       | no             |
| Netlify           | `netlify.toml` + `_headers`          | yes       | no             |
| GitHub Pages      | `.nojekyll` (headers limited)        | yes       | no             |
| Vercel            | `vercel.json`                        | yes       | OTP via phone  |

### Recommended: Cloudflare Pages (no phone needed)

1. Sign up: <https://dash.cloudflare.com/sign-up> — email only, no OTP.
2. Workers & Pages → **Create application** → **Pages** → **Connect to Git**.
3. Authorize Cloudflare to access GitHub → select `mine-cast/castminer`.
4. Set up build:
   - **Production branch**: `devin/1778691247-castminer-app` (or `main` after you merge)
   - **Framework preset**: `None`
   - **Build command**: *(empty)*
   - **Build output directory**: `/` (or leave default)
5. **Save and Deploy**. You'll get a URL like `castminer.pages.dev`.
6. **Substitute the domain** — replace every occurrence of `YOUR-DOMAIN-HERE` with your real Cloudflare Pages domain (or custom domain) in:
   - `.well-known/farcaster.json` — `homeUrl`, `iconUrl`, `splashImageUrl`, and inside `frame.{...}` (4 total)
   - `index.html` — the `fc:frame:image` meta tag (use your splash image URL)
   - Commit + push → Cloudflare auto-redeploys.
7. **Add assets** — drop `icon.png` (200×200) and `splash.png` (1200×630) at the repo root, push.

### Netlify

1. Sign up: <https://app.netlify.com/signup> → **Sign up with GitHub** (no phone OTP).
2. **Add new site** → **Import an existing project** → GitHub → select `mine-cast/castminer`.
3. Build settings: leave **Build command** empty, **Publish directory** `.` (root). Click **Deploy**.
4. Same domain-substitution + asset steps as above.

### GitHub Pages

1. Repo → **Settings** → **Pages** → **Build and deployment** → Source: **Deploy from a branch**.
2. Branch: `devin/1778691247-castminer-app` (or `main`) → folder `/ (root)` → **Save**.
3. URL: `https://mine-cast.github.io/castminer/`.
4. Same domain-substitution + asset steps. (Note: GH Pages does not honor `_headers` — the page works, but iframe-embed headers fall back to GitHub defaults. Should be fine for Warpcast Frame Playground.)

### Vercel

Uses `vercel.json` (already in repo). Same flow as above, but Vercel requires a phone OTP at signup.

The manifest is served at `https://<your-domain>/.well-known/farcaster.json` directly from the file at the repo root.

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
├── _headers                            # Cloudflare Pages / Netlify headers
├── netlify.toml                        # Netlify build + headers config
├── .nojekyll                           # Disable Jekyll on GitHub Pages
├── vercel.json                         # Vercel headers (optional, if you use Vercel)
├── CASTMINER-PROJECT.md                # Full spec from project doc
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
