#!/usr/bin/env python3
"""
💰 Ad Monetization CLI

Earn from ads with barely any effort:

    python -m monetization.cli build              # compile config -> ad-loader.js + ads.txt
    python -m monetization.cli snippet            # print the one line to paste in your <head>
    python -m monetization.cli inject ./site      # auto-add ads to every .html in a folder
    python -m monetization.cli serve ./site       # local preview with a fake ad filling the slots
    python -m monetization.cli estimate 50000     # rough monthly revenue for N pageviews

Typical flow:
    1) sign up for an ad network (AdSense is easiest)
    2) paste your IDs into monetization/ad_config.yaml, set enabled: true
    3) build, then inject (or paste the snippet) — done.
"""

import sys
import os
import shutil

from .builder import AdBuilder
from .injector import Injector


def _print(msg):
    print(msg, flush=True)


def cmd_build(_args):
    b = AdBuilder()
    res = b.build()
    _print("✅ Built ad system:")
    _print(f"   loader : {res['loader']}")
    _print(f"   snippet: {res['snippet']}")
    if res["ads_txt"]:
        _print(f"   ads.txt: {res['ads_txt']}  (upload to https://yourdomain/ads.txt)")
    nets = res["networks"]
    if nets:
        _print(f"   networks active: {', '.join(nets)}")
    else:
        _print("   ⚠️  No networks enabled yet — edit monetization/ad_config.yaml "
               "and set a network's `enabled: true`.")
    _print("\nNext: copy the loader to your web root, then run "
           "`python -m monetization.cli inject ./your-site`")


def cmd_snippet(_args):
    _print(AdBuilder().snippet())


def cmd_inject(args):
    if not args:
        _print("Usage: python -m monetization.cli inject <file-or-folder> [loader-url]")
        return 1
    target = args[0]
    loader_url = args[1] if len(args) > 1 else "/ad-loader.js"
    if not os.path.exists(target):
        _print(f"❌ Path not found: {target}")
        return 1
    inj = Injector(loader_url=loader_url)
    injected, skipped = inj.inject_path(target)
    _print(f"✅ Injected ads into {len(injected)} page(s).")
    for f in injected:
        _print(f"   + {f}")
    if skipped:
        _print(f"   ({len(skipped)} already had the ad loader, left untouched)")
    _print("\nDon't forget: copy dist/ad-loader.js to your web root so the "
           "injected <script src> resolves.")
    return 0


def cmd_serve(args):
    """Build a preview site with the loader + a demo banner, then serve it."""
    import http.server
    import socketserver

    src = args[0] if args else None
    port = int(args[1]) if len(args) > 1 else 8800

    b = AdBuilder()
    res = b.build()
    preview = os.path.join(b.base, "dist", "preview")
    os.makedirs(preview, exist_ok=True)

    # Stage either the user's site or a generated demo page.
    if src and os.path.isdir(src):
        for root, _d, names in os.walk(src):
            for n in names:
                rel = os.path.relpath(os.path.join(root, n), src)
                dst = os.path.join(preview, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(root, n), dst)
        Injector().inject_path(preview)
    else:
        with open(os.path.join(preview, "index.html"), "w", encoding="utf-8") as f:
            f.write(_DEMO_PAGE)

    shutil.copy2(res["loader"], os.path.join(preview, "ad-loader.js"))

    os.chdir(preview)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        _print(f"🌐 Preview at http://localhost:{port}  (Ctrl+C to stop)")
        _print("   Ad slots are injected & lazy-loaded; with real IDs they fill with paid ads.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            _print("\nStopped.")
    return 0


def cmd_estimate(args):
    """Rough monthly revenue = pageviews/1000 * RPM, across a few scenarios."""
    if not args:
        _print("Usage: python -m monetization.cli estimate <monthly_pageviews> [rpm]")
        return 1
    try:
        pv = float(args[0])
    except ValueError:
        _print("❌ pageviews must be a number")
        return 1
    if len(args) > 1:
        scenarios = [("your RPM", float(args[1]))]
    else:
        scenarios = [("low", 2.0), ("typical", 8.0), ("high (niche/US)", 25.0)]
    _print(f"📊 Estimated monthly ad revenue for {int(pv):,} pageviews:")
    for label, rpm in scenarios:
        _print(f"   {label:<16} @ ${rpm:>5.1f} RPM  =  ${pv/1000*rpm:,.2f}/mo")
    _print("\nRPM = revenue per 1,000 pageviews. Stacking networks + the sticky "
           "footer + lazy loading typically lifts RPM 20–60%.")
    return 0


_DEMO_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ad Monetization Demo</title>
<style>body{font:16px/1.7 system-ui,sans-serif;max-width:720px;margin:0 auto;padding:24px}
.ad-slot{background:#f3f4f6;border:1px dashed #bbb}.ad-slot:after{content:'(demo ad slot — fills with real ads once you add network IDs)';color:#888;font-size:13px;display:block;padding:30px 8px}</style>
</head><body>
<article>
<h1>Your Article Title</h1>
<p>This is a demo page. The toolkit injected ad slots into the highest-paying
positions and lazy-loads them as you scroll. Add your AdSense/Media.net IDs in
<code>ad_config.yaml</code>, run <code>build</code>, and these slots fill with
paid ads automatically.</p>
""" + "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 40 + """</p>
</article>
</body></html>
"""


COMMANDS = {
    "build": cmd_build,
    "snippet": cmd_snippet,
    "inject": cmd_inject,
    "serve": cmd_serve,
    "estimate": cmd_estimate,
}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        _print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    fn = COMMANDS.get(cmd)
    if not fn:
        _print(f"Unknown command: {cmd}\n")
        _print(__doc__)
        return 1
    return fn(rest) or 0


if __name__ == "__main__":
    sys.exit(main())
