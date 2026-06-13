"""
💉 Injector — drops the ad loader into existing HTML files automatically.

Point it at a folder of .html files and it inserts the loader <script> just
before </head> (or before </body> as a fallback) on every page. Idempotent:
re-running won't add duplicate tags. This is the "barely any effort" path —
one command monetizes an entire static site.
"""

import os
import re

MARKER = "ad-loader.js"   # used to detect already-injected pages


class Injector:
    def __init__(self, loader_url="/ad-loader.js"):
        # Relative URL by default so it works on any domain without editing.
        self.tag = ('<!-- 💰 ad monetization (auto-injected) -->\n'
                    '<script async src="{}"></script>').format(loader_url)

    def _inject_html(self, html):
        if MARKER in html:
            return html, False  # already done
        # Prefer right before </head>; fall back to </body>; else append.
        if re.search(r"</head>", html, re.IGNORECASE):
            return re.sub(r"</head>", self.tag + "\n</head>", html,
                          count=1, flags=re.IGNORECASE), True
        if re.search(r"</body>", html, re.IGNORECASE):
            return re.sub(r"</body>", self.tag + "\n</body>", html,
                          count=1, flags=re.IGNORECASE), True
        return html + "\n" + self.tag + "\n", True

    def inject_file(self, path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        new_html, changed = self._inject_html(html)
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_html)
        return changed

    def inject_path(self, target):
        """Inject into a single file or recursively across a directory."""
        injected, skipped = [], []
        if os.path.isfile(target):
            files = [target]
        else:
            files = []
            for root, _dirs, names in os.walk(target):
                for n in names:
                    if n.lower().endswith((".html", ".htm")):
                        files.append(os.path.join(root, n))
        for fp in files:
            if self.inject_file(fp):
                injected.append(fp)
            else:
                skipped.append(fp)
        return injected, skipped
