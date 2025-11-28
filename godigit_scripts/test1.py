#!/usr/bin/env python3
import asyncio
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

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

def ts():
    return datetime.utcnow().isoformat().replace(":", "-").split(".")[0]

def save_file_path(prefix, plan_name, tag):
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in plan_name)[:120]
    filename = f"{prefix}_{safe_name}_{tag}_{ts()}.html"
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
        km_option = km_modal.locator("input.kmRangeRadio[value='0-4000 km (0-10 km/day)']")
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
    # Combined selectors that may represent the plan list / plan cards
    plan_section = page.locator(".plans-container, .plan-cards, .plan-cards-wrapper")
    try:
        await plan_section.first.wait_for(state="visible", timeout=45000)
        await page.wait_for_load_state("networkidle")
        print("[9] Plan page loaded!")
    except Exception:
        print("⚠ Plan page did not load in time")
        await clear_backdrop(page)
    return plan_section

# ----------------- Snapshot helpers -----------------

async def snapshot_addon_blocks(page, plan_tag, manifest_entry):
    """
    Capture:
    - Select add on package block (the add-on package container)
    - Popular pack (5 add-on) block
    - Popular+ pack (6 add-on) block
    - Ultimate pack (8 add-on) block
    - Total Premium (Incl. GST) (the total premium container)
    """
    blocks = {
        "select_add_on_package": ".add-on-package, .select-add-on-package, .add-on-cls",
        "popular_pack_5": ".popular-pack, .popular-pack-5",
        "popular_plus_pack_6": ".popular-plus-pack, .popular-plus-pack-6",
        "ultimate_pack_8": ".ultimate-pack, .ultimate-pack-8",
        "total_premium_incl_gst": ".total-premium, .total-premium-incl-gst, .premium-total, .prem-break"
    }
    saved = {}
    for tag, selector in blocks.items():
        path = save_file_path("addon", plan_tag, tag)
        ok = await save_outer_html(page, selector, path)
        if ok:
            saved[tag] = path.name
            manifest_entry.setdefault("snapshots", {}).setdefault("addon_blocks", {})[tag] = {
                "file": path.name,
                "selector": selector,
                "ts": ts()
            }
        else:
            manifest_entry.setdefault("snapshots", {}).setdefault("addon_blocks", {})[tag] = {
                "file": None, "selector": selector, "ts": ts()
            }
    return saved

# ----------------- Plan processing -----------------

async def wait_for_and_click(selector, page, description="", timeout=15000):
    try:
        loc = page.locator(selector)
        await loc.wait_for(state="attached", timeout=timeout)
        await page.wait_for_timeout(200)
        return await click_force_js(page, loc)
    except Exception as e:
        print(f"⚠ Could not click {description} ({selector}): {e}")
        return False

async def process_plan(page, plan_index, plan_name, manifest, plan_locator=None):
    """
    Processes a single plan: snapshot, toggle NCB if present, click continue, capture modal, capture cost-breakup expanded, return breadcrumb to plan list.
    plan_locator: optional locator pointing to the plan-card wrapper (useful to scope selectors)
    """
    print(f"\n--- Processing plan #{plan_index} : {plan_name} ---")
    manifest_entry = {
        "plan_index": plan_index,
        "plan_name": plan_name,
        "actions": [],
        "snapshots": {},
    }

    # Save full page before interacting
    page_snapshot_path = save_file_path("fullpage", plan_name, "before_continue")
    await save_outer_html(page, None, page_snapshot_path)
    manifest_entry["snapshots"]["fullpage_before"] = {
        "file": page_snapshot_path.name, "ts": ts()
    }

    # Save addon blocks
    await snapshot_addon_blocks(page, plan_name, manifest_entry)

    # Try to click NCB protector checkbox within this plan context
    ncb_selector = "#ncb-protector-addon"
    ncb_locator = None
    try:
        # If plan_locator is provided, search inside it
        if plan_locator:
            ncb_locator = plan_locator.locator(ncb_selector)
            if await ncb_locator.count() == 0:
                ncb_locator = None
        if ncb_locator is None:
            ncb_locator = page.locator(ncb_selector)
        if await ncb_locator.count() > 0:
            await click_force_js(page, ncb_locator.first)
            manifest_entry["actions"].append({"action": "toggle_ncb", "selector": ncb_selector, "ts": ts()})
            await page.wait_for_timeout(700)
            print("✔ NCB protector clicked (if present)")
        else:
            print("ℹ NCB protector not found for this plan.")
            manifest_entry["actions"].append({"action": "ncb_not_found", "selector": ncb_selector, "ts": ts()})
    except Exception as e:
        print(f"⚠ Error toggling NCB: {e}")
        manifest_entry["actions"].append({"action": "ncb_error", "error": str(e), "ts": ts()})

    # Save page after NCB toggle (so we have updated addon HTML)
    page_snapshot_path2 = save_file_path("fullpage", plan_name, "after_ncb")
    await save_outer_html(page, None, page_snapshot_path2)
    manifest_entry["snapshots"]["fullpage_after_ncb"] = {"file": page_snapshot_path2.name, "ts": ts()}

    # Save the addon blocks again (updated)
    await snapshot_addon_blocks(page, plan_name + "_after_ncb", manifest_entry)

    # Click continue button
    continue_selector = "button#continue-btn.btn-digit.btn-primary.btn-footer.tab-key-cta-bg-color"
    cont_ok = await wait_for_and_click(continue_selector, page, description="Continue button")
    manifest_entry["actions"].append({"action": "click_continue", "selector": continue_selector, "success": cont_ok, "ts": ts()})
    if not cont_ok:
        print("❌ Continue button click failed; attempting fallback selectors")
        # fallback: button with id continue-btn
        cont_ok = await wait_for_and_click("button#continue-btn", page, description="Continue (fallback)")
        manifest_entry["actions"][-1]["fallback_click"] = cont_ok

    # Wait for modal
    modal_selector = ".ng-star-inserted"
    try:
        modal_loc = page.locator(modal_selector).filter(has=page.locator(".vehicle-details-submit"))
        await modal_loc.first.wait_for(state="visible", timeout=15000)
        modal_path = save_file_path("modal", plan_name, "vehicle_modal")
        await save_outer_html(page, modal_selector, modal_path)
        manifest_entry["snapshots"]["modal"] = {"file": modal_path.name, "selector": modal_selector, "ts": ts()}
        print("✔ Modal appeared and saved")
    except Exception:
        # Try to find any modal-like element
        try:
            modal_any = page.locator(".modal, .ng-star-inserted")
            if await modal_any.count() > 0:
                modal_path = save_file_path("modal", plan_name, "vehicle_modal_fallback")
                await save_outer_html(page, ".modal, .ng-star-inserted", modal_path)
                manifest_entry["snapshots"]["modal"] = {"file": modal_path.name, "selector": ".modal, .ng-star-inserted", "ts": ts()}
        except Exception:
            print("⚠ Modal not found after clicking continue")
            manifest_entry["snapshots"]["modal"] = {"file": None, "ts": ts()}

    # Click confirm/submit inside modal
    try:
        confirm_btn = page.locator(".vehicle-details-submit")
        if await confirm_btn.count() > 0:
            await click_force_js(page, confirm_btn.first)
            manifest_entry["actions"].append({"action": "modal_confirm_click", "selector": ".vehicle-details-submit", "ts": ts()})
            await page.wait_for_timeout(1200)
        else:
            manifest_entry["actions"].append({"action": "modal_confirm_not_found", "selector": ".vehicle-details-submit", "ts": ts()})
    except Exception as e:
        print(f"⚠ Could not click modal confirm: {e}")
        manifest_entry["actions"].append({"action": "modal_confirm_error", "error": str(e), "ts": ts()})

    # Wait for cost-breakup card
    cost_breakup_selector = ".cost-breakup-card-title.ng-tns-c125-166"
    try:
        cb_loc = page.locator(cost_breakup_selector)
        await cb_loc.first.wait_for(state="visible", timeout=20000)
        manifest_entry["actions"].append({"action": "cost_breakup_appeared", "selector": cost_breakup_selector, "ts": ts()})
        print("✔ Cost-breakup card appeared")
    except Exception:
        print("⚠ Cost-breakup card did not appear in time")
        manifest_entry["actions"].append({"action": "cost_breakup_not_found", "selector": cost_breakup_selector, "ts": ts()})

    # Click the cost-breakup expand icon (try several possible classes)
    expand_selector = ".material-icons-outlined.notranslate.tab-key-border.ng-tns-c125-166.ng-star-inserted, .material-icons-outlined.notranslate"
    try:
        expand_loc = page.locator(expand_selector)
        if await expand_loc.count() > 0:
            await click_force_js(page, expand_loc.first)
            await page.wait_for_timeout(700)
            manifest_entry["actions"].append({"action": "expand_cost_breakup", "selector": expand_selector, "ts": ts()})
            print("✔ Expanded cost-breakup")
        else:
            manifest_entry["actions"].append({"action": "expand_selector_not_found", "selector": expand_selector, "ts": ts()})
    except Exception as e:
        print(f"⚠ Could not expand cost-breakup: {e}")
        manifest_entry["actions"].append({"action": "expand_error", "error": str(e), "ts": ts()})

    # Save expanded breakup HTML and full page after expansion
    try:
        breakup_card_selector = ".cost-breakup-card, .cost-breakup-card-title.ng-tns-c125-166"
        breakup_path = save_file_path("breakup", plan_name, "expanded")
        await save_outer_html(page, breakup_card_selector, breakup_path)
        manifest_entry["snapshots"]["breakup_expanded"] = {"file": breakup_path.name, "selector": breakup_card_selector, "ts": ts()}
        full_after_expand_path = save_file_path("fullpage", plan_name, "after_expand")
        await save_outer_html(page, None, full_after_expand_path)
        manifest_entry["snapshots"]["fullpage_after_expand"] = {"file": full_after_expand_path.name, "ts": ts()}
    except Exception as e:
        print(f"⚠ Could not save expanded breakup/html: {e}")

    # Click breadcrumb to return to plan page (if exists)
    try:
        breadcrumb_selector = ".choose-details-bredcrumb-text.ng-tns-c125-271"
        bc_loc = page.locator(breadcrumb_selector)
        if await bc_loc.count() > 0:
            await click_force_js(page, bc_loc.first)
            await page.wait_for_timeout(1100)
            manifest_entry["actions"].append({"action": "breadcrumb_click", "selector": breadcrumb_selector, "ts": ts()})
            print("✔ Breadcrumb clicked to return to plan list")
        else:
            manifest_entry["actions"].append({"action": "breadcrumb_not_found", "selector": breadcrumb_selector, "ts": ts()})
    except Exception as e:
        print(f"⚠ Could not click breadcrumb: {e}")
        manifest_entry["actions"].append({"action": "breadcrumb_error", "error": str(e), "ts": ts()})

    # Save manifest entry and return
    manifest.append(manifest_entry)
    # persist manifest each plan
    with open(MANIFEST_PATH, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)
    return True

# ----------------- High-level flow -----------------

async def main():
    manifest = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # set headless=True if desired
        context = await browser.new_context()
        page = await context.new_page()

        # Stealth script injection
        try:
            await page.add_init_script(STEALTH_JS)
        except Exception:
            pass

        print("Navigating to base url...")
        await page.goto(BASE_URL)
        await wait_for_cloudflare(page)

        # Interact with the initial form
        try:
            await click_car_insurance_tab(page)
        except Exception as e:
            print(f"⚠ Could not click car tab: {e}")
        await fill_registration_number(page)
        await fill_mobile_number(page)
        view_ok = await click_view_prices(page)
        if not view_ok:
            print("Exiting due to inability to click View Prices.")
            await browser.close()
            return

        await handle_km_modal(page)

        # Wait for plan page to load
        await wait_for_plan_page(page)

        # Wait for the specific first plan info element
        first_plan_info_selector = ".ng-tns-c137-84.plan-info.ng-star-inserted#ComprehensiveWithPiCoverPlanInfo"
        try:
            if await page.locator(first_plan_info_selector).count() > 0:
                first_plan_loc = page.locator(first_plan_info_selector).first
                print("First (ComprehensiveWithPiCoverPlanInfo) plan found.")
            else:
                # fallback to any plan-info
                first_plan_loc = page.locator(".plan-info").first
                print("Fallback to first .plan-info")
        except Exception:
            first_plan_loc = page.locator(".plan-info").first

        # Process first plan (index 1)
        try:
            await process_plan(page, 1, "ComprehensiveWithPiCoverPlanInfo", manifest, plan_locator=first_plan_loc)
        except Exception as e:
            print(f"⚠ Error processing first plan: {e}")

        # Wait and find second comprehensive plan by id
        second_plan_info_selector = ".ng-tns-c137-294.plan-info.ng-star-inserted#ComprehensiveCoverPlanInfo"
        try:
            if await page.locator(second_plan_info_selector).count() > 0:
                second_plan_loc = page.locator(second_plan_info_selector).first
                print("Second comprehensive plan found.")
            else:
                second_plan_loc = page.locator("#ComprehensiveCoverPlanInfo").first
        except Exception:
            second_plan_loc = None

        if second_plan_loc:
            # Ensure the plan card is active/select it
            try:
                plan_card_selector = ".plan-card.plan-card-des.tab-key-border.ng-tns-c137-294.ng-star-inserted.active"
                if await page.locator(plan_card_selector).count() == 0:
                    # try clicking its plan-card wrapper (search by id sibling)
                    wrapper = second_plan_loc.locator("xpath=ancestor::div[contains(@class,'plan-card')]")
                    if await wrapper.count() > 0:
                        await click_force_js(page, wrapper.first)
                        await page.wait_for_timeout(800)
                await process_plan(page, 2, "ComprehensiveCoverPlanInfo", manifest, plan_locator=second_plan_loc)
            except Exception as e:
                print(f"⚠ Error processing second plan: {e}")
        else:
            print("ℹ Second comprehensive plan not found; continuing to scroll plans")

        # After second plan, click right-scroll to navigate to next plan(s) and process each
        scroll_right_selector = "#scrollRight"
        plan_counter = 3
        while True:
            try:
                scroll_right = page.locator(scroll_right_selector)
                if await scroll_right.count() == 0:
                    print("No scrollRight found — assuming no more plans.")
                    break
                # click right scroll to bring next plan into view
                await click_force_js(page, scroll_right.first)
                await page.wait_for_timeout(900)

                # detect active plan card
                active_plan_card = page.locator(".plan-card.active").first
                if await active_plan_card.count() == 0:
                    active_plan_card = page.locator(".plan-card").nth(plan_counter - 1)
                # determine plan name / id if any
                plan_info_loc = active_plan_card.locator(".plan-info").first
                plan_name_attr = None
                try:
                    # try to get id or some identifier
                    handle = await plan_info_loc.element_handle()
                    if handle:
                        plan_name_attr = await page.evaluate("(el) => el.id || el.getAttribute('data-plan-name') || el.className", handle)
                except Exception:
                    pass
                plan_name = plan_name_attr or f"plan_{plan_counter}"

                # If this is third-party plan (class includes 'third' or id unknown), handle addons differently
                # For third-party plan, target add-on container and click addon labels car-00..car-02
                try:
                    addon_container = page.locator(".add-on-cls.mb-24")
                    if await addon_container.count() > 0:
                        # click addon labels for car-00, car-01, car-02
                        for i in range(3):
                            lbl_id = f"car-0{i}"
                            lbl_selector = f"label[for='addon{i}']#{lbl_id}, label#{lbl_id}, label[for='addon{i}']"
                            lbl_loc = page.locator(lbl_selector)
                            if await lbl_loc.count() > 0:
                                await click_force_js(page, lbl_loc.first)
                                manifest.append({"plan_index": plan_counter, "action": "click_addon_label", "label": lbl_selector, "ts": ts()})
                                await page.wait_for_timeout(300)
                        # save addon container & full page
                        addon_path = save_file_path("addon", plan_name, "selected_addons")
                        await save_outer_html(page, ".add-on-cls.mb-24", addon_path)
                        full_after_addons = save_file_path("fullpage", plan_name, "after_addons")
                        await save_outer_html(page, None, full_after_addons)
                except Exception as e:
                    print(f"⚠ Error while handling addons for plan {plan_counter}: {e}")

                # Now process this plan using same generic routine
                await process_plan(page, plan_counter, plan_name, manifest, plan_locator=plan_info_loc)

                plan_counter += 1

                # Heuristic break to avoid infinite loop: if we've processed >10 plans, break
                if plan_counter > 12:
                    print("Reached plan processing limit; stopping to avoid infinite loop.")
                    break

                # small wait before next scroll
                await page.wait_for_timeout(600)
            except Exception as e:
                print(f"⚠ Exception in plan scrolling loop: {e}")
                break

        # final manifest write
        with open(MANIFEST_PATH, "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2)

        print(f"\nDone. Snapshots saved to: {OUTPUT_DIR.resolve()}")
        print(f"Manifest: {MANIFEST_PATH.resolve()}")

        # keep browser open for inspection; close if running headless
        # await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting.")
