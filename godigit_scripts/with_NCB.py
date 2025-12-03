#!/usr/bin/env python3
import asyncio
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright
from godigit_bs4 import (
    parse_comprehensive_plan_footer,
    scrape_idv_block,
    scrape_plan_card,
    scrape_policy_durations,
    scrape_plan_info,
    extract_extra_addons,
    extract_ncb_percentage_and_value,
    extract_addon_names,
    extract_policy_durations,
    parse_trust_card_numbers_only,
    parse_popular,
    parse_popular_pack,
    parse_addon_pack,
    extract_cost_breakup_from_html,
    extract_idv_values,
    extract_cost_breakup_from_html as _dup_placeholder,  # keep import parity
)

# ----------------- CONFIG -----------------
BASE_URL = "https://www.godigit.com/"
REG_NO = "MH04KW1827"
MOBILE = "8712345645"

OUTPUT_DIR = Path("./godigit_snapshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
delete navigator.__proto__.webdriver;
"""

# ----------------- Utilities -----------------


def ts():
    return datetime.utcnow().isoformat().replace(":", "-").split(".")[0]


def safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(name))[:120]


def save_file_path(prefix, plan_name, tag):
    safe = safe_name(plan_name)
    filename = f"{prefix}_{safe}_{tag}_{ts()}.html"
    return OUTPUT_DIR / filename


def save_json_path(prefix, plan_name, tag):
    safe = safe_name(plan_name)
    filename = f"{prefix}_{safe}_{tag}_{ts()}.json"
    return OUTPUT_DIR / filename


async def save_string_to_file(text, filepath):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text or "")
        return True
    except Exception as e:
        print(f"⚠ Could not save text to {filepath}: {e}")
        return False


async def click_force_js(page, locator):
    for attempt in range(5):
        try:
            await locator.click(timeout=2000)
            return True
        except Exception:
            pass
        try:
            box = await locator.bounding_box()
            if box:
                await page.mouse.click(
                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                )
                return True
        except Exception:
            pass
        try:
            handle = await locator.element_handle()
            if handle:
                await page.evaluate("(el) => el.click()", handle)
                return True
        except Exception:
            pass
        await page.wait_for_timeout(500)
    return False


async def fill_force_js(page, locator, value):
    try:
        await locator.fill(value)
        return
    except Exception:
        pass
    try:
        handle = await locator.element_handle()
        if handle:
            await page.evaluate(
                """
                (el, val) => {
                  el.value = val;
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """,
                handle,
                value,
            )
    except Exception:
        pass


async def clear_backdrop(page):
    try:
        await page.evaluate(
            """
        document.querySelectorAll('.modal-backdrop.show').forEach(e => e.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = 'auto';
        """
        )
        await page.wait_for_timeout(300)
    except Exception:
        pass


async def wait_for_cloudflare(page, timeout_s=30):
    for _ in range(timeout_s):
        html = (await page.content()).lower()
        if "checking your browser" not in html:
            return True
        if await page.locator("#car-tab").count() > 0:
            return True
        await page.wait_for_timeout(1000)
    print("⚠ Cloudflare check timeout")
    return False


# Helper: try multiple selectors to read the total premium shown on page
async def get_total_premium_text(page):
    selectors = [
        ".total-premium",
        ".totalPremium",
        ".premium-amount",
        ".total-amount",
        ".grand-total .amount",
        ".footer-card .price",
        ".footer-card-container .price",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                txt = (await loc.inner_text()).strip()
                if txt:
                    return txt
        except Exception:
            pass
    # fallback: try to find any element with "₹" and reasonable text length
    try:
        els = page.locator("text=/₹|INR|rs\\.?/i")
        if await els.count() > 0:
            for i in range(min(els.count(), 8)):
                try:
                    t = (await els.nth(i).inner_text()).strip()
                    if len(t) < 80 and any(ch.isdigit() for ch in t):
                        return t
                except Exception:
                    pass
    except Exception:
        pass
    return None


async def wait_for_premium_change(page, before_text, timeout_s=8):
    # If before_text is None, just wait a short fixed time
    if before_text is None:
        await page.wait_for_timeout(1200)
        return True
    for _ in range(int(timeout_s * 2)):  # poll every 500ms
        await page.wait_for_timeout(500)
        now = await get_total_premium_text(page)
        if now is None:
            continue

        # compare normalized digits only
        def norm(s):
            return "".join(ch for ch in (s or "") if ch.isdigit())

        if norm(now) != norm(before_text):
            return True
    return False


# ----------------- Page actions (original working steps) -----------------


async def click_car_insurance_tab(page):
    print("[1] Clicking Car Insurance tab…")
    tab = page.locator("#car-tab")
    await page.wait_for_timeout(500)
    await click_force_js(page, tab)
    await page.wait_for_timeout(1000)


async def fill_registration_number(page):
    print("[2] Filling vehicle registration…")
    try:
        locator = page.locator("input#car-registration-number")
        await locator.wait_for(timeout=15000)
        await fill_force_js(page, locator, REG_NO)
        return
    except Exception:
        pass
    try:
        textbox = page.get_by_role("textbox", name="E.g. KA04DK8337")
        await fill_force_js(page, textbox, REG_NO)
    except Exception:
        print("❌ Could not find registration input.")


async def fill_mobile_number(page):
    print("[3] Filling mobile number…")
    try:
        locator = page.locator("#mobile")
        await locator.wait_for(timeout=15000)
        await fill_force_js(page, locator, MOBILE)
        return
    except Exception:
        pass
    try:
        textbox = page.get_by_role("textbox", name="Enter Mobile Number")
        await fill_force_js(page, textbox, MOBILE)
    except Exception:
        print("❌ Could not find mobile input.")


async def click_view_prices(page):
    print("[4] Clicking View Prices…")
    btn = page.locator("button#get-quote-btn[ng-click*='carWheelerCtrl']")
    if await btn.count() == 0:
        try:
            btn = page.get_by_role("button", name="View Prices").filter(
                has=page.locator("[ng-click*='carWheelerCtrl']")
            )
        except Exception:
            pass
    try:
        await btn.wait_for(state="attached", timeout=15000)
    except Exception:
        print("⚠ View Prices button not present/attached")
    try:
        el_handle = await btn.element_handle()
        await page.wait_for_function(
            """(el) => el && !el.disabled && !el.classList.contains('btn-loading')""",
            arg=el_handle,
            timeout=15000,
        )
    except Exception:
        print("⚠ Button stayed disabled; proceeding anyway")
    try:
        await page.evaluate(
            "(el) => el.scrollIntoView({behavior:'instant', block:'center'})",
            await btn.element_handle(),
        )
    except Exception:
        pass
    await clear_backdrop(page)
    clicked = await click_force_js(page, btn)
    if clicked:
        print("[5] View Prices clicked")
        await page.wait_for_timeout(1500)
        return True
    print("❌ Could not click 'View Prices'.")
    return False


async def handle_km_modal(page):
    print("[6] Checking for KM modal…")
    try:
        km_modal = page.locator(".sticky.motor-question-modal")
        await km_modal.wait_for(state="visible", timeout=15000)
        km_option = km_modal.locator(
            "input.kmRangeRadio[value='0-4000 km (0-10 km/day)']"
        )
        await click_force_js(page, km_option)
        submit_btn = km_modal.locator("button:has-text('Continue')")
        if await submit_btn.count() > 0:
            await click_force_js(page, submit_btn)
            await page.wait_for_timeout(800)
        print("[7] KM modal answered")
    except Exception:
        print("⚠ KM modal not found — continuing…")


async def wait_for_plan_page(page):
    print("[8] Waiting for Plan Page to load…")
    plan_section = page.locator(".plans-container, .plan-cards, .plan-cards-wrapper")
    try:
        await plan_section.first.wait_for(state="visible", timeout=45000)
        # avoid networkidle because Angular keeps polling
        await page.wait_for_timeout(1200)
        print("[9] Plan page loaded!")
    except Exception:
        print("⚠ Plan page did not load in time")
        await clear_backdrop(page)
    return plan_section


# ----------------- Additional steps you requested (Option A selectors) -----------------


async def capture_multiyear_addon(page):
    sel = ".desktop-idv-content-multiyear"
    print(f"[STEP] Waiting for multiyear block ({sel})")
    try:
        block = page.locator(sel).first
        await block.wait_for(state="visible", timeout=30000)
        html = await block.inner_html()
        path = OUTPUT_DIR / f"multiyear_addon_{ts()}.html"
        path.write_text(html, encoding="utf-8")
        print("[SAVED] multiyear_addon ->", path)
    except Exception as e:
        print("⚠ multiyear block not found:", e)


async def capture_motor_idv_content(page):
    sel = ".motor-idv-content"
    print(f"[STEP] Waiting for motor idv block ({sel})")
    try:
        block = page.locator(sel).first
        await block.wait_for(state="visible", timeout=30000)
        html = await block.inner_html()
        path = OUTPUT_DIR / f"motor_idv_content_{ts()}.html"
        path.write_text(html, encoding="utf-8")
        print("[SAVED] motor_idv_content ->", path)
    except Exception as e:
        print("⚠ motor idv block not found:", e)


async def capture_desktop_idv_addon_wrap(page):
    sel = ".desktop-idv-content.add-on-wrap"
    print(f"[STEP] Waiting for desktop idv add-on wrap ({sel})")
    try:
        block = page.locator(sel).first
        await block.wait_for(state="visible", timeout=30000)
        html = await block.inner_html()
        path = OUTPUT_DIR / f"desktop_idv_addon_wrap_{ts()}.html"
        path.write_text(html, encoding="utf-8")
        print("[SAVED] desktop_idv_addon_wrap ->", path)
    except Exception as e:
        print("⚠ desktop idv addon wrap not found:", e)


async def click_checkbox_label_sequence(page):
    sel = ".checkbox-label"
    print(f"[STEP] Clicking checkbox-label items ({sel}) sequentially")
    try:
        locs = page.locator(sel)
        count = await locs.count()
        print(f"[INFO] Found {count} checkbox-label elements")
        for i in range(count):
            try:
                before = await get_total_premium_text(page)
                el = locs.nth(i)
                await click_force_js(page, el)
                changed = await wait_for_premium_change(page, before, timeout_s=8)
                print(f" - clicked checkbox-label {i} changed={changed}")
            except Exception as e:
                print(f" ⚠ error clicking checkbox-label {i}: {e}")
    except Exception as e:
        print("⚠ checkbox-label sequence failed:", e)


async def click_price_rows(page):
    sel = ".price"
    print(f"[STEP] Clicking price rows ({sel}) sequentially")
    try:
        locs = page.locator(sel)
        count = await locs.count()
        print(f"[INFO] Found {count} price elements")
        for i in range(count):
            try:
                before = await get_total_premium_text(page)
                el = locs.nth(i)
                await click_force_js(page, el)
                changed = await wait_for_premium_change(page, before, timeout_s=6)
                print(f" - clicked price {i} changed={changed}")
            except Exception as e:
                print(f" ⚠ error clicking price {i}: {e}")
    except Exception as e:
        print("⚠ price rows click failed:", e)


async def click_checkbox_subcover_sequence(page):
    sel = ".checkbox-subcover"
    print(f"[STEP] Clicking checkbox-subcover items ({sel}) sequentially")
    try:
        locs = page.locator(sel)
        count = await locs.count()
        print(f"[INFO] Found {count} checkbox-subcover elements")
        for i in range(count):
            try:
                before = await get_total_premium_text(page)
                el = locs.nth(i)
                await click_force_js(page, el)
                changed = await wait_for_premium_change(page, before, timeout_s=8)
                print(f" - clicked checkbox-subcover {i} changed={changed}")
            except Exception as e:
                print(f" ⚠ error clicking checkbox-subcover {i}: {e}")
    except Exception as e:
        print("⚠ checkbox-subcover sequence failed:", e)


async def capture_footer_container(page):
    sel = ".footer-card-container"
    print(f"[STEP] Capturing footer container ({sel})")
    try:
        block = page.locator(sel).first
        await block.wait_for(state="visible", timeout=30000)
        html = await block.inner_html()
        path = OUTPUT_DIR / f"footer_card_{ts()}.html"
        path.write_text(html, encoding="utf-8")
        print("[SAVED] footer_card ->", path)
    except Exception as e:
        print("⚠ footer container not found:", e)


# ----------------- MASTER function to run all new steps -----------------


async def run_additional_steps(page):
    await capture_multiyear_addon(page)
    await capture_motor_idv_content(page)
    await capture_desktop_idv_addon_wrap(page)

    # click sequence: checkbox-label (several), price rows, subcovers, and again checkboxes if present
    await click_checkbox_label_sequence(page)
    await click_price_rows(page)
    await click_checkbox_subcover_sequence(page)

    # second pass on checkbox labels to catch any newly revealed ones
    await click_checkbox_label_sequence(page)

    await capture_footer_container(page)


# ----------------- MAIN -----------------


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # add stealth JS to page
        try:
            await page.add_init_script(STEALTH_JS)
        except Exception:
            pass

        print("[OPEN] Navigating to base URL")
        await page.goto(BASE_URL)
        # small wait to allow angular bootstrap and initial rendering
        await page.wait_for_timeout(2500)
        # ensure cloudflare check cleared
        try:
            await wait_for_cloudflare(page)
        except Exception:
            pass

        # ORIGINAL WORKING FLOW (kept intact)
        await click_car_insurance_tab(page)
        await fill_registration_number(page)
        await fill_mobile_number(page)
        await click_view_prices(page)
        await handle_km_modal(page)
        await wait_for_plan_page(page)

        # Save a snapshot of the plan page before additional interactions
        # await save_full_page_html(page, prefix="plan_page_before_addons")

        # RUN added steps
        await run_additional_steps(page)

        # Save final snapshot
        # await save_full_page_html(page, prefix="plan_page_after_addons")

        print("✔ Script finished")

        try:
            await context.close()
            await browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
