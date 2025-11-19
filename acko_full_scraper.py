import json
import asyncio
import copy
import os
from urllib.parse import urlparse, parse_qs

import requests
from playwright.async_api import async_playwright

CAR_NUMBER = "MH12SE5466"
PHONE = "8335278236"
INSURANCE_NAME = "acko"

HOME_URL = "https://www.acko.com/"
CAR_URL = "https://www.acko.com/gi/car"
ACKO_NEXT_NODE_URL = "https://www.acko.com/sdui/api/v1/next-node"
CLAIM_STATUES = ["not_claimed", "claimed"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSURER_OUTPUT_DIR = os.path.join(BASE_DIR, "insurer", INSURANCE_NAME)
os.makedirs(INSURER_OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------------------------
# API HELPERS
# -------------------------------------------------------------------
NODE_BODIES = {
    "entry_node": {
        "journey": "fresh_car",
        "data": {
            "is_new": False,
            "origin": "acko",
            "product": "car",
            "proposal_ekey": "",
            "session_data": {
                "vehicle_addons_node_visited": False,
                "family_addons_node_visited": False,
                "idv_packs_node_visited": False,
                "multi_year_plan_node_visited": False,
                "multi_tenure_plan_node_visited": False,
                "is_edit_journey": False,
            },
        },
        "current_node": "entry_node",
    },
    "previous_claim_confirmation_node": {
        "journey": "fresh_car",
        "data": {
            "is_new": "false",
            "origin": "acko",
            "product": "car",
            "previous_policy_claim_answer": "",
            "pincode": "",
            "phone": PHONE,
            "proposal_ekey": "",
            "session_data": {
                "vehicle_addons_node_visited": False,
                "family_addons_node_visited": False,
                "idv_packs_node_visited": False,
                "multi_year_plan_node_visited": False,
                "multi_tenure_plan_node_visited": False,
                "is_edit_journey": False,
            },
        },
        "expected_node": "",
        "current_node": "previous_claim_confirmation_node",
    },
}

NODE_BODIES_EXTENDED = {
    "plan_selection_node": {
        "journey": "fresh_car",
        "data": {
            "is_new": "false",
            "origin": "acko",
            "product": "car",
            "selected_idv": 590750,
            "selected_idv_type": "custom",
            "plan_id": "car_acko_garage_comprehensive_deductible",
            "display_name_sdui": "Comprehensive Plan",
            "proposal_ekey": "",
            "session_data": {
                "vehicle_addons_node_visited": False,
                "family_addons_node_visited": False,
                "idv_packs_node_visited": False,
                "multi_year_plan_node_visited": False,
                "multi_tenure_plan_node_visited": False,
                "is_edit_journey": False,
            },
        },
        "current_node": "plan_selection_node",
    },
    "plan_variants_node": {
        "journey": "fresh_car",
        "data": {
            "is_new": "false",
            "origin": "acko",
            "product": "car",
            "selected_idv": 590750,
            "selected_idv_type": "custom",
            "plan_id": "car_acko_garage_comprehensive_deductible",
            "display_name_sdui": "Comprehensive : Network Garage Plan",
            "proposal_ekey": "",
            "session_data": {
                "vehicle_addons_node_visited": False,
                "family_addons_node_visited": False,
                "idv_packs_node_visited": False,
                "multi_year_plan_node_visited": False,
                "multi_tenure_plan_node_visited": False,
                "is_edit_journey": False,
            },
        },
        "current_node": "plan_variants_node",
    },
}


def get_request_body(current_node, proposal_key, claim_status=None, pincode=None):
    if current_node not in NODE_BODIES:
        raise ValueError(f"Unknown current_node: {current_node}")

    body = copy.deepcopy(NODE_BODIES[current_node])
    if "data" in body:
        body["data"]["proposal_ekey"] = proposal_key
        if claim_status:
            body["data"]["previous_policy_claim_answer"] = claim_status
        if pincode and "pincode" in body["data"]:
            body["data"]["pincode"] = pincode
    return body


def call_next_node_api(current_node, proposal_key, claim_status=None, pincode=None):
    body = get_request_body(current_node, proposal_key, claim_status, pincode)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    response = requests.post(ACKO_NEXT_NODE_URL, json=body, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    print(f"\n➡ Request sent for node: {current_node}")
    print("➡ Status Code:", response.status_code)
    print("➡ Response:")
    # print(json.dumps(data, indent=2))

    return data


def save_claim_response(car_number, claim_status, response_data):
    if not claim_status:
        return
    filename = f"{car_number}-{claim_status}.json"
    file_path = os.path.join(INSURER_OUTPUT_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(response_data, f, indent=4)
    print(f">>> Saved {claim_status} response to {file_path}")


def extract_pincode_from_response(data):
    """
    Traverse the response JSON and try to locate the pincode value.
    """

    if isinstance(data, dict):
        if data.get("name") == "pincode" and isinstance(data.get("value"), (str, int)):
            return str(data["value"])
        if data.get("payloadData"):
            payload = data["payloadData"]
            if (
                isinstance(payload, dict)
                and payload.get("name") == "pincode"
                and payload.get("value")
            ):
                return str(payload["value"])
        for value in data.values():
            pincode = extract_pincode_from_response(value)
            if pincode:
                return pincode
    elif isinstance(data, list):
        for item in data:
            pincode = extract_pincode_from_response(item)
            if pincode:
                return pincode
    return None


# -------------------------------------------------------------------
# MAIN SCRAPER
# -------------------------------------------------------------------
async def scrape_acko_full_flow():

    output_path = f"acko_full_output_{CAR_NUMBER}.json"
    final_json = {
        "car_number": CAR_NUMBER,
        "api_responses": {},
    }
    api_nodes = [
        "previous_claim_confirmation_node",
        "plan_selection_node",
        "plan_variants_node",
    ]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ---------------------------------------------------------
        # STEP 1: HOME PAGE → CAR INSURANCE
        # ---------------------------------------------------------
        print(">>> Opening Home")
        await page.goto(HOME_URL, timeout=60000)

        await page.wait_for_selector("div.HomeLandingWidget_productCardWrappers__CK_EM")

        product_cards = page.locator(
            "div.HomeLandingWidget_productCardWrappers__CK_EM span.ProductCardButton_productHeading__nn6iU"
        )

        count = await product_cards.count()
        for i in range(count):
            name = await product_cards.nth(i).inner_text()
            if "Car" in name:
                print(">>> Clicking Car Insurance")
                await product_cards.nth(i).click()
                break

        # ---------------------------------------------------------
        # STEP 2: ENTER CAR NUMBER
        # ---------------------------------------------------------
        print(">>> Waiting for Car Page...")
        await page.wait_for_load_state("networkidle")

        await page.wait_for_selector("input#carNumber")
        print(">>> Filling Car Number")
        await page.fill("input#carNumber", CAR_NUMBER)
        await asyncio.sleep(1)

        print(">>> Clicking Check Price")
        await page.click("button.jsx-2611325737.style-button-primary")

        # ---------------------------------------------------------
        # STEP 3: Entering Phone
        # ---------------------------------------------------------
        print(">>> Entering Phone")
        await page.wait_for_selector("input#phone")
        await page.fill("input#phone", PHONE)
        print(">>> Clicking View Prices")
        await page.click("button.sc-eHgmQL.sc-cqpYsc")
        # ---------------------------------------------------------
        # STEP 3: PREVIOUS CLAIM → YES/NO
        # ---------------------------------------------------------
        print(">>> Handling Claim Question")
        await page.wait_for_selector("div.jsx-1278309658.question")

        yes_no = page.locator("button.sc-elJkPf")
        await yes_no.nth(0).click()  # Click YES

        # Wait until the page URL changes and contains a proposal_ekey (timeout 30s)
        initial_url = page.url
        proposal_ekey = None
        timeout = 30.0
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            current_url = page.url
            if current_url != initial_url:
                proposal_ekey = parse_qs(urlparse(current_url).query).get(
                    "proposal_ekey", [None]
                )[0]
            if proposal_ekey:
                break
            await asyncio.sleep(0.5)

        # Final attempt in case it changed right after the loop
        if not proposal_ekey:
            current_url = page.url
            proposal_ekey = parse_qs(urlparse(current_url).query).get(
                "proposal_ekey", [None]
            )[0]
        if not proposal_ekey:
            raise RuntimeError("Could not determine proposal_ekey from the URL.")
        final_json["proposal_ekey"] = proposal_ekey
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=4)

        print(f">>> Captured proposal_ekey: {proposal_ekey}")

        print(">>> Triggering API nodes")
        loop = asyncio.get_running_loop()

        # First node call: entry_node
        entry_node_response = await loop.run_in_executor(
            None, call_next_node_api, "entry_node", proposal_ekey
        )
        final_json["api_responses"]["entry_node"] = entry_node_response
        extracted_pincode = extract_pincode_from_response(entry_node_response)
        if extracted_pincode:
            print(f">>> Extracted pincode from entry node: {extracted_pincode}")
        else:
            print(">>> Warning: Failed to extract pincode from entry node response")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=4)

        # Second node: previous_claim_confirmation_node - make two calls
        for claim_status in CLAIM_STATUES:
            node_key = f"previous_claim_confirmation_node_{claim_status}"
            node_response = await loop.run_in_executor(
                None,
                call_next_node_api,
                "previous_claim_confirmation_node",
                proposal_ekey,
                claim_status,
                extracted_pincode,
            )
            final_json["api_responses"][node_key] = node_response
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(final_json, f, indent=4)
            save_claim_response(CAR_NUMBER, claim_status, node_response)

        # Remaining plan-related nodes
        # for node in api_nodes[1:]:
        #     node_response = await loop.run_in_executor(
        #         None, call_next_node_api, node, proposal_ekey
        #     )
        #     final_json["api_responses"][node] = node_response
        #     with open(output_path, "w", encoding="utf-8") as f:
        #         json.dump(final_json, f, indent=4)

        print(f"\n>>> DONE: Latest data → {output_path}\n")

        await browser.close()
        return


# RUN
if __name__ == "__main__":
    asyncio.run(scrape_acko_full_flow())
