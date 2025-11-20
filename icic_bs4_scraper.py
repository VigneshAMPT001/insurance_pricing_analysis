"""
BeautifulSoup4 scraper for ICICI Lombard quote page.
Takes HTML content as input and extracts plan/premium information.
"""

import json
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup


async def extract_car_details(page):
    def get_text(selector):
        el = page.locator(selector)
        return el.inner_text().strip() if el and el.count() > 0 else None

    car_details = {}

    # Manufacturer & Model
    car_details["manufacturer"] = get_text("app-vehicle-details h3[notranslate]")
    car_details["model"] = get_text(
        "app-vehicle-details .car-model-wrap p[notranslate]"
    )

    # City
    car_details["city_of_registration"] = get_text(
        "app-vehicle-details ul.car-model-breakup li:nth-child(1) span"
    )

    # Expand section fields
    details_list = page.locator(
        "app-vehicle-details .slide-breakup ul.car-model-breakup li"
    )

    for i in range(await details_list.count()):
        item = details_list.nth(i)
        label = (await item.locator("p").inner_text()).strip().lower()

        value_el = item.locator("span")
        value = (
            (await value_el.inner_text()).strip()
            if await value_el.count() > 0
            else None
        )

        if "first registration" in label:
            car_details["first_registration_date"] = value
        elif "previous" in label and "end date" in label:
            car_details["previous_policy_end_date"] = value
        elif "claims in last" in label:
            car_details["claims_last_year"] = value
        elif "ncb" in label:
            car_details["previous_ncb"] = value
        elif "registered under" in label:
            car_details["registered_under"] = value
        elif "previous policy type" in label:
            car_details["previous_policy_type"] = value

    # Ownership flag checkbox
    ownership_el = page.locator("input#vehicleownd")
    if await ownership_el.count() > 0:
        is_checked = await ownership_el.is_checked()
        car_details["no_change_of_ownership"] = is_checked

    return car_details


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
    """
    Extract premium summary information from the page.

    Args:
        soup: BeautifulSoup object containing parsed HTML

    Returns:
        Dictionary with premium summary and additional covers breakdown
    """
    summary = {}

    # --- Base Premium ---
    base = soup.select_one(".basic-premium li:nth-child(1) span")
    summary["base_premium"] = base.get_text(strip=True) if base else None

    # --- Additional Covers Total (Single Value) ---
    add = soup.select_one(".basic-premium li:nth-child(2) span")
    summary["additional_covers"] = add.get_text(strip=True) if add else None

    # --- Sub Total ---
    subtotal = soup.select_one(".basic-premium li:nth-child(3) span")
    summary["sub_total"] = subtotal.get_text(strip=True) if subtotal else None

    # --- Discounts ---
    discounts = soup.select_one(".additional-premium li:nth-child(1) span")
    summary["discounts"] = discounts.get_text(strip=True) if discounts else None

    # --- Net Premium ---
    net = soup.select_one(".additional-premium li:nth-child(2) span")
    summary["net_premium"] = net.get_text(strip=True) if net else None

    # --- Total Premium + GST ---
    total_span = soup.select_one(".total-premium li span")
    if total_span:
        total_text = total_span.get_text(" ", strip=True)
        parts = total_text.split("+")
        summary["total_premium"] = parts[0].strip()

        gst_tag = total_span.select_one("sub.tp-gst")
        summary["gst"] = gst_tag.get_text(strip=True) if gst_tag else None
    else:
        summary["total_premium"] = None
        summary["gst"] = None

    # --- Additional Covers Breakdown ---
    summary["additional_covers_breakdown"] = []
    add_ul = soup.select_one("ul.add-premium-details")

    if add_ul:
        for li in add_ul.select("li"):
            name_tag = li.select_one("p.greyTxt")
            price_tag = li.select_one("span.greyTxt")

            name = name_tag.get_text(strip=True) if name_tag else None
            price = price_tag.get_text(strip=True) if price_tag else None

            if name or price:
                summary["additional_covers_breakdown"].append(
                    {"name": name, "price": price}
                )

    return summary


def scrape_icic_plans(html_content: str) -> Dict[str, Any]:
    """
    Scrape ICICI Lombard quote page HTML to extract plans information.

    Args:
        html_content: HTML content as string

    Returns:
        Dictionary containing extracted plan data
    """
    soup = BeautifulSoup(html_content, "html.parser")

    scraped_data = {
        "plans": [],
        "premium_summary": {},
    }

    # -------------------------------------------------------------
    # EXTRACT PLANS FROM CARDS
    # -------------------------------------------------------------
    scraped_data["plans"] = extract_plans_from_cards(soup)

    return scraped_data


def scrape_icic_plan_premium(html_content: str) -> Dict[str, Any]:
    """
    Scrape ICICI Lombard quote page HTML to premium information.

    Args:
        html_content: HTML content as string

    Returns:
        Dictionary containing extracted premium data
    """
    soup = BeautifulSoup(html_content, "html.parser")

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
    html_file = "icic_quote_page.html"

    print(f">>> Scraping HTML from: {html_file}")
    result = scrape_from_file(html_file)

    # Save results
    output_file = "icic_scraped_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    print(f">>> Scraping completed!")
    print(f">>> Output saved to: {output_file}")
    print(f"\n>>> Summary:")
    print(f"  - Plans found: {len(result['plans'])}")
    print(f"  - Premium summary keys: {list(result['premium_summary'].keys())}")


if __name__ == "__main__":
    main()
