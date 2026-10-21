"""End-to-end test + showcase generator: clicks through the whole ParkRefund demo in a real
browser and writes one screenshot per step to demo/.

    .venv/bin/pip install playwright && .venv/bin/playwright install chromium   # once
    .venv/bin/python demo_walkthrough.py          # starts streamlit itself, mock mode unless .env
    PARKREFUND_MODEL=claude-opus-5-5 .venv/bin/python demo_walkthrough.py   # live, with .env

Exit code 0 = every step rendered. The PNGs are what DEMO.md shows.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent
OUT = REPO / "demo"
PORT = int(os.getenv("PORT", "8599"))
URL = f"http://localhost:{PORT}"
n = 0


def shot(pg, name, full=True):
    global n
    n += 1
    path = OUT / f"{n:02d}_{name}.png"
    pg.screenshot(path=str(path), full_page=full)
    print("✓", path.name)


def pick_sample(pg, text):
    pg.get_by_role("tab", name="Pick a sample case").click()
    time.sleep(0.8)
    combo = pg.get_by_role("combobox").first
    combo.scroll_into_view_if_needed()
    combo.click()
    time.sleep(0.8)
    opt = pg.get_by_role("option").filter(has_text=text)
    if opt.count():
        opt.first.click()
    else:  # fall back to typing into the open select
        pg.keyboard.type(text)
        time.sleep(0.5)
        pg.keyboard.press("Enter")
    time.sleep(2)


def main():
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(REPO / "app.py"), "--server.headless", "true",
         "--server.port", str(PORT), "--browser.gatherUsageStats", "false"],
        cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(5)
        with sync_playwright() as p:
            kw = {"args": ["--no-sandbox"]}
            exe = os.getenv("CHROME_PATH")
            if exe:
                kw["executable_path"] = exe
            b = p.chromium.launch(**kw)
            pg = b.new_page(viewport={"width": 1280, "height": 900})
            pg.goto(URL, wait_until="networkidle")
            pg.get_by_text("Check my case").wait_for(timeout=60000)
            time.sleep(1)
            shot(pg, "landing", full=False)

            pg.set_input_files("input[type=file]", str(REPO / "data/tickets/0_NP-2026-004117.png"))
            time.sleep(4)
            shot(pg, "ticket_uploaded_prefilled")

            pg.get_by_text("Check my case").click()
            pg.get_by_text("What helps you").wait_for(timeout=120000)
            time.sleep(1)
            shot(pg, "verdict_strong")

            pg.get_by_text("Draft my appeal").click()
            pg.get_by_text("Download as .txt").wait_for(timeout=120000)
            time.sleep(1)
            shot(pg, "letter_and_payout")

            pg.reload(wait_until="networkidle")
            pg.get_by_text("Check my case").wait_for(timeout=60000)
            pick_sample(pg, "forgot p-skive")
            pg.get_by_text("Check my case").click()
            pg.get_by_text("What works against you").wait_for(timeout=120000)
            time.sleep(1)
            shot(pg, "verdict_weak_declined")

            pg.goto(f"{URL}/Ops_dashboard", wait_until="networkidle")
            pg.get_by_text("Review queue").wait_for(timeout=60000)
            time.sleep(2)
            shot(pg, "ops_dashboard")
            b.close()
    finally:
        server.terminate()
    print(f"\n{n} steps rendered → {OUT}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
