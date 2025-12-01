from bs4 import BeautifulSoup
import re, json
from datetime import datetime

# Regex patterns
REG_NO_PATTERN = re.compile(r"\b([A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4})\b", re.I)
DATE_PATTERN = re.compile(r"(\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4})")
FUEL_PATTERN = re.compile(r"fuel\s*type\s*(?:is|:)\s*(\w+)", re.I)
VARIANT_PATTERN = re.compile(r"variant\s*(?:is|:)\s*(.+)", re.I)
RTO_PATTERN = re.compile(r"RTO\s*[-:]?\s*(.+)", re.I)
MAKE_MODEL_PATTERN = re.compile(
    r"([A-Z][A-Z0-9\- ]+)\s*<span[^>]*>\s*([^<]+)\s*</span>", re.I
)


def clean_text(t):
    return " ".join(t.split()).strip()


def try_parse_date(text):
    m = DATE_PATTERN.search(text)
    if not m:
        return None
    s = m.group(1)
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except:
            continue
    return s


def clean_amount(v):
    v = v.replace("₹", "").replace(",", "").strip()
    return re.sub(r"[^\d]", "", v)


def parse_idv_section(html):
    soup = BeautifulSoup(html, "html.parser")

    # Locate IDV container
    idv_box = soup.find("div", class_=lambda c: c and "idv-selection" in c)
    if not idv_box:
        print("⚠ IDV section not found")
        return {}

    # Extract elements
    min_tag = idv_box.select_one(".irs-min")
    max_tag = idv_box.select_one(".irs-max")
    selected_tag = idv_box.select_one(".irs-single")

    def clean(x):
        if not x:
            return None
        text = x.get_text(strip=True)
        return text.replace("₹", "").replace(",", "").strip()

    return {
        "idv_min": clean(min_tag),
        "idv_max": clean(max_tag),
        "idv_selected": clean(selected_tag),
    }


def parse_cover_sections(html):
    soup = BeautifulSoup(html, "html.parser")

    result = {"whats_covered": [], "whats_not_covered": []}

    # ---- Helper: extract accordion items ----
    def extract_items(container_id):
        container = soup.find("div", id=container_id)
        items = []

        if not container:
            return items

        accordion_items = container.find_all(
            "div", class_=lambda c: c and "accordion-item" in c
        )

        for item in accordion_items:
            header_btn = item.find(
                "button", class_=lambda c: c and "accordion-button" in c
            )
            body_div = item.find("div", class_=lambda c: c and "accordion-body" in c)

            if not header_btn or not body_div:
                continue

            title = header_btn.get_text(strip=True)
            desc = body_div.get_text(strip=True)

            items.append({"title": title, "description": desc})

        return items

    # ---- Extract both sections ----
    result["whats_covered"] = extract_items("accordionFlushExampleCovered")
    result["whats_not_covered"] = extract_items("accordionFlushExampleNotCovered")

    return result


def parse_premium_breakup(html):
    soup = BeautifulSoup(html, "html.parser")

    # --- Primary selector ---
    ul = soup.find("ul", class_=lambda c: c and "prembr-list" in c)

    # --- Fallback selectors (more flexible) ---
    if not ul:
        ul = soup.select_one("ul[class*='prembr']")
    if not ul:
        ul = soup.select_one("ul.prembr-list, ul[class*='prembr-list']")
    if not ul:
        print("⚠ prembr-list <ul> not found even after fallback checks")
        return {}

    result = {}
    current_section = None

    # Only iterate direct children — avoids nested tag pollution
    for tag in ul.find_all(recursive=False):

        # Section header
        if tag.name == "h6":
            sec = tag.get_text(strip=True)
            result[sec] = []
            current_section = sec

        # LI row
        elif tag.name == "li" and current_section:

            label_div = tag.find("div", class_=lambda c: c and "prem-lable" in c)
            amt_div = tag.find("div", class_=lambda c: c and "prem-amt" in c)

            if not (label_div and amt_div):
                continue  # avoid crashes

            label = label_div.get_text(strip=True)
            amt = clean_amount(amt_div.get_text())

            result[current_section].append({"label": label, "amount": amt})

    return result


def parse_car_details(html):
    soup = BeautifulSoup(html, "html.parser")
    result = []
    blocks = soup.find_all("app-car-details")
    if not blocks:
        blocks = [soup]
    for blk in blocks:
        data = {
            "registration_number": None,
            "make": None,
            "model": None,
            "fuel_type": None,
            "variant": None,
            "registration_date": None,
            "rto": None,
            "raw_lines": [],
        }
        lis = blk.find_all("li")
        if lis:
            for li in lis:
                txt = clean_text(li.get_text(separator=" "))
                data["raw_lines"].append(txt)
                if not data["registration_number"]:
                    m = REG_NO_PATTERN.search(txt)
                    if m:
                        data["registration_number"] = m.group(1).upper()
                if not data["fuel_type"]:
                    m = FUEL_PATTERN.search(txt)
                    if m:
                        data["fuel_type"] = m.group(1).upper()
                if not data["variant"]:
                    m = VARIANT_PATTERN.search(txt)
                    if m:
                        data["variant"] = m.group(1).strip()
                if not data["registration_date"]:
                    dt = try_parse_date(txt)
                    if dt:
                        data["registration_date"] = dt
                if not data["rto"]:
                    m = RTO_PATTERN.search(txt)
                    if m:
                        data["rto"] = m.group(1).strip()
                span = li.find("span")
                if span and not data["model"]:
                    full = clean_text(li.get_text(separator=" "))
                    span_txt = clean_text(span.get_text())
                    make_guess = full.replace(span_txt, "").strip()
                    if make_guess:
                        data["make"] = make_guess.upper()
                        data["model"] = span_txt
        else:
            txt = clean_text(blk.get_text(separator=" | "))
            data["raw_lines"].append(txt)
            m = REG_NO_PATTERN.search(txt)
            if m:
                data["registration_number"] = m.group(1).upper()
            m = FUEL_PATTERN.search(txt)
            if m:
                data["fuel_type"] = m.group(1).upper()
            m = VARIANT_PATTERN.search(txt)
            if m:
                data["variant"] = m.group(1).strip()
            dt = try_parse_date(txt)
            if dt:
                data["registration_date"] = dt
            m = RTO_PATTERN.search(txt)
            if m:
                data["rto"] = m.group(1).strip()
            mm = MAKE_MODEL_PATTERN.search(str(blk))
            if mm:
                data["make"] = mm.group(1).strip().upper()
                data["model"] = mm.group(2).strip()

        result.append(data)
    return result


# Example usage:
if __name__ == "__main__":
    html_file_path = "chola_test.html"
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    print(json.dumps(parse_car_details(html_content), indent=2))

    parsed = parse_premium_breakup(html_content)
    print(json.dumps(parsed, indent=2))
    print(json.dumps(parse_idv_section(html_content), indent=2))
    print(json.dumps(parse_cover_sections(html_content), indent=2))
