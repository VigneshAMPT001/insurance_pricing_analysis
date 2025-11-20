from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
import re


def extract_premium_summary(soup: BeautifulSoup) -> dict:
    summary = {}

    # --- Base Premium ---
    summary["base_premium"] = None
    # --- Additional Covers (Total) ---
    summary["additional_covers"] = None
    # --- Sub Total ---
    summary["sub_total"] = None

    for li in soup.select(".basic-premium > li"):
        label = li.select_one("p")
        value = li.select_one("span")
        if label and value:
            text = label.get_text(strip=True)
            if "Base premium" in text:
                summary["base_premium"] = value.get_text(strip=True)
            elif "Additional covers" in text:
                summary["additional_covers"] = value.get_text(strip=True)
            elif "Sub Total" in text:
                summary["sub_total"] = value.get_text(strip=True)

    # --- Additional Covers Breakdown ---
    summary["additional_covers_breakdown"] = []
    add_breakdown_ul = soup.select_one(".basic-premium .add-premium-details")
    if add_breakdown_ul:
        for li in add_breakdown_ul.select("li"):
            name = li.select_one("p")
            price = li.select_one("span")
            if name and price:
                summary["additional_covers_breakdown"].append(
                    {
                        "name": name.get_text(strip=True),
                        "price": price.get_text(strip=True),
                    }
                )

    # --- Discounts ---
    summary["discounts"] = None
    for li in soup.select(".additional-premium > li"):
        label = li.select_one("p")
        value = li.select_one("span")
        if label and value:
            text = label.get_text(strip=True)
            if "Discount" in text:
                summary["discounts"] = value.get_text(strip=True)

    # --- Discount Breakdown ---
    summary["discount_breakdown"] = []
    discount_breakdown_ul = soup.select_one(".additional-premium .add-premium-details")
    if discount_breakdown_ul:
        for li in discount_breakdown_ul.select("li"):
            name = li.select_one("p")
            price = li.select_one("span")
            if name and price:
                summary["discount_breakdown"].append(
                    {
                        "name": name.get_text(strip=True),
                        "price": price.get_text(strip=True),
                    }
                )

    # --- Net Premium ---
    summary["net_premium"] = None
    for li in soup.select(".additional-premium > li"):
        label = li.select_one("p")
        value = li.select_one("span")
        if label and value:
            text = label.get_text(strip=True)
            if "Net Premium" in text:
                summary["net_premium"] = value.get_text(strip=True)

    # --- Total Premium and GST ---
    total = soup.select_one(".total-premium li span")
    if total:
        premium_raw = total.get_text(" ", strip=True)
        summary["total_premium"] = premium_raw.split("+")[0].strip()
        gst_tag = total.select_one("sub.tp-gst")
        if gst_tag:
            import re

            match = re.search(r"(\d+)%", gst_tag.get_text(strip=True))
            summary["gst"] = match.group(1) + "%" if match else None
        else:
            summary["gst"] = None
    else:
        summary["total_premium"] = None
        summary["gst"] = None

    return summary


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

    soup = BeautifulSoup(html, "html.parser")

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


if __name__ == "__main__":
    html_file = "icic_scraped_output_MH49BB1307_fixed.html"
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    print(f">>> Scraping HTML from: {html_file}")
    soup = BeautifulSoup(html_content, "html.parser")

    data = extract_premium_summary(soup)

    print(data)
    recommended, min_idv, max_idv = extract_idv_values(html_content)

    print("Recommended:", recommended)
    print("Min:", min_idv)
    print("Max:", max_idv)
