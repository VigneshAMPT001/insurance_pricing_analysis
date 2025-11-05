import os
import json
from typing import Dict, List, Any, Optional


ROOT_DIR = "/home/ampera/Documents/insurance_pricing_data"
IGNORED_TOP_LEVEL = {"session_storage_data", "venv"}


def normalize_plan_name(filename: str) -> str:
    base = os.path.splitext(filename)[0]
    cleaned = base.replace(" ", " ").replace("_", " ").strip()
    # Collapse multiple spaces
    cleaned = " ".join(part for part in cleaned.split(" ") if part)
    return cleaned


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        v = str(value).strip()
        if v == "" or v == "-":
            return None
        return float(v)
    except Exception:
        return None


def extract_pricing(
    file_path: str, company: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    pricing: Dict[str, Any] = {
        "total_premium": None,
        "net_premium": None,
        "tax_amount": None,
        "currency": "INR",
    }

    if company == "acko":
        plan = data.get("selected_plan", {})
        price = plan.get("price", {})
        pricing["net_premium"] = safe_float(price.get("net_premium"))
        pricing["total_premium"] = safe_float(price.get("gross_premium"))
        gst = price.get("gst", {})
        # gst field may be nested with total under "gst"
        pricing["tax_amount"] = safe_float(gst.get("gst"))
        return pricing

    if company == "royal_sundaram":
        details = data.get("PREMIUMDETAILS", {}).get("DATA", {})
        pricing["total_premium"] = safe_float(
            details.get("GROSS_PREMIUM") or details.get("PREMIUM")
        )
        pricing["net_premium"] = safe_float(details.get("PACKAGE_PREMIUM"))
        cgst = safe_float(details.get("CGST")) or 0.0
        sgst = safe_float(details.get("SGST")) or 0.0
        igst = safe_float(details.get("IGST")) or 0.0
        utgst = safe_float(details.get("UTGST")) or 0.0
        total_tax = cgst + sgst + igst + utgst
        pricing["tax_amount"] = total_tax if total_tax > 0 else None
        return pricing

    if company == "zurich_kotak":
        # Two variants exist: General coverage and Get360 include similar fields
        pricing["total_premium"] = safe_float(data.get("vTotalPremium"))
        pricing["net_premium"] = safe_float(data.get("vNetPremium"))
        pricing["tax_amount"] = safe_float(data.get("vGSTAmount"))
        return pricing

    # # Default fallback: try common keys
    # pricing["total_premium"] = safe_float(
    #     data.get("total_premium") or data.get("gross_premium")
    # )
    # pricing["net_premium"] = safe_float(data.get("net_premium"))
    # return pricing


def collect_company_model_plans() -> Dict[str, Dict[str, Dict[str, Any]]]:
    mapping: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # Only iterate immediate children of ROOT_DIR as companies
    try:
        top_entries = [
            d for d in os.listdir(ROOT_DIR) if os.path.isdir(os.path.join(ROOT_DIR, d))
        ]
    except FileNotFoundError:
        raise SystemExit(f"Root directory not found: {ROOT_DIR}")

    for company in top_entries:
        if company in IGNORED_TOP_LEVEL:
            continue
        company_path = os.path.join(ROOT_DIR, company)
        company_map: Dict[str, Dict[str, Any]] = {}

        # Walk subdirectories; any directory that contains .json files is treated as a model directory
        for dirpath, dirnames, filenames in os.walk(company_path):
            json_files = [f for f in filenames if f.lower().endswith(".json")]
            if not json_files:
                continue

            # Determine model name as the current directory name (leaf containing plan files)
            model_name = os.path.basename(dirpath)

            # Initialize model entry
            if model_name not in company_map:
                company_map[model_name] = {}

            # For each plan file in this folder, parse and extract pricing
            for jf in json_files:
                plan_name = normalize_plan_name(jf)
                file_path = os.path.join(dirpath, jf)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

                price_info = extract_pricing(file_path, company, data)
                company_map[model_name][plan_name] = {
                    "price": price_info,
                    "source_file": file_path,
                }

        if company_map:
            mapping[company] = company_map

    return mapping


def main() -> None:
    mapping = collect_company_model_plans()
    out_path = os.path.join(ROOT_DIR, "normalized_plans.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(out_path)


if __name__ == "__main__":
    main()
