#!/usr/bin/env python3
"""Generate qa-drop/launcher.html with copy-to-clipboard buttons for each QA script."""

import glob
import html
import json
import os
import sys
from datetime import datetime

QA_DIR = "qa-drop"
OUT_FILE = os.path.join(QA_DIR, "launcher.html")


def main():
    scripts = sorted(glob.glob(os.path.join(QA_DIR, "*.md")))
    if not scripts:
        print("No .md files found in qa-drop/", file=sys.stderr)
        sys.exit(1)

    cards = []
    for path in scripts:
        fname = os.path.basename(path)
        with open(path) as f:
            content = f.read()
        safe_id = fname.replace(".", "_").replace("-", "_")
        cards.append({"fname": fname, "content": content, "safe_id": safe_id})

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build button HTML
    btn_html = ""
    for c in cards:
        btn_html += (
            f'<button class="copy-btn" onclick="copyScript(\'{c["safe_id"]}\')">\n'
            f'  <span class="icon">\U0001f4cb</span> Copy {html.escape(c["fname"])}\n'
            f'  <span class="flash" id="flash_{c["safe_id"]}">✓ Copied!</span>\n'
            f'</button>\n'
        )

    # Build JS data
    script_data = ""
    for c in cards:
        script_data += f"SCRIPTS['{c['safe_id']}'] = {json.dumps(c['content'])};\n"

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QA Launcher</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: #1a1a2e; color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  padding: 40px 20px; min-height: 100vh;
}}
h1 {{ text-align: center; font-size: 1.8rem; margin-bottom: 8px; color: #fff; }}
.subtitle {{ text-align: center; color: #888; font-size: 0.9rem; margin-bottom: 32px; }}
.container {{ max-width: 600px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }}
.copy-btn {{
  display: flex; align-items: center; gap: 12px;
  width: 100%; padding: 18px 24px;
  background: #16213e; border: 1px solid #0f3460; border-radius: 12px;
  color: #e0e0e0; font-size: 1.05rem;
  cursor: pointer; transition: all 0.15s ease;
  position: relative; text-align: left;
}}
.copy-btn:hover {{ background: #1a2a50; border-color: #e94560; transform: translateY(-1px); }}
.copy-btn:active {{ transform: translateY(0); }}
.copy-btn .icon {{ font-size: 1.3rem; }}
.copy-btn .flash {{
  display: none; margin-left: auto;
  color: #53d769; font-weight: 600; font-size: 0.95rem;
}}
.copy-btn .flash.show {{ display: inline; }}
.timestamp {{ text-align: center; color: #555; font-size: 0.75rem; margin-top: 32px; }}
</style>
</head>
<body>
<h1>QA Launcher</h1>
<p class="subtitle">Click to copy a QA script to clipboard, then paste into Cowork</p>
<div class="container">
{btn_html}</div>
<p class="timestamp">Generated: {ts}</p>
<script>
var SCRIPTS = {{}};
{script_data}
function copyScript(id) {{
  navigator.clipboard.writeText(SCRIPTS[id]).then(function() {{
    var el = document.getElementById("flash_" + id);
    el.classList.add("show");
    setTimeout(function() {{ el.classList.remove("show"); }}, 1500);
  }});
}}
</script>
</body>
</html>"""

    with open(OUT_FILE, "w") as f:
        f.write(page)

    print(f"✓ {OUT_FILE} generated ({len(cards)} script(s), {ts})")


if __name__ == "__main__":
    main()
