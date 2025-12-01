"""
BeautifulSoup4 scraper for ICICI Lombard quote page.
Takes HTML content as input and extracts plan/premium information.
"""

from pathlib import Path
import json, re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup


def get_soup(html: str):
    return BeautifulSoup(html, "html.parser")


def extract_idv_values(html: str):
    """
    Extract recommended IDV, minimum IDV, and maximum IDV from the IDV popup HTML.
    Returns integers: (recommended, min_idv, max_idv)
    If any value cannot be found, returns None for that field.
    """

    def to_int(s):
        if not s:
            return None
        s = re.sub(r"[^\d]", "", s)
        return int(s) if s else None

    soup = get_soup(html)

    # ---- Step 1: Identify popup ----
    popup = soup.find("div", {"id": "idvPopup"})
    if not popup:
        popup = soup.find("div", class_=lambda c: c and "popoverlay" in c)

    if not popup:
        return None, None, None

    # ---- Step 2: Extract recommended IDV ----
    recommended_text = None

    rec = popup.select_one("span.idv-pre")
    if rec:
        recommended_text = rec.get_text(strip=True)
    else:
        # fallback: find label "Recommended IDV" then next span
        label = popup.find(
            lambda tag: tag.name == "span"
            and tag.get_text(strip=True) == "Recommended IDV"
        )
        if label:
            sib = label.find_next_sibling("span")
            if sib:
                recommended_text = sib.get_text(strip=True)

    # ---- Step 3: Extract min/max IDV ----
    min_text, max_text = None, None

    # try primary selector: span containing phrase
    range_span = None
    candidates = popup.find_all("span", class_=lambda c: c and "ng-star-inserted" in c)

    for sp in candidates:
        txt = sp.get_text(" ", strip=True)
        if "Enter an IDV between" in txt:
            range_span = sp
            break

    # fallback phrase-only search
    if not range_span:
        range_span = popup.find(
            lambda tag: tag.name == "span"
            and "Enter an IDV between" in tag.get_text(" ", strip=True)
        )

    # extract min/max numbers
    if range_span:
        numbers = re.findall(r"₹\s*[\d,]+", range_span.get_text(" ", strip=True))
        if len(numbers) >= 2:
            min_text, max_text = numbers[0], numbers[1]
        else:
            # deeper fallback: cursorpointer spans
            inner = range_span.find_all(
                "span", class_=lambda c: c and "cursorpointer" in c
            )
            if len(inner) >= 2:
                min_text = inner[0].get_text(strip=True)
                max_text = inner[1].get_text(strip=True)

    # ---- Convert to integers ----
    recommended = to_int(recommended_text)
    min_idv = to_int(min_text)
    max_idv = to_int(max_text)

    return recommended, min_idv, max_idv


def extract_icici_car_details(html):
    soup = get_soup(html)

    vehicle_section = soup.find("app-vehicle-details")
    if vehicle_section is None:
        return {}

    data = {}

    # Manufacturer + Model
    manu = vehicle_section.find("h3")
    model = vehicle_section.find("p", attrs={"notranslate": True})

    data["manufacturer"] = manu.get_text(strip=True) if manu else None
    data["model"] = model.get_text(strip=True) if model else None

    # City
    city_el = vehicle_section.select_one("ul.car-model-breakup li span")
    data["city_of_registration"] = city_el.get_text(strip=True) if city_el else None

    # Expand block items
    expanded_section = vehicle_section.select_one(".slide-breakup ul.car-model-breakup")
    if expanded_section:
        for li in expanded_section.find_all("li"):
            label_el = li.find("p")
            value_el = li.find("span")

            if not label_el or not value_el:
                continue

            label = label_el.get_text(strip=True).lower()
            value = value_el.get_text(strip=True)

            if "first registration" in label:
                data["first_registration_date"] = value
            elif "previous" in label and "end date" in label:
                data["previous_policy_end_date"] = value
            elif "claims in last" in label:
                data["claims_last_year"] = value
            elif "ncb" in label:
                data["previous_ncb"] = value
            elif "registered under" in label:
                data["registered_under"] = value
            elif "previous policy type" in label:
                data["previous_policy_type"] = value

    # Ownership flag (checkbox)
    checkbox = vehicle_section.find("input", id="vehicleownd")
    if checkbox:
        data["no_change_of_ownership"] = checkbox.has_attr("checked")
    else:
        data["no_change_of_ownership"] = None

    return data


def extract_plans_from_cards(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract plan information from .singlecard elements.

    Args:
        soup: BeautifulSoup object containing parsed HTML

    Returns:
        List of plan dictionaries
    """
    plans = []

    # Try to find plan cards - can be in app-plan-card or direct button.plans-box
    app_plan_cards = soup.find_all("app-plan-card")

    # If app-plan-card exists, look for .singlecard or .plans-box inside it
    if app_plan_cards:
        for app_card in app_plan_cards:
            # First try .singlecard, if not found try .plans-box
            card = app_card.select_one(".singlecard") or app_card.select_one(
                "button.plans-box"
            )

            if not card:
                continue

            plan = {}

            # ---- TITLE ----
            title = card.select_one("h3")
            plan["title"] = title.get_text(" ", strip=True) if title else None

            # ---- PRICES ----
            premium = card.select_one(".premium-amount")
            discount = card.select_one(".discount-amount")
            policy_year = card.select_one(".policy-year")

            plan["premium"] = premium.get_text(strip=True) if premium else None
            plan["discount"] = discount.get_text(strip=True) if discount else None
            plan["policy_year"] = (
                policy_year.get_text(" ", strip=True) if policy_year else None
            )

            # ---- BENEFITS ----
            benefits = []
            for li in card.select(".plan-benefits li"):
                # li text contains tooltip text; we want only the visible benefit name
                # Approach: take the text before tooltip <span>
                text_nodes = [t for t in li.contents if isinstance(t, str)]
                benefit = (
                    text_nodes[0].strip() if text_nodes else li.get_text(strip=True)
                )
                benefits.append(benefit)

            plan["benefits"] = benefits
            plans.append(plan)

    # If no app-plan-card found, try direct .plans-box or .singlecard
    if not plans:
        direct_cards = soup.select(".plans-box, .singlecard")
        for card in direct_cards:
            plan = {}

            # ---- TITLE ----
            title = card.select_one("h3")
            plan["title"] = title.get_text(" ", strip=True) if title else None

            # ---- PRICES ----
            premium = card.select_one(".premium-amount")
            discount = card.select_one(".discount-amount")
            policy_year = card.select_one(".policy-year")

            plan["premium"] = premium.get_text(strip=True) if premium else None
            plan["discount"] = discount.get_text(strip=True) if discount else None
            plan["policy_year"] = (
                policy_year.get_text(" ", strip=True) if policy_year else None
            )

            # ---- BENEFITS ----
            benefits = []
            for li in card.select(".plan-benefits li"):
                # li text contains tooltip text; we want only the visible benefit name
                # Approach: take the text before tooltip <span>
                text_nodes = [t for t in li.contents if isinstance(t, str)]
                benefit = (
                    text_nodes[0].strip() if text_nodes else li.get_text(strip=True)
                )
                benefits.append(benefit)

            plan["benefits"] = benefits
            plans.append(plan)

    return plans


def extract_premium_summary(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    summary = {}

    # --------------------------
    # Helper to extract pairs
    # --------------------------
    def extract_key_values(container_selector: str) -> Dict[str, str]:
        data = {}
        container = soup.select_one(container_selector)
        if not container:
            return data

        for li in container.select("li"):
            p = li.select_one("p")
            span = li.select_one("span")
            if not p or not span:
                continue
            key = p.get_text(strip=True)
            value = span.get_text(strip=True)
            data[key] = value
        return data

    # ---------- BASIC PREMIUM + ADDITIONAL COVERS + SUBTOTAL ----------
    basic = extract_key_values(".basic-premium")

    summary["base_premium"] = basic.get("Base premium")
    summary["additional_covers"] = basic.get("Additional covers")
    summary["sub_total"] = basic.get("Sub Total")

    # ---------- ADDITIONAL COVERS BREAKDOWN ----------
    summary["additional_covers_breakdown"] = []
    add_ul = soup.select_one(".basic-premium .add-premium-details")
    if add_ul:
        for li in add_ul.select("li"):
            name = li.select_one("p")
            price = li.select_one("span")
            if name and price:
                summary["additional_covers_breakdown"].append(
                    {
                        "name": name.get_text(strip=True),
                        "price": price.get_text(strip=True),
                    }
                )

    # ---------- NET PREMIUM (Comes under .additional-premium) ----------
    additional = extract_key_values(".additional-premium")
    summary["net_premium"] = additional.get("Net Premium")
    summary["discounts"] = additional.get("Discounts")  # if ever present

    # ---------- DISCOUNT BREAKDOWN ----------
    summary["discount_breakdown"] = []
    discount_ul = soup.select_one(".additional-premium .add-premium-details")
    if discount_ul:
        for li in discount_ul.select("li"):
            name = li.select_one("p")
            price = li.select_one("span")
            if name and price:
                summary["discount_breakdown"].append(
                    {
                        "name": name.get_text(strip=True),
                        "price": price.get_text(strip=True),
                    }
                )

    # ---------- TOTAL PREMIUM + GST ----------
    total_span = soup.select_one(".total-premium li span")
    if total_span:
        full_text = total_span.get_text(" ", strip=True)

        summary["total_premium"] = full_text.split("+")[0].strip()

        gst = total_span.select_one("sub.tp-gst")
        if gst:
            gst_text = gst.get_text(strip=True)
            gst_clean = (
                gst_text.replace("+", "")
                .replace("GST", "")
                .replace("(", "")
                .replace(")", "")
                .strip()
            )
            summary["gst"] = gst_clean
        else:
            summary["gst"] = None
    else:
        summary["total_premium"] = None
        summary["gst"] = None

    return summary


def scrape_icic_plans(html_content: str) -> Dict[str, Any]:
    """
    Scrape ICICI Lombard quote page HTML to extract plans information.

    Args:
        html_content: HTML content as string

    Returns:
        Dictionary containing extracted plan data
    """
    soup = get_soup(html_content)

    # -------------------------------------------------------------
    # EXTRACT PLANS FROM CARDS
    # -------------------------------------------------------------
    scraped_data = extract_plans_from_cards(soup)

    return scraped_data


def scrape_icic_plan_premium(html_content: str) -> Dict[str, Any]:
    """
    Scrape ICICI Lombard quote page HTML to premium information.

    Args:
        html_content: HTML content as string

    Returns:
        Dictionary containing extracted premium data
    """
    soup = get_soup(html_content)

    scraped_data = {
        "premium_summary": {},
    }

    # -------------------------------------------------------------
    # EXTRACT PREMIUM SUMMARY
    # -------------------------------------------------------------
    scraped_data["premium_summary"] = extract_premium_summary(soup)

    return scraped_data


def scrape_from_file(html_file_path: str) -> Dict[str, Any]:
    """
    Convenience function to scrape from HTML file.

    Args:
        html_file_path: Path to HTML file

    Returns:
        Dictionary containing extracted plan/premium data
    """
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    return scrape_icic_plans(html_content)


def main():
    """Main function to test the scraper."""
    html_file = Path(__file__).parent / "icici_prem.html"

    print(f">>> Scraping HTML from: {html_file}")
    result = scrape_from_file(html_file)

    # # Save results
    # output_file = "icic_scraped_output.json"
    # with open(output_file, "w", encoding="utf-8") as f:
    #     json.dump(result, f, indent=4, ensure_ascii=False)

    # print(f">>> Scraping completed!")
    # print(f">>> Output saved to: {output_file}")
    # print(f"\n>>> Summary:")
    # print(f"  - Plans found: {len(result['plans'])}")
    # print(f"  - Premium summary keys: {list(result['premium_summary'].keys())}")


if __name__ == "__main__":
    main()
