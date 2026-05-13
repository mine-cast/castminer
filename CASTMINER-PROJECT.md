# CastMiner — Project Documentation (Full Version)

> Browser-based crypto mining on Base network, exclusively available as a Farcaster Mini App.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack & Architecture](#2-tech-stack--architecture)
3. [Farcaster Integration](#3-farcaster-integration)
4. [Access Control (Gate System)](#4-access-control-gate-system)
5. [Design System](#5-design-system)
6. [Page-by-Page UI Specification](#6-page-by-page-ui-specification)
7. [JavaScript Logic & State](#7-javascript-logic--state)
8. [Wallet & On-Chain Integration](#8-wallet--on-chain-integration)
9. [File Structure](#9-file-structure)
10. [Deployment Checklist](#10-deployment-checklist)
11. [Future Roadmap](#11-future-roadmap)

---

## 1. Project Overview

### What is CastMiner?

CastMiner is a browser-based mining application that runs **exclusively inside Farcaster clients** (Warpcast, Supercast, etc.). Users mine a token called **$CAST** by contributing browser hashrate. The app operates on the **Base network** (Coinbase L2, Chain ID 8453).

### Core Concept

- Users open CastMiner as a **Farcaster Mini App** (formerly Frames v2)
- They tap "START MINING" to begin contributing hashrate from their browser
- $CAST tokens accumulate in real-time based on hashrate contribution
- Users claim accumulated $CAST to their Farcaster wallet on Base network
- Non-Farcaster visitors see a gate/landing page prompting them to open in Farcaster

### Key Principles

- **Farcaster-exclusive**: No mining allowed outside Farcaster clients
- **Base-native**: All on-chain activity happens on Base (chain ID 8453, hex 0x2105)
- **Mobile-first**: Designed for Farcaster's ~424px frame viewport
- **No hardcoded domain**: Domain name is NOT set yet — no "castminer.xyz" or any domain in UI
- **Light/Dark mode**: Full theme toggle support

---

## 2. Tech Stack & Architecture

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | Vanilla HTML/CSS/JS (single file) |
| Fonts | Google Fonts — Outfit (headings, 400-800) + DM Sans (body, 400-700) |
| Icons | Inline SVG (no icon library) |
| Styling | CSS Custom Properties (variables) for theming |
| Animations | CSS @keyframes + JS intervals |
| Layout | Flexbox + CSS Grid, max-width 424px |

### Farcaster SDK

| Component | Details |
|-----------|---------|
| SDK | `@farcaster/frame-sdk` via CDN (jsDelivr) |
| Auth | Farcaster context (FID, username, pfpUrl) |
| Wallet | Farcaster embedded wallet (ethProvider) |
| Manifest | `/.well-known/farcaster.json` |

### Blockchain

| Component | Details |
|-----------|---------|
| Network | Base (Chain ID: 8453, Hex: 0x2105) |
| Token | $CAST (ERC-20, contract TBD) |
| RPC | https://mainnet.base.org |
| Explorer | https://basescan.org |

---

## 3. Farcaster Integration

### SDK Loading

```html
<script src="https://cdn.jsdelivr.net/npm/@farcaster/frame-sdk@latest/dist/index.min.js"></script>
```

### Detection Methods (3-layer)

The app uses three methods to detect if it's running inside Farcaster:

**Method 1: SDK Context**
```javascript
// Check for Farcaster Frame SDK globals
if (window.frame?.sdk) fcSdk = window.frame.sdk;
else if (window.FrameSDK) fcSdk = new window.FrameSDK();
else if (window.farcaster) fcSdk = window.farcaster;

// Get user context with 3s timeout
fcContext = await Promise.race([
  typeof fcSdk.context === 'function' ? fcSdk.context() : fcSdk.context,
  new Promise((_, reject) => setTimeout(() => reject('timeout'), 3000))
]);
```

**Method 2: Iframe + URL Parameters**
```javascript
const isIframe = window !== window.parent;
const hasFcParams = urlParams.has('fc_fid') || urlParams.has('fid') || urlParams.has('signer');
const isFcReferrer = referrer.includes('warpcast') || referrer.includes('farcaster') || referrer.includes('supercast');
```

**Method 3: Wallet Provider**
```javascript
ethProvider = fcSdk.wallet.ethProvider || fcSdk.wallet.getEthereumProvider?.();
```

### Ready Signal

After initialization, the app signals ready to the Farcaster client:
```javascript
if (fcSdk && typeof fcSdk.actions?.ready === 'function') {
  fcSdk.actions.ready();
}
```

### Frame Meta Tags

```html
<meta name="fc:frame" content="vNext" />
<meta name="fc:frame:image" content="" />
<meta name="fc:frame:button:1" content="Open CastMiner" />
<meta name="fc:frame:button:1:action" content="launch_frame" />
<meta name="og:title" content="CastMiner — Browser Mining on Base" />
<meta name="og:description" content="Mine $CAST tokens directly from Farcaster. Powered by Base network." />
```

### Manifest File (`/.well-known/farcaster.json`)

```json
{
  "name": "CastMiner",
  "short_name": "CastMiner",
  "description": "Browser-based mining on Base network. Mine $CAST tokens directly from Farcaster.",
  "version": "1.0.0",
  "homeUrl": "https://YOUR-DOMAIN-HERE",
  "iconUrl": "https://YOUR-DOMAIN-HERE/icon.png",
  "splashImageUrl": "https://YOUR-DOMAIN-HERE/splash.png",
  "splashBackgroundColor": "#0A0E1A",
  "frame": {
    "version": "next",
    "name": "CastMiner",
    "iconUrl": "https://YOUR-DOMAIN-HERE/icon.png",
    "homeUrl": "https://YOUR-DOMAIN-HERE",
    "splashImageUrl": "https://YOUR-DOMAIN-HERE/splash.png",
    "splashBackgroundColor": "#0A0E1A"
  },
  "triggers": [
    {
      "type": "cast_action",
      "id": "mine",
      "name": "Start Mining",
      "description": "Open CastMiner and start mining $CAST"
    }
  ],
  "requiredChains": ["eip155:8453"],
  "permissions": ["wallet"]
}
```

---

## 4. Access Control (Gate System)

### Flow

```
User opens URL
    |
    v
[Loading Screen] "Connecting to Farcaster..."
    |
    v
[Detect Farcaster?]
    |         |
   YES        NO
    |          |
    v          v
[Show App]  [Show Gate Page]
[User Bar]  "Open in Farcaster"
[Mining UI]  button → warpcast.com
```

### Gate Page Content (Non-Farcaster Visitors)

- **Icon block**: 120x120px rounded square, gradient blue→purple, mining pickaxe SVG inside
- **Logo**: "CastMiner" in gradient text (36px, Outfit 800)
- **Subtitle**: "Browser-based mining on Base network. Exclusively available inside Farcaster."
- **Feature chips** (3 items in a row):
  - Mine (pickaxe icon)
  - Earn (checkmark icon)
  - Claim (wallet icon)
- **CTA Button**: "Open in Farcaster" — purple gradient (#8A63D2 → #6944A8), links to https://warpcast.com
- **Note text**: "Install Warpcast or any Farcaster client to start mining $CAST tokens on Base network."

### Loading Screen

- Full-screen overlay, z-index 10000
- Spinning ring (48x48, blue border-top on gray ring)
- Text: "Connecting to Farcaster..." (Outfit 13px)
- Fades out after detection completes

---

## 5. Design System

### Color Palette

| Variable | Dark Mode | Light Mode | Usage |
|----------|-----------|------------|-------|
| `--primary` | #0052FF | #0052FF | Base network blue, primary actions |
| `--primary-glow` | rgba(0,82,255,0.4) | rgba(0,82,255,0.4) | Glow effects |
| `--accent` | #8A63D2 | #8A63D2 | Farcaster purple, secondary actions |
| `--accent-glow` | rgba(138,99,210,0.3) | rgba(138,99,210,0.3) | Accent glow |
| `--success` | #00C853 | #00C853 | Active states, confirmations |
| `--warning` | #FFB300 | #FFB300 | Warnings, light mode toggle |
| `--danger` | #FF3D71 | #FF3D71 | Inactive states, errors |
| `--bg` | #0A0E1A | #F5F7FA | Main background |
| `--bg-secondary` | #111827 | #FFFFFF | Secondary background |
| `--surface` | rgba(255,255,255,0.06) | rgba(0,0,0,0.03) | Card surfaces, inputs |
| `--text` | #F0F2F5 | #111827 | Primary text |
| `--text-secondary` | #8B95A5 | #6B7280 | Labels, secondary text |
| `--text-muted` | #4A5568 | #9CA3AF | Muted text, hints |
| `--card-bg` | rgba(17,24,39,0.7) | rgba(255,255,255,0.85) | Card backgrounds |
| `--card-border` | rgba(255,255,255,0.06) | rgba(0,0,0,0.06) | Card borders |
| `--nav-bg` | rgba(10,14,26,0.95) | rgba(255,255,255,0.95) | Navigation background |

### Typography

| Element | Font | Weight | Size |
|---------|------|--------|------|
| Headings, logos, numbers | Outfit | 600-800 | 13-48px |
| Body text, labels | DM Sans | 400-600 | 11-15px |
| Addresses, code | monospace (system) | 500 | 10-12px |

### Spacing & Layout

- **App container**: max-width 424px, centered, full viewport height (100dvh)
- **Content padding**: 0 16px, bottom padding 100px (clearance for nav)
- **Card padding**: 18px, border-radius 16px, margin-bottom 12px
- **Stat card padding**: 14px, border-radius 12px
- **Grid gaps**: 10px (stats grid)
- **Desktop (>425px)**: Outer body background #050810 (dark) / #E8EBF0 (light), side borders on container

### Animation System

| Animation | Keyframe | Duration | Easing |
|-----------|----------|----------|--------|
| Page transition | fadeSlideIn | 0.35s | ease |
| Float particles | floatUp | 12-30s | linear |
| Status dot pulse | pulse-dot | 2s | ease-in-out |
| Mine button pulse | btnPulse | 2s | ease-in-out |
| Icon spin (mining) | spinSlow | 3s | linear |
| Loading spinner | spin | 0.8s | linear |
| All color transitions | — | 0.3s | cubic-bezier(0.4, 0, 0.2, 1) |

### Glassmorphism Cards

```css
background: var(--card-bg);          /* semi-transparent */
backdrop-filter: blur(16px);         /* glass blur */
border: 1px solid var(--card-border); /* subtle border */
border-radius: 16px;
```

### Background Particles

- 18 floating text particles
- Content: hash-like strings (0x3a8f, sha256, keccak, nonce:, hash:, block#, etc.)
- Opacity: 0.12
- Animation: float upward (floatUp), random duration 12-30s, random delay 0-15s
- Font size: 8-14px randomized

---

## 6. Page-by-Page UI Specification

### Global UI Elements

#### Status Bar (top, always visible)
```
[Green dot] Connected to Base    CastMiner    [Theme Toggle]
```
- Left: Animated green dot (7x7px, pulsing) + "Connected to Base" text
- Center: "CastMiner" logo in gradient text (Outfit 800, 16px)
- Right: Theme toggle switch (40x22px, circle slides left/right)
  - Dark mode: Blue circle on left, moon icon visible
  - Light mode: Yellow circle on right, sun icon visible

#### User Bar (below status bar, visible only when in Farcaster)
```
[Avatar] DisplayName          [0x5Fe1...a3B7]
         @username · FID #123
```
- Avatar: 32x32px circle, shows Farcaster PFP or gradient placeholder
- Name: Outfit 600, 13px
- FID: 11px muted text
- Wallet: Monospace 10px, truncated address in a bordered chip

#### Bottom Navigation (fixed bottom, 4 tabs)
```
  Mine     Pool     Rank     Claim
```
- Each tab: SVG icon (22x22) + label (Outfit 600, 10px)
- Active tab: Blue color + blue indicator bar (20x3px) above icon
- Inactive: Muted gray color
- Background: nav-bg with blur(20px), border-top
- Padding includes safe-area-inset-bottom for iOS notch

---

### Page 1: Mine (Dashboard) — Default/Home

This is the main mining interface. Layout from top to bottom:

#### Mining Status Badge
- Position: Center-aligned, top of page
- States:
  - Inactive: Red-tinted background, red text "Inactive", static dot
  - Active: Green-tinted background, green text "Mining", pulsing dot
- Style: Pill shape (20px radius), 6px 14px padding, Outfit 600 12px

#### Hashrate Display
- Large number: "0.00" → animates up when mining (e.g. "28.45")
- Style: Outfit 800, 42px, gradient text (blue→purple)
- Unit label below: "MH/s Hashrate" (DM Sans 500, 14px, secondary color)

#### Mining Button
- Size: 180x180px circle
- Background: linear-gradient(135deg, #0052FF, #8A63D2)
- Content (centered, vertical stack):
  - Pickaxe SVG icon (36x36, white)
  - "START" label (Outfit 700, 14px, 1.5px letter-spacing)
  - "MINING" sublabel (10px, 70% opacity)
- Decorative rings: Two concentric circles (210px and 240px), primary-glow border
- States:
  - Idle: Static, press scales to 0.95
  - Mining: Label changes to "STOP", button pulses with glow animation (btnPulse), icon spins (spinSlow 3s)

#### Stats Grid (2x2)
| Card | Label | Value ID | Color | Sub-label |
|------|-------|----------|-------|-----------|
| Earned | EARNED | earnedValue | primary (blue) | $CAST Tokens |
| Session | SESSION | sessionTime | accent (purple) | Duration |
| Shares | SHARES | sharesValue | success (green) | Accepted |
| Efficiency | EFFICIENCY | effValue | default | Rate |

- Grid: 2 columns, 10px gap
- Each card: surface background, surface-border, 14px padding, 12px radius

#### Network Stats Card
- Title: "NETWORK STATS" (card-title style)
- Rows (label — value format, separated by bottom border):
  - Total Hashrate → "842.5 GH/s" (fluctuates every 5s)
  - Difficulty → "14,205,381" (fluctuates every 5s)
  - Block Height → "19,847,632" (increments randomly during mining)
  - Block Reward → "50 $CAST" (static)

---

### Page 2: Pool

#### Section Title
- "Pool Overview" (Outfit 700, 20px)

#### Pool Hero
- Center-aligned large number: "1,247" (Outfit 800, 48px, primary blue)
- Label: "Miners Online" (13px, secondary color)
- Number fluctuates every 5 seconds (1240-1255 range)

#### Stats Grid (2x2)
| Card | Label | Value | Sub-label |
|------|-------|-------|-----------|
| Pool Hashrate | POOL HASHRATE | 342.8 (fluctuates) | GH/s |
| Blocks Found | BLOCKS FOUND | 2,841 | Last 24h |
| Avg. Block Time | AVG. BLOCK TIME | 12.4s | Target: 12s |
| Pool Fee | POOL FEE | 1.5% | PPLNS |

#### Your Contribution Card
- Title: "YOUR CONTRIBUTION"
- Row: "Share of Pool" label → percentage value (blue)
- Progress bar below: 8px height, gradient fill (blue→purple), animated width
- Percentage starts at 0.00%, updates based on user hashrate / pool hashrate

#### Recent Blocks Card
- Title: "RECENT BLOCKS"
- 4 block items, each with:
  - Block icon: 36x36px rounded square, gradient, white cube SVG inside
  - Block number: "#19,847,631" (bold 14px)
  - Time: "2 min ago" (11px muted)
  - Reward: "+50 $CAST" (Outfit 600, green)
- Blocks: #19,847,631 (2 min), #19,847,630 (14 min), #19,847,629 (28 min), #19,847,628 (41 min)

---

### Page 3: Leaderboard (tab labeled "Rank")

#### Section Title
- "Top Miners" (Outfit 700, 20px)

#### Leaderboard Table
- Grid columns: 40px | 1fr | 90px | 70px
- Header row: # | Miner | Mined | Hash (11px, muted, uppercase)
- 10 data rows:

| Rank | Address | Tokens | Hashrate | Note |
|------|---------|--------|----------|------|
| 1 (gold) | 0x3a8F...c2dE | 14,820 | 1.2 GH | Gold color rank |
| 2 (silver) | 0xb12D...9f4A | 12,340 | 980 MH | Silver color rank |
| 3 (bronze) | 0x7eC1...d38B | 9,152 | 740 MH | Bronze color rank |
| 4 | 0x91fA...27eC | 7,841 | 520 MH | |
| 5 | 0xdE43...81bF | 6,290 | 410 MH | |
| 6 | 0x22aB...f5D1 | 5,120 | 380 MH | |
| 7 | 0xC8f2...4a9E | 4,310 | 290 MH | |
| **8** | **0x5Fe1...a3B7** | **dynamic** | **dynamic** | **Current user — highlighted row** |
| 9 | 0xA4d8...c72F | 2,840 | 180 MH | |
| 10 | 0x6bE9...1dA4 | 2,105 | 120 MH | |

- Current user row (rank 8): Blue glow background (--glow-1), 8px border-radius, negative margin for inset effect
- Rank colors: #FFD700 (gold), #C0C0C0 (silver), #CD7F32 (bronze)
- Addresses: monospace font, 12px
- Token values: Outfit 600, accent purple, right-aligned
- Hash values: 11px, muted, right-aligned

#### Your Rank Card
- Centered card below table
- "YOUR RANK" label (stat-label style)
- "#8" large number (Outfit 700, 32px, accent purple)
- "of 1,247 miners" sub-label

---

### Page 4: Claim

#### Section Title
- "Claim Rewards" (Outfit 700, 20px)

#### Claim Hero
- Large amount: "0.000" (Outfit 800, 44px, gradient text blue→purple)
- Synced with earned value from mining
- Label: "$CAST Available to Claim" (13px, secondary color)
- Base badge below: Pill with Base logo (blue circle + white triangle) + "On Base Network" text

#### Claim Button
- Full-width, 16px padding, 14px radius
- Background: gradient blue→purple
- Text: wallet icon (20x20 SVG) + "CLAIM REWARDS" (Outfit 700, 16px, white)
- Hover: Glow shadow + translateY(-1px)
- Press: scale(0.98)
- States during claim flow:
  1. "Signing Transaction..." (with spinning loader ring)
  2. "Confirming on Base..." (with spinning loader ring)
  3. "Claimed Successfully!" (checkmark)
  4. Resets back to "CLAIM REWARDS"
- Error state: "Claim Failed — Try Again"
- No balance: "Nothing to Claim"
- No wallet: "Connect Wallet First"

#### How It Works Card
- Title: "HOW IT WORKS"
- 4 numbered steps with connector lines:
  1. **Mine $CAST** — "Start mining to earn $CAST tokens. Your hashrate determines earnings."
  2. **Accumulate Rewards** — "Tokens accrue in real-time. View your balance on the dashboard."
  3. **Claim on Base** — "Tap claim to initiate an on-chain transaction on Base network."
  4. **Receive Tokens** — "$CAST tokens arrive in your connected wallet within seconds."
- Step visual: Numbered circle (28px, primary border) + vertical connector line (2px)

#### Claim History Card
- Title: "CLAIM HISTORY"
- Pre-populated with 3 sample entries:
  - +125.400 $CAST — May 10, 2026 — 14:32 — Confirmed (green badge)
  - +84.200 $CAST — May 8, 2026 — 09:15 — Confirmed
  - +210.750 $CAST — May 5, 2026 — 21:48 — Confirmed
- New claims get prepended with fadeSlideIn animation
- Each row: amount (green, Outfit 600, 14px) | date (11px muted) | status badge (green background + text)

---

## 7. JavaScript Logic & State

### State Variables

```javascript
let isMining = false;        // Mining toggle state
let hashrate = 0;            // Current hashrate in MH/s
let earned = 0;              // Total $CAST earned this session
let shares = 0;              // Accepted shares count
let sessionSeconds = 0;      // Session duration in seconds
let miningInterval = null;   // Mining tick interval (100ms)
let sessionInterval = null;  // Session timer interval (1s)
let blockHeight = 19847632;  // Current block height

// Farcaster
let fcContext = null;        // Farcaster SDK context (user info)
let fcSdk = null;            // Farcaster SDK reference
let ethProvider = null;      // Ethereum provider from Farcaster wallet
let isInFarcaster = false;   // Whether running in Farcaster client
let userAddress = null;      // Connected wallet address
```

### Mining Simulation

- **Tick rate**: 100ms (10 updates per second)
- **Hashrate ramp-up**: Target = 24 + random(0-12) MH/s, approaches at 8% per tick
- **Hashrate fluctuation**: +/- 0.75 MH/s random noise when at target
- **Earn rate**: hashrate * 0.0000012 $CAST per tick
- **Share acceptance**: 15% chance per tick
- **Block discovery**: 0.5% chance per tick (increments block height)
- **Efficiency**: 94-99.8% when mining (random display)
- **Ramp-down on stop**: Multiplied by 0.9 per 100ms tick until < 0.01

### Network Stats Animation

- Updates every 5 seconds
- Total hashrate: 840-845 GH/s range
- Difficulty: 14,200,000-14,210,000 range
- Pool miners: 1,240-1,255 range
- Pool hashrate: 340-345 GH/s range

### Theme Toggle

- Stored on `<html data-theme="dark|light">`
- Toggle via click on theme-toggle element
- All colors transition smoothly via CSS custom properties
- Default: Dark mode

### Page Navigation

- 4 pages: mine, pool, leaderboard, claim
- Switch via `switchPage(name)` function
- Active page gets `.active` class (display: block + fadeSlideIn animation)
- Nav items get `.active` class (blue color + top indicator bar)
- Content scrolls to top on page switch

---

## 8. Wallet & On-Chain Integration

### Wallet Connection Flow

```
1. Try Farcaster SDK wallet (fcSdk.wallet.ethProvider)
2. Request accounts (eth_requestAccounts)
3. Switch to Base network (wallet_switchEthereumChain, chainId: 0x2105)
4. If Base not added, add it (wallet_addEthereumChain)
5. Fallback: try window.ethereum if SDK wallet not available
6. Display truncated address in user bar
```

### Base Network Config

```javascript
{
  chainId: '0x2105',           // 8453 decimal
  chainName: 'Base',
  rpcUrls: ['https://mainnet.base.org'],
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  blockExplorerUrls: ['https://basescan.org']
}
```

### Claim Transaction (Production)

Currently simulated. For production, uncomment and configure:

```javascript
const tx = await ethProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: userAddress,
    to: CASTMINER_CONTRACT_ADDRESS,  // Deploy and set this
    data: claimFunctionData,          // ABI-encoded claim() call
    chainId: '0x2105'
  }]
});
```

### Required Smart Contract

A $CAST ERC-20 contract needs to be deployed on Base with:
- `claim(address miner, uint256 amount)` function
- Access control for authorized claim signers
- Total supply management
- Block reward distribution logic

---

## 9. File Structure

```
project/
├── index.html                          # Main app (single file, ~1870 lines)
│   ├── <head>
│   │   ├── Farcaster meta tags (fc:frame, og:title, og:description)
│   │   ├── Google Fonts (Outfit + DM Sans)
│   │   ├── Farcaster Frame SDK (CDN)
│   │   └── <style> (~1050 lines CSS)
│   ├── <body>
│   │   ├── Loading screen overlay
│   │   ├── Gate overlay (non-Farcaster)
│   │   ├── Background particles canvas
│   │   ├── App container (424px)
│   │   │   ├── Status bar
│   │   │   ├── User bar (Farcaster auth)
│   │   │   ├── Content area (scrollable)
│   │   │   │   ├── Page: Mine (dashboard)
│   │   │   │   ├── Page: Pool
│   │   │   │   ├── Page: Leaderboard
│   │   │   │   └── Page: Claim
│   │   │   └── Bottom navigation
│   │   └── <script> (~415 lines JS)
│   │       ├── Farcaster integration (init, detect, auth, wallet)
│   │       ├── Mining simulation (start, stop, tick, display)
│   │       ├── Theme toggle
│   │       ├── Page switching
│   │       ├── Claim flow
│   │       ├── Background particles
│   │       └── Network stats animation
│
├── manifest.json                       # Farcaster app manifest template
│   └── Host at: /.well-known/farcaster.json
│
├── CASTMINER-PROJECT.md               # This documentation
│
└── (needed for production)
    ├── icon.png                        # App icon (200x200px)
    ├── splash.png                      # Splash screen (1200x630px)
    ├── api/
    │   └── webhook.js                  # Farcaster webhook handler
    └── contracts/
        └── CastMiner.sol              # $CAST ERC-20 on Base
```

---

## 10. Deployment Checklist

### Pre-Deploy

- [ ] Choose and register domain name
- [ ] Replace ALL `YOUR-DOMAIN-HERE` in manifest.json with actual domain
- [ ] Create `icon.png` (200x200px, app icon)
- [ ] Create `splash.png` (1200x630px, splash/loading image)
- [ ] Update `fc:frame:image` meta tag with splash image URL
- [ ] Remove `_instructions` field from manifest.json

### Farcaster Setup

- [ ] Already have Farcaster FID (confirmed)
- [ ] Host manifest at `https://your-domain/.well-known/farcaster.json`
- [ ] Register app at https://warpcast.com/~/developers
- [ ] Test in Warpcast developer tools (Frame Playground)
- [ ] Share Mini App link in a cast to make it discoverable

### Smart Contract (for production claims)

- [ ] Write and audit $CAST ERC-20 contract
- [ ] Deploy to Base mainnet
- [ ] Set `CASTMINER_CONTRACT_ADDRESS` in code
- [ ] Encode `claim()` function data
- [ ] Set up backend for claim authorization/signing

### Hosting

- [ ] Deploy static HTML to hosting (Vercel, Cloudflare Pages, etc.)
- [ ] Ensure HTTPS is enabled
- [ ] Verify CORS headers allow Farcaster client iframes
- [ ] Set `X-Frame-Options` to allow Warpcast embedding (or remove it)
- [ ] Add `Content-Security-Policy` frame-ancestors for Farcaster clients

---

## 11. Future Roadmap

### Phase 1 — MVP (current)
- [x] UI/UX design complete
- [x] Farcaster SDK integration
- [x] Gate page for non-FC users
- [x] Mining simulation frontend
- [x] Light/dark mode
- [x] Wallet connection flow
- [ ] Domain + deployment
- [ ] Farcaster app registration

### Phase 2 — On-Chain
- [ ] $CAST token contract on Base
- [ ] Real mining proof system (proof-of-work or proof-of-browser-compute)
- [ ] On-chain claim function
- [ ] Backend API for mining verification
- [ ] Real-time pool stats from blockchain

### Phase 3 — Features
- [ ] Referral system (cast-to-earn bonuses)
- [ ] Mining boost NFTs
- [ ] Daily/weekly mining challenges
- [ ] Farcaster channel integration
- [ ] Push notifications for block discovery
- [ ] Multi-pool support

### Phase 4 — Growth
- [ ] $CAST tokenomics (supply schedule, halving)
- [ ] DEX liquidity on Base (Uniswap/Aerodrome)
- [ ] Governance features
- [ ] Mobile optimization improvements
- [ ] Analytics dashboard

---

*Document generated for CastMiner project. Last updated: May 2026.*
*This is a living document — update as the project evolves.*
