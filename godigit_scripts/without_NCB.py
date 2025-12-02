#!/usr/bin/env python3
import asyncio
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright
from godigit_bs4 import parse_comprehensive_plan_footer, scrape_idv_block, scrape_plan_card, scrape_policy_durations ,scrape_plan_info ,extract_extra_addons, extract_ncb_percentage_and_value, extract_addon_names, extract_policy_durations, parse_trust_card_numbers_only, parse_popular, parse_popular_pack, parse_addon_pack, extract_cost_breakup_from_html, extract_idv_values

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

# ----------------- PLACE YOUR PARSER FUNCTIONS HERE -----------------
# Either paste your functions below, or import them, for example:
#
from godigit_bs4 import (
    extract_cost_breakup_from_html,
    parse_addon_pack,
    parse_popular_pack,
    parse_popular,
    parse_trust_card_numbers_only,
    extract_policy_durations,
    extract_addon_names,
    extract_ncb_percentage_and_value,
    extract_extra_addons,
    scrape_plan_info,
    scrape_plan_card,
    scrape_policy_durations,
    scrape_idv_block,
    parse_comprehensive_plan_footer,
    extract_idv_values
)
#
# The script will attempt to call these functions if they exist.
# --------------------------------------------------------------------

# ----------------- Utilities -----------------

def ts():
    return datetime.utcnow().isoformat().replace(":", "-").split(".")[0]

def save_file_path(prefix, plan_name, tag):
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(plan_name))[:120]
    filename = f"{prefix}_{safe_name}_{tag}_{ts()}.html"
    return OUTPUT_DIR / filename

def save_json_path(prefix, plan_name, tag):
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(plan_name))[:120]
    filename = f"{prefix}_{safe_name}_{tag}_{ts()}.json"
    return OUTPUT_DIR / filename

async def save_outer_html(page, selector, filepath):
    try:
        if selector is None:
            html = await page.content()
        else:
            loc = page.locator(selector).first
            if await loc.count() == 0:
                # fallback: try querySelector via evaluate
                html = await page.evaluate(f"""() => {{
                    const el = document.querySelector("{selector.replace('"', '\\"')}");
                    return el ? el.outerHTML : null;
                }}""")
                if not html:
                    html = ""
            else:
                handle = await loc.element_handle()
                html = await page.evaluate("(el) => el.outerHTML", handle)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html or "")
        return True
    except Exception as e:
        print(f"⚠ Could not save {selector} -> {filepath}: {e}")
        return False

async def save_full_page_html(page, prefix="plan_page_full"):
    try:
        content = await page.content()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.html"
        filepath = OUTPUT_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[INFO] Full page HTML saved at: {filepath}")
        return filepath
    except Exception as e:
        print(f"⚠ Failed to save full page HTML ({prefix}): {e}")
        return None

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
                await page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
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
            # set value and dispatch events
            await page.evaluate("""
                (el, val) => {
                  el.value = val;
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, handle, value)
    except Exception:
        pass

async def clear_backdrop(page):
    try:
        await page.evaluate("""
        document.querySelectorAll('.modal-backdrop.show').forEach(e => e.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = 'auto';
        """)
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

# Small helper to detect total premium changes (best-effort)
async def _read_total_premium_text(page):
    # Try several common candidate selectors for total premium
    candidates = [
        ".total-premium", ".total-price", ".grand-total", ".premium-amount",
        ".totalPremium", ".total-amount", ".price.total", ".final-price", ".finalPremium"
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                txt = (await loc.inner_text()).strip()
                if txt:
                    return txt
        except Exception:
            pass
    # fallback: try to find any element with "₹" symbol in page
    try:
        html = await page.content()
        # not returning full html; just indicate length as fallback
        return str(len(html))
    except Exception:
        return ""

async def wait_for_premium_update(page, prev_value=None, timeout_s=12):
    # If prev_value not provided, read once and then wait for change
    try:
        start = datetime.utcnow()
        if prev_value is None:
            prev_value = await _read_total_premium_text(page)
        for _ in range(timeout_s * 2):
            await page.wait_for_timeout(500)
            cur = await _read_total_premium_text(page)
            if cur != prev_value:
                return cur
        return prev_value
    except Exception:
        await page.wait_for_timeout(2000)
        return None

# ----------------- Page actions -----------------

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
            timeout=15000
        )
    except Exception:
        print("⚠ Button stayed disabled; proceeding anyway")
    try:
        await page.evaluate(
            "(el) => el.scrollIntoView({behavior:'instant', block:'center'})",
            await btn.element_handle()
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
        km_option = km_modal.locator("input.kmRangeRadio").first
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
        # don't rely on networkidle; small pause instead
        await page.wait_for_timeout(1500)
        print("[9] Plan page loaded!")
    except Exception:
        print("⚠ Plan page did not load in time")
        await clear_backdrop(page)
    return plan_section

# ----------------- NEW STEPS YOU REQUESTED -----------------

async def handle_pa_owner_cover(page):
    print("[A] Handling PA Owner Cover…")
    # prefer id-based selection if present
    try:
        # wait for wrapper or id
        await page.wait_for_timeout(500)
        # try by id first
        if await page.locator("input#paOwner").count() > 0:
            checkbox = page.locator("input#paOwner")
            prev = await _read_total_premium_text(page)
            await click_force_js(page, checkbox)
            await wait_for_premium_update(page, prev)
            print("[A] Clicked input#paOwner")
            await save_full_page_html(page, prefix="pa_owner_after_click")
            return
        # fallback: wrapper then checkbox inside
        wrapper = page.locator("#pa-cover, .extra-package-addon.pa-owner-cover-section, .package-addon-pa-owner")
        await wrapper.first.wait_for(state="visible", timeout=15000)
        cb = wrapper.locator("input[type='checkbox']").first
        if await cb.count() > 0:
            prev = await _read_total_premium_text(page)
            await click_force_js(page, cb)
            await wait_for_premium_update(page, prev)
            await save_full_page_html(page, prefix="pa_owner_after_click")
            print("[A] Clicked PA owner fallback checkbox")
            return
    except Exception as e:
        print(f"[A] PA owner cover step failed: {e}")

async def handle_motor_idv_and_edit_icons(page):
    print("[B] Handling motor-idv-content -> find edit icons -> click each and save HTML")
    try:
        # wait for motor idv content
        midv = page.locator(".motor-idv-content, .idv-mob-des")
        await midv.first.wait_for(state="visible", timeout=20000)
        await page.wait_for_timeout(500)
    except Exception:
        print("⚠ motor-idv-content not found (continuing)")
    try:
        # find containers that often wrap edit icons (use stable part)
        containers = page.locator(".ng-tns-c136-2, .idv-edit-container, .idv-section")
        # if none, fallback to body
        if await containers.count() == 0:
            containers = page.locator("body")
        count = await containers.count()
        # search for edit icons globally
        edit_icons = page.locator(".editIcon, .select-btn, .edit-icon, .edit-btn")
        ecount = await edit_icons.count()
        if ecount == 0:
            # try a more specific class used in your description
            edit_icons = page.locator(".editIcon.ml-auto.select-btn.font-extrabold.text-xs")
            ecount = await edit_icons.count()
        for i in range(ecount):
            try:
                icon = edit_icons.nth(i)
                await click_force_js(page, icon)
                await page.wait_for_timeout(1000)
                await save_full_page_html(page, prefix=f"idv_editicon_{i}")
                print(f"[B] clicked edit icon #{i} and saved html")
            except Exception as e:
                print(f"[B] clicking edit icon #{i} failed: {e}")
    except Exception as e:
        print(f"[B] motor idv / edit icons step failed: {e}")

async def handle_select_modal_and_choose(page):
    print("[C] Click Select button and choose radio in modal")
    try:
        # click first 'Select' button visible
        select_btn = page.locator("button:has-text('Select'), .select-button, button.select")
        if await select_btn.count() == 0:
            print("⚠ No select button found")
            return
        await click_force_js(page, select_btn.first)
        # wait for modal
        modal = page.locator(".ng-tns-c60-45, .zd-modal, .zd-popup, .modal")
        await modal.first.wait_for(state="visible", timeout=15000)
        await page.wait_for_timeout(500)
        # choose the preferred radio option
        radio = modal.locator(".zdPopUpRadioButton.previousZdOpt, .zdPopUpRadioButton, input[type='radio']")
        if await radio.count() > 0:
            prev = await _read_total_premium_text(page)
            await click_force_js(page, radio.first)
            await page.wait_for_timeout(300)
            await wait_for_premium_update(page, prev)
            await save_full_page_html(page, prefix="select_modal_after_choice")
            print("[C] Modal option selected and premium updated")
        else:
            print("⚠ No radio option found in modal")
    except Exception as e:
        print(f"[C] select modal step failed: {e}")

async def handle_ncb_protector_addon(page):
    print("[D] Handling NCB Protector Add-on")
    try:
        # wait for add-on list wrapper
        addon_wrappers = page.locator(".pl-2_5.desktop-idv-content.add-on-list, .add-on-list, .desktop-idv-content.add-on-list")
        if await addon_wrappers.count() == 0:
            # try a more general wrapper
            addon_wrappers = page.locator(".pl-2_5, .desktop-idv-content, .add-on-wrap")
        if await addon_wrappers.count() > 0:
            wrapper = addon_wrappers.first
            await wrapper.wait_for(state="visible", timeout=15000)
            # try id-based checkbox
            if await page.locator("input#ncb-protector").count() > 0:
                cb = page.locator("input#ncb-protector")
                prev = await _read_total_premium_text(page)
                await click_force_js(page, cb)
                await wait_for_premium_update(page, prev)
                await save_full_page_html(page, prefix="ncb_protector_after_click")
                print("[D] Clicked #ncb-protector")
                return
            # fallback: find grey-border tab-key-border checkbox inside wrapper
            cb2 = wrapper.locator("input.grey-border.tab-key-border, .grey-border.tab-key-border input[type='checkbox'], input[type='checkbox']")
            if await cb2.count() > 0:
                prev = await _read_total_premium_text(page)
                await click_force_js(page, cb2.first)
                await wait_for_premium_update(page, prev)
                await save_full_page_html(page, prefix="ncb_protector_after_click_fallback")
                print("[D] Clicked addon checkbox fallback")
                return
        else:
            print("⚠ addon wrapper not found")
    except Exception as e:
        print(f"[D] ncb protector step failed: {e}")

async def capture_addon_section_html(page):
    print("[E] Capturing addon section HTML")
    try:
        selector = ".pl-2_5.desktop-idv-content.add-on-list, .desktop-idv-content.add-on-list, .add-on-list"
        path = OUTPUT_DIR / f"addon_section_{ts()}.html"
        await save_outer_html(page, selector, path)
        print("[E] Addon section saved:", path)
    except Exception as e:
        print(f"[E] capture addon html failed: {e}")

async def handle_footer_capture(page):
    print("[F] Capturing footer card HTML and clicking footer-card")
    try:
        footer = page.locator(".footer-card, .footer-card-container, .footer-card-wrapper")
        await footer.first.wait_for(state="visible", timeout=20000)
        # click footer if interactive
        try:
            await click_force_js(page, footer.first)
        except Exception:
            pass
        path = OUTPUT_DIR / f"footer_card_{ts()}.html"
        await save_outer_html(page, ".footer-card, .footer-card-container, .footer-card-wrapper", path)
        print("[F] Footer card saved:", path)
    except Exception as e:
        print(f"[F] footer capture failed: {e}")

# ----------------- MASTER FUNCTION TO RUN ALL NEW STEPS -----------------

async def run_additional_steps(page):
    # 1. PA owner cover checkbox
    await handle_pa_owner_cover(page)
    # 2. motor idv content and edit icons
    await handle_motor_idv_and_edit_icons(page)
    # 3. select modal and choose
    await handle_select_modal_and_choose(page)
    # 4. ncb protector addon
    await handle_ncb_protector_addon(page)
    # 5. capture addon section html
    await capture_addon_section_html(page)
    # 6. footer capture and click
    await handle_footer_capture(page)
    print("[✔] All extra steps completed")

# ----------------- MAIN -----------------

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # optional stealth injection (uncomment if needed)
        try:
            await page.add_init_script(STEALTH_JS)
        except Exception:
            pass

        print("[OPENING WEBSITE]")
        await page.goto(BASE_URL)
        # small pause to let angular start rendering
        await page.wait_for_timeout(2000)
        # ensure cloudflare check passed
        try:
            await wait_for_cloudflare(page)
        except Exception:
            pass

        # run original working steps
        await click_car_insurance_tab(page)
        await fill_registration_number(page)
        await fill_mobile_number(page)
        await click_view_prices(page)
        await handle_km_modal(page)
        await wait_for_plan_page(page)

        # save full page after landing on plan page (optional)
        await save_full_page_html(page, prefix="plan_page_landed")

        # run new steps requested by you
        await run_additional_steps(page)

        print("🎉 Script Completed")
        try:
            await context.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
