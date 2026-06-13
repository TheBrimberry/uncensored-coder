# 💰 Ad Monetization Toolkit

Make money from ads on any website with **barely any effort**. Sign up for an
ad network, paste your ID into one config file, run one command — every page on
your site starts earning.

It auto-places ad slots in the **highest-paying positions**, lazy-loads them so
your site stays fast, stacks multiple networks for maximum fill rate, and handles
the boring-but-mandatory bits (`ads.txt`, consent bar, "Advertisement" labels)
that otherwise get your account banned.

---

## 🚀 Quick start (3 steps)

```bash
# 1. Open the config and turn on a network (AdSense is the easiest to get approved)
nano monetization/ad_config.yaml
#    networks.adsense.enabled: true
#    networks.adsense.publisher_id: "ca-pub-XXXXXXXXXXXXXXXX"

# 2. Build the drop-in ad loader + ads.txt
python -m monetization.cli build

# 3a. Auto-inject ads into every page of your site...
python -m monetization.cli inject ./path-to-your-website
#    ...then copy monetization/dist/ad-loader.js + ads.txt to your web root.

# 3b. ...OR just paste this one line into your <head> on any platform:
python -m monetization.cli snippet
```

That's it. You're monetized.

---

## 🧩 "Plug in whatever you gotta plug in"

Enable any combination of networks in `ad_config.yaml`. Stacking them increases
fill rate (and income). Each is one `enabled: true` away:

| Network          | Why use it                                  | Approval |
|------------------|---------------------------------------------|----------|
| **Google AdSense** | Highest baseline RPM, easy to start        | Needs review |
| **Media.net**    | Strong contextual ads, good AdSense backup  | Needs review |
| **Ezoic**        | AI placement, usually best RPM at scale     | Needs review |
| **PropellerAds** | Pop-under/push, no traffic minimum          | Instant |
| **Direct/house** | Sell your own banners at 100% margin        | Instant |

`ads.txt` is regenerated automatically to match whatever you enable.

---

## 📈 "The most income possible"

The toolkit ships these revenue levers on by default (tune in `ad_config.yaml`):

- **High-value placements**: top banner, in-content (x2), sidebar, sticky footer.
- **Sticky anchored footer** — among the highest-RPM mobile units.
- **Lazy loading** — keeps Core Web Vitals green (Google rewards fast sites
  with better ranking *and* higher ad rates).
- **Network stacking + fallback** — direct → AdSense → Ezoic, so slots rarely
  go empty.
- **Optional ad refresh** (`refresh_seconds`) — more impressions per visit.
- **Consent bar** — unlocks personalized ads, which pay multiples of
  non-personalized.

Estimate your earnings:

```bash
python -m monetization.cli estimate 50000        # low / typical / high RPM
python -m monetization.cli estimate 50000 12.5   # using your own RPM
```

---

## 👀 Preview locally

```bash
python -m monetization.cli serve ./your-site     # or omit path for a demo page
# open http://localhost:8800
```

You'll see the ad slots injected and lazy-loading exactly where they'll appear.
With real network IDs in the config, those slots fill with paid ads.

---

## 🛠️ Commands

| Command | What it does |
|---------|--------------|
| `build` | Compile config → `dist/ad-loader.js`, `dist/snippet.html`, `dist/ads.txt` |
| `snippet` | Print the one `<script>` line to paste into your `<head>` |
| `inject <path>` | Auto-insert the loader into every `.html`/`.htm` in a file or folder (idempotent) |
| `serve [path] [port]` | Local preview server |
| `estimate <pageviews> [rpm]` | Rough monthly revenue projection |

---

## ⚠️ Stay compliant (don't get banned)

- Put real content on pages — ad networks reject thin/empty sites
  (use `min_content_words` to auto-skip near-empty pages).
- Never click your own ads.
- Keep `label_ads` and `generate_ads_txt` on; upload `ads.txt` to your domain root.
- If `refresh_seconds > 0`, confirm your network allows refresh first.
