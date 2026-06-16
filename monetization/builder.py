"""
💰 AdBuilder — compiles ad_config.yaml into a deployable ad system.

Outputs:
  - dist/ad-loader.js   the single drop-in script you embed on every page
  - dist/snippet.html   the one-line <script> tag to paste into your <head>
  - dist/ads.txt        authorized-sellers file (required by most networks)

Everything is config-driven so adding/removing an ad network is a one-line
edit, not a code change.
"""

import os
import json
import yaml


class AdBuilder:
    # ads.txt lines per network. Keeping them here means `ads.txt` is always
    # in sync with whichever networks you enabled — networks reject your
    # inventory if this file is missing or stale.
    ADS_TXT_TEMPLATES = {
        "adsense":  "google.com, {publisher_id}, DIRECT, f08c47fec0942fa0",
        "medianet": "media.net, {customer_id}, DIRECT",
        "ezoic":    "ezoic.com, {site_id}, DIRECT",
        "propeller": "propellerads.com, {zone_id}, DIRECT",
    }

    def __init__(self, config_path=None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.base = base
        self.config_path = config_path or os.path.join(base, "ad_config.yaml")
        self.tmpl_path = os.path.join(base, "templates", "ad_loader.js.tmpl")
        self.aff_tmpl_path = os.path.join(base, "templates", "affiliate.js.tmpl")
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    # -- helpers --------------------------------------------------------------
    def _output_dir(self):
        out = self.config.get("site", {}).get("output_dir", "monetization/dist")
        if not os.path.isabs(out):
            # resolve relative to the repo root (one level above this package)
            repo_root = os.path.dirname(self.base)
            out = os.path.join(repo_root, out)
        os.makedirs(out, exist_ok=True)
        return out

    def _client_config(self):
        """Flatten the YAML into the compact object the JS loader expects."""
        opt = self.config.get("optimization", {})
        comp = self.config.get("compliance", {})
        placements = []
        for name, p in self.config.get("placements", {}).items():
            if p.get("enabled"):
                placements.append({
                    "placement": name,
                    "selector": p.get("selector", "body"),
                    "position": p.get("position", "beforeend"),
                    "enabled": True,
                })
        return {
            "networks": self.config.get("networks", {}),
            "placements": placements,
            "lazy_load": opt.get("lazy_load", True),
            "lazy_margin_px": opt.get("lazy_margin_px", 600),
            "sticky_footer": opt.get("sticky_footer", True),
            "refresh_seconds": opt.get("refresh_seconds", 0),
            "respect_consent": opt.get("respect_consent", True),
            "min_content_words": opt.get("min_content_words", 0),
            "label_ads": comp.get("label_ads", True),
        }

    def enabled_networks(self):
        return [n for n, c in self.config.get("networks", {}).items()
                if isinstance(c, dict) and c.get("enabled")]

    # -- build steps ----------------------------------------------------------
    def _affiliate_module(self):
        """Return the affiliate JS (config injected), or '' if disabled."""
        aff = self.config.get("affiliate", {})
        if not aff.get("enabled"):
            return ""
        with open(self.aff_tmpl_path, "r", encoding="utf-8") as f:
            tmpl = f.read()
        return tmpl.replace("__AFFILIATE_CONFIG__", json.dumps(aff, indent=2))

    def build_loader(self):
        with open(self.tmpl_path, "r", encoding="utf-8") as f:
            tmpl = f.read()
        cfg_json = json.dumps(self._client_config(), indent=2)
        loader = tmpl.replace("__AD_CONFIG__", cfg_json)

        # Bundle the affiliate income module into the SAME file, so one script
        # tag drives both ads and affiliate revenue.
        aff = self._affiliate_module()
        if aff:
            loader += "\n\n/* ===== bundled affiliate module ===== */\n" + aff

        out = os.path.join(self._output_dir(), "ad-loader.js")
        with open(out, "w", encoding="utf-8") as f:
            f.write(loader)
        return out

    def affiliate_enabled(self):
        return bool(self.config.get("affiliate", {}).get("enabled"))

    def build_ads_txt(self):
        if not self.config.get("compliance", {}).get("generate_ads_txt", True):
            return None
        lines = ["# ads.txt — authorized digital sellers (auto-generated)"]
        nets = self.config.get("networks", {})
        for name, tmpl in self.ADS_TXT_TEMPLATES.items():
            cfg = nets.get(name, {})
            if cfg.get("enabled"):
                try:
                    lines.append(tmpl.format(**cfg))
                except KeyError:
                    pass
        out = os.path.join(self._output_dir(), "ads.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return out

    def snippet(self):
        """The single line you paste into a page <head> to go live."""
        domain = self.config.get("site", {}).get("domain", "example.com")
        return ('<!-- 💰 Ad monetization — paste once, earns on every page -->\n'
                '<script async src="https://{d}/ad-loader.js"></script>').format(d=domain)

    def build_snippet_file(self):
        out = os.path.join(self._output_dir(), "snippet.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(self.snippet() + "\n")
        return out

    def build(self):
        """Build everything. Returns a dict of what was written."""
        result = {
            "loader": self.build_loader(),
            "snippet": self.build_snippet_file(),
            "ads_txt": self.build_ads_txt(),
            "networks": self.enabled_networks(),
            "affiliate": self.affiliate_enabled(),
        }
        return result
