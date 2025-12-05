import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


PLAN_CATEGORY_LABELS = {
    "comp": "Comprehensive",
    "od": "Own Damage",
    "tp": "Third Party",
    "zd": "Zero Depreciation",
}

CLAIM_STATUS_LABELS = {
    "claimed": "Claimed",
    "not_claimed": "Not Claimed",
    "pending": "Pending",
}

BADGE_TEXTS_TO_REMOVE = {"recommended for your car"}


def init_car_file_entry() -> Dict[str, List[Dict[str, Any]]]:
    """Return default storage structure for car files across insurers."""
    return {
        "acko": [],
        "icici": [],
        "cholams": [],
        "royal_sundaram": [],
        "godigit": [],
    }


def sanitize_badge_text(badge: Any) -> str:
    """Return cleaned badge text while suppressing unwanted phrases."""
    if not isinstance(badge, str):
        return ""
    badge_clean = badge.strip()
    return "" if badge_clean.lower() in BADGE_TEXTS_TO_REMOVE else badge_clean


def normalize_claim_status(status: Any) -> str:
    """Return normalized claim status key (claimed / not_claimed / pending)."""
    if status is None:
        return ""
    value = str(status).strip().lower().replace(" ", "_")
    if value in {"claimed", "not_claimed", "notclaimed", "not-claimed"}:
        return "not_claimed" if value != "claimed" and "not" in value else "claimed"
    if value in {"unclaimed"}:
        return "not_claimed"
    if value in {"pending", "in_process", "in-process"}:
        return "pending"
    return value


def format_claim_status(status: Any, fallback: str = "") -> str:
    """Return a user-friendly claim status label."""
    normalized = normalize_claim_status(status)
    if not normalized:
        return fallback
    return CLAIM_STATUS_LABELS.get(normalized, normalized.replace("_", " ").title())


def infer_claim_status_from_filename(file_path: str) -> str:
    """Infer claim status from trailing token in filename stem (e.g., '-claimed')."""
    try:
        stem = Path(file_path).stem
    except Exception:
        return ""
    if "-" not in stem:
        return ""
    suffix = stem.split("-")[-1]
    return normalize_claim_status(suffix)


def extract_signed_amount(value: Any) -> float:
    """Extract numeric value while preserving sign (supports strings like '-₹ 652')."""
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return 0.0
    value_str = str(value).strip()
    if not value_str:
        return 0.0

    working = value_str
    sign = 1.0

    if working.startswith("(") and working.endswith(")"):
        sign = -1.0
        working = working[1:-1]

    working = working.strip()
    if working.startswith("-"):
        sign = -1.0
        working = working[1:]
    elif working.startswith("+"):
        working = working[1:]

    numbers = re.findall(r"[\d,\.]+", working)
    if not numbers:
        return 0.0
    number_str = numbers[0].replace(",", "")
    try:
        return sign * float(number_str)
    except ValueError:
        return 0.0


def build_idv_info(*sources: Dict[str, Any]) -> Dict[str, float]:
    """Merge IDV information from multiple sources into a normalized dict."""
    field_map = {
        "current": ["current_idv", "idv", "default_idv", "idv_value", "slider_value"],
        "recommended": ["recommended_idv"],
        "min": ["min_idv", "idv_min"],
        "max": ["max_idv", "idv_max"],
        "selected": ["idv_selected"],
    }

    idv_info: Dict[str, float] = {}

    for source in sources:
        if not isinstance(source, dict):
            continue
        for normalized_key, possible_keys in field_map.items():
            if normalized_key in idv_info:
                continue
            for key in possible_keys:
                if key in source and source[key] not in (None, ""):
                    idv_info[normalized_key] = extract_signed_amount(source[key])
                    break

    return idv_info


def init_pricing_template() -> Dict[str, Any]:
    """Return a normalized pricing structure used across insurers."""
    return {
        "base_premium": None,
        "own_damage_premium": None,
        "third_party_premium": None,
        "addons_total": 0.0,
        "addons_breakdown": [],
        "discounts_total": 0.0,
        "discount_breakdown": [],
        "gst_amount": None,
        "gst_rate": "",
        "net_premium": None,
        "total_premium": None,
        "sections": [],
    }


def finalize_pricing_breakdown(pricing: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize zero values to None when no supporting data exists."""
    if not pricing["addons_breakdown"]:
        pricing["addons_total"] = None
    if not pricing["discount_breakdown"]:
        pricing["discounts_total"] = None
    return pricing


def build_acko_pricing(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Approximate pricing components for an Acko plan."""
    pricing = init_pricing_template()
    total_premium = extract_signed_amount(plan.get("premium_value", 0.0))
    addons_breakdown = []
    addons_total = 0.0

    for addon in plan.get("addons", []):
        if not isinstance(addon, dict):
            continue
        name = addon.get("display_name") or addon.get("name") or "Addon"
        price_value = (
            addon.get("net_premium")
            or addon.get("price")
            or addon.get("gross_premium", 0)
        )
        amount = extract_signed_amount(price_value)
        if amount == 0:
            continue
        addons_breakdown.append({"name": name, "price": amount})
        addons_total += amount

    pricing["addons_breakdown"] = addons_breakdown
    pricing["addons_total"] = addons_total if addons_breakdown else None
    pricing["base_premium"] = max(total_premium - addons_total, 0.0)
    pricing["net_premium"] = total_premium
    pricing["total_premium"] = total_premium
    pricing["sections"] = []

    return finalize_pricing_breakdown(pricing)


def build_icici_pricing(premium_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Build pricing details from ICICI premium summary block."""
    pricing = init_pricing_template()
    if not isinstance(premium_summary, dict):
        return finalize_pricing_breakdown(pricing)

    pricing["base_premium"] = extract_signed_amount(premium_summary.get("base_premium"))

    addons_breakdown = []
    addons_total = 0.0
    for cover in premium_summary.get("additional_covers_breakdown", []):
        if not isinstance(cover, dict):
            continue
        name = cover.get("name", "Additional Cover")
        amount = extract_signed_amount(cover.get("price"))
        if amount == 0:
            continue
        addons_breakdown.append({"name": name, "price": amount})
        addons_total += amount

    discounts_breakdown = []
    discounts_total = 0.0
    for discount in premium_summary.get("discount_breakdown", []):
        if not isinstance(discount, dict):
            continue
        name = discount.get("name", "Discount")
        amount = extract_signed_amount(discount.get("price"))
        if amount == 0:
            continue
        discounts_breakdown.append({"name": name, "price": amount})
        discounts_total += amount

    pricing["addons_breakdown"] = addons_breakdown
    pricing["addons_total"] = addons_total if addons_breakdown else None
    pricing["discount_breakdown"] = discounts_breakdown
    pricing["discounts_total"] = discounts_total if discounts_breakdown else None
    pricing["gst_rate"] = premium_summary.get("gst", "")
    total = extract_signed_amount(premium_summary.get("total_premium"))
    pricing["net_premium"] = total if total else None
    pricing["total_premium"] = total if total else None
    pricing["sections"] = []

    return finalize_pricing_breakdown(pricing)


def build_cholams_pricing(plan_premium: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Cholams plan premium table into normalized pricing data."""
    pricing = init_pricing_template()
    if not isinstance(plan_premium, dict):
        return finalize_pricing_breakdown(pricing)

    sections = []
    addons_total = 0.0
    discounts_total = 0.0

    for section_name, entries in plan_premium.items():
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            label = entry.get("label", "").strip()
            amount = extract_signed_amount(entry.get("amount", 0))
            sections.append({"section": section_name, "label": label, "amount": amount})

            normalized_label = label.lower()

            if "own damage premium after discount" in normalized_label:
                pricing["own_damage_premium"] = amount
            elif normalized_label == "own damage":
                pricing["base_premium"] = amount
            elif "third party" in normalized_label:
                pricing["third_party_premium"] = amount
            elif normalized_label.startswith("net premium"):
                pricing["net_premium"] = amount
            elif normalized_label.startswith("total premium"):
                pricing["total_premium"] = amount
            elif "gst" in normalized_label:
                pricing["gst_amount"] = amount
            elif section_name.startswith("(C) Add-On") and (
                "own damage premium" not in normalized_label
            ):
                pricing["addons_breakdown"].append({"name": label, "price": amount})
                addons_total += amount
            elif section_name.startswith("(B)"):
                discount_value = -abs(amount)
                pricing["discount_breakdown"].append(
                    {"name": label, "price": discount_value}
                )
                discounts_total += discount_value

    pricing["sections"] = sections
    pricing["addons_total"] = addons_total if pricing["addons_breakdown"] else None
    pricing["discounts_total"] = (
        discounts_total if pricing["discount_breakdown"] else None
    )

    return finalize_pricing_breakdown(pricing)


def normalize_plan_category(category: str) -> str:
    """Normalize various plan category strings into common keys."""
    if not category:
        return ""
    value = category.strip().lower()

    if value in {"zd", "zd_od", "zero dep", "zero_dep", "zero depreciation"}:
        return "comp"

    if "third" in value or value in {"tp", "third-party", "third party"}:
        return "tp"

    if "own" in value and "damage" in value:
        return "od"
    if value in {"od", "od_plan"}:
        return "od"

    if "bumper" in value:
        return "comp"

    if "comp" in value or "comprehensive" in value:
        return "comp"

    return value


def get_plan_category_label(category_key: str, fallback: str = "") -> str:
    """Return a user-friendly label for a normalized category key."""
    if not category_key:
        return fallback
    return PLAN_CATEGORY_LABELS.get(
        category_key, category_key.replace("_", " ").title()
    )


def extract_premium_value(premium_str: str) -> float:
    """Extract numeric value from premium string like '₹5,142' or '₹4,992'"""
    if not premium_str:
        return 0.0
    numbers = re.findall(r"[\d,]+", premium_str.replace("₹", "").replace(",", ""))
    if numbers:
        try:
            return float(numbers[0].replace(",", ""))
        except ValueError:
            return 0.0
    return 0.0


def load_json_data(file_path: str) -> Dict[str, Any]:
    """Load and parse JSON insurance data from a file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_acko_plans(
    data: Dict[str, Any], claim_status: str = ""
) -> List[Dict[str, Any]]:
    """Extract plans from Acko data structure."""
    plans = []
    car_info = data.get("car_info", {})
    idv_info = build_idv_info(car_info)
    normalized_claim_status = normalize_claim_status(claim_status)
    for plan in data.get("plans", []):
        category_raw = plan.get("category", "")
        normalized_category = normalize_plan_category(category_raw)

        plan_info = {
            "plan_id": plan.get("plan_id", ""),
            "plan_name": plan.get("plan_name", ""),
            "category": normalized_category or category_raw,
            "category_display": get_plan_category_label(
                normalized_category, category_raw.upper()
            ),
            "premium_display": plan.get("premium_display", ""),
            "premium_value": plan.get("premium_value", 0.0),
            "description": plan.get("description", ""),
            "is_selected": plan.get("is_selected", False),
            "badge": sanitize_badge_text(plan.get("badge", "")),
            "addons": plan.get("addons", []),
            "insurer": "Acko",
            "idv": idv_info,
            "pricing_breakdown": build_acko_pricing(plan),
            "claim_status": normalized_claim_status,
        }
        plans.append(plan_info)
    return plans


def get_icici_plans(
    data: Dict[str, Any], claim_status: str = ""
) -> List[Dict[str, Any]]:
    """Extract plans from ICICI data structure."""
    plans = []
    plans_offered = data.get("plans_offered", {})
    premiums_list = plans_offered.get("premiums", [])
    idv_info = build_idv_info(data)
    normalized_claim_status = normalize_claim_status(claim_status)

    for premium_info in premiums_list:
        plan_type = premium_info.get("plan_type", "")
        button_text = premium_info.get("button_text", "")
        title = button_text.split("\n")[0].replace("Recommended\n", "").strip()
        normalized_category = normalize_plan_category(plan_type)

        premium_summary = premium_info.get("premium", {}).get("premium_summary", {})
        total_premium_str = premium_summary.get("total_premium", "₹0")
        base_premium_str = premium_summary.get("base_premium", "₹0")

        additional_covers = premium_summary.get("additional_covers_breakdown", [])
        description_parts = []
        for cover in additional_covers:
            if isinstance(cover, dict):
                name = cover.get("name", "")
                if name:
                    description_parts.append(name)
            elif isinstance(cover, str):
                description_parts.append(cover)

        plan_info = {
            "plan_id": f"{plan_type}_{premium_info.get('button_index', 0)}",
            "plan_name": title,
            "category": normalized_category or plan_type.lower(),
            "category_display": get_plan_category_label(
                normalized_category, plan_type.title()
            ),
            "premium_display": total_premium_str,
            "premium_value": extract_premium_value(total_premium_str),
            "base_premium": extract_premium_value(base_premium_str),
            "description": ", ".join(description_parts),
            "is_selected": "Recommended" in button_text,
            "badge": sanitize_badge_text(
                "Recommended" if "Recommended" in button_text else ""
            ),
            "addons": premium_summary.get("additional_covers_breakdown", []),
            "benefits": [],
            "insurer": "ICICI",
            "idv": idv_info,
            "pricing_breakdown": build_icici_pricing(premium_summary),
            "claim_status": normalized_claim_status,
        }

        plans_list = plans_offered.get("plans", [])
        if plans_list:
            for plan_group in plans_list:
                if plan_type in plan_group:
                    plan_variants = plan_group[plan_type]
                    button_idx = premium_info.get("button_index", 0)
                    if button_idx < len(plan_variants):
                        plan_info["benefits"] = plan_variants[button_idx].get(
                            "benefits", []
                        )
                        break

        plans.append(plan_info)
    return plans


def get_cholams_plans(data: List[Any], claim_status: str = "") -> List[Dict[str, Any]]:
    """Extract plans from Cholams data structure."""
    plans = []
    normalized_claim_status = normalize_claim_status(claim_status)

    if not isinstance(data, list) or len(data) < 2:
        return plans

    plans_data = data[1] if len(data) > 1 else []

    for plan_obj in plans_data:
        if not isinstance(plan_obj, dict):
            continue

        for plan_name, plan_details in plan_obj.items():
            if not isinstance(plan_details, dict):
                continue

            plan_premium = plan_details.get("plan_premium", {})
            total_premium_section = plan_premium.get("(F) Total Premium", [])
            if not total_premium_section:
                total_premium_section = plan_premium.get("(C) Total Premium", [])

            total_premium_amount = "₹0"
            net_premium_amount = "₹0"

            for item in total_premium_section:
                if isinstance(item, dict):
                    label = item.get("label", "")
                    amount = item.get("amount", "0")
                    if "Total Premium" in label:
                        total_premium_amount = f"₹{amount}"
                    elif "Net Premium" in label:
                        net_premium_amount = f"₹{amount}"

            normalized_category = normalize_plan_category(plan_name)

            benefits_covered = plan_details.get("benefits_covered", {})
            whats_covered = benefits_covered.get("whats_covered", [])
            benefits = []
            for benefit in whats_covered:
                if isinstance(benefit, dict):
                    title = benefit.get("title", "")
                    description = benefit.get("description", "")
                    if title:
                        benefits.append(f"{title}: {description}")

            addons = []
            addon_section = plan_premium.get("(C) Add-On Cover", [])
            for item in addon_section:
                if isinstance(item, dict):
                    label = item.get("label", "")
                    amount = item.get("amount", "0")
                    if label and "Own Damage Premium" not in label:
                        try:
                            amount_clean = amount.replace(",", "").strip()
                            price = float(amount_clean) if amount_clean else 0
                        except (ValueError, AttributeError):
                            price = 0
                        addons.append({"name": label, "price": price})

            plan_info = {
                "plan_id": plan_name.lower().replace(" ", "_"),
                "plan_name": plan_name,
                "category": normalized_category or "comp",
                "category_display": get_plan_category_label(
                    normalized_category, plan_name
                ),
                "premium_display": total_premium_amount,
                "premium_value": extract_premium_value(total_premium_amount),
                "base_premium": extract_premium_value(net_premium_amount),
                "description": ", ".join([b.split(":")[0] for b in benefits[:3]]),
                "is_selected": False,
                "badge": "",
                "addons": addons,
                "benefits": benefits,
                "insurer": "Cholams",
                "idv": build_idv_info(plan_details.get("idv_range", {})),
                "pricing_breakdown": build_cholams_pricing(plan_premium),
                "claim_status": normalized_claim_status,
            }

            plans.append(plan_info)

    return plans


def build_royal_sundaram_pricing(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Build pricing breakdown for Royal Sundaram plans."""
    pricing = init_pricing_template()
    if not isinstance(plan, dict):
        return finalize_pricing_breakdown(pricing)

    premium_breakup = plan.get("premium_breakup", {}) or {}
    own_damage = premium_breakup.get("own_damage", {}) or {}
    liability = premium_breakup.get("liability", {}) or {}

    base_od = extract_signed_amount(own_damage.get("base_premium"))
    liability_base = extract_signed_amount(liability.get("base_premium"))
    net_premium = extract_signed_amount(premium_breakup.get("net_premium"))
    gst_amount = extract_signed_amount(
        premium_breakup.get("gst_18_percent") or premium_breakup.get("gst_amount")
    )
    total_premium = extract_signed_amount(premium_breakup.get("total_premium"))

    addons_total = 0.0
    discount_total = 0.0
    for name, value in (own_damage.get("add_ons") or {}).items():
        amount = extract_signed_amount(value)
        if amount == 0:
            continue
        label = name.replace("_", " ").title()
        entry = {"name": label, "price": amount}
        if amount > 0:
            pricing["addons_breakdown"].append(entry)
            addons_total += amount
        else:
            pricing["discount_breakdown"].append(entry)
            discount_total += amount

    pricing["base_premium"] = base_od if base_od else None
    od_total = net_premium - liability_base if net_premium and liability_base else None
    pricing["own_damage_premium"] = od_total if od_total else None
    pricing["third_party_premium"] = liability_base if liability_base else None
    pricing["addons_total"] = addons_total if pricing["addons_breakdown"] else None
    pricing["discounts_total"] = (
        discount_total if pricing["discount_breakdown"] else None
    )
    pricing["gst_amount"] = gst_amount if gst_amount else None
    pricing["gst_rate"] = "18%" if gst_amount else ""
    pricing["net_premium"] = net_premium if net_premium else None
    pricing["total_premium"] = total_premium if total_premium else None
    pricing["sections"] = []

    return finalize_pricing_breakdown(pricing)


def build_godigit_pricing(premium_breakup: Dict[str, Any]) -> Dict[str, Any]:
    """Build pricing breakdown for Go Digit plans."""
    pricing = init_pricing_template()
    if not isinstance(premium_breakup, dict):
        return finalize_pricing_breakdown(pricing)

    od = extract_signed_amount(premium_breakup.get("own_damage"))
    tp = extract_signed_amount(premium_breakup.get("third_party"))
    addons_amount = extract_signed_amount(premium_breakup.get("addons"))
    ncb_discount = extract_signed_amount(premium_breakup.get("ncb_discount"))
    digit_discount = extract_signed_amount(premium_breakup.get("digit_discount"))
    net_premium = extract_signed_amount(premium_breakup.get("net_premium"))
    gst_amount = extract_signed_amount(premium_breakup.get("gst"))
    final_premium = extract_signed_amount(premium_breakup.get("final_premium"))

    pricing["own_damage_premium"] = od if od else None
    pricing["third_party_premium"] = tp if tp else None
    pricing["base_premium"] = od + tp if (od and tp) else None

    if addons_amount:
        pricing["addons_breakdown"].append({"name": "Add-ons", "price": addons_amount})
        pricing["addons_total"] = addons_amount

    discounts_total = 0.0
    if ncb_discount:
        pricing["discount_breakdown"].append(
            {"name": "NCB Discount", "price": ncb_discount}
        )
        discounts_total += ncb_discount
    if digit_discount:
        pricing["discount_breakdown"].append(
            {"name": "Digit Discount", "price": digit_discount}
        )
        discounts_total += digit_discount
    pricing["discounts_total"] = (
        discounts_total if pricing["discount_breakdown"] else None
    )

    pricing["gst_amount"] = gst_amount if gst_amount else None
    pricing["net_premium"] = net_premium if net_premium else None
    pricing["total_premium"] = final_premium if final_premium else None
    pricing["sections"] = []

    return finalize_pricing_breakdown(pricing)


def format_selected_addons(selected_addons: Dict[str, Any]) -> List[str]:
    """Return a readable list of selected addon labels."""
    benefits = []
    for key, value in (selected_addons or {}).items():
        label = key.replace("_", " ").title()
        value_str = str(value).strip()
        if not value_str:
            continue
        if value_str.lower() in {"yes", "true", "selected"}:
            benefits.append(label)
        else:
            benefits.append(f"{label}: {value_str}")
    return benefits


def normalize_royal_sundaram_addons(addons: Dict[str, Any]) -> List[Any]:
    """Convert Royal Sundaram addon dict into list for display."""
    normalized: List[Any] = []
    for key, value in (addons or {}).items():
        label = key.replace("_", " ").title()
        if isinstance(value, (int, float)):
            normalized.append({"name": label, "price": float(value)})
        else:
            normalized.append(f"{label}: {value}")
    return normalized


def _normalize_godigit_addons(addons_block: Any) -> List[Any]:
    """Convert Go Digit addons structure into a normalized list."""
    normalized: List[Any] = []

    if isinstance(addons_block, dict):
        for label in addons_block.get("addons", []) or []:
            normalized.append(str(label))

        ncb_protection = addons_block.get("ncb_protection") or {}
        for name, value in ncb_protection.items():
            normalized.append(f"{name}: {value}")

    elif isinstance(addons_block, list):
        for addon in addons_block:
            if isinstance(addon, dict):
                label = str(addon.get("label") or addon.get("name") or "Addon")
                price_raw = addon.get("price") or addon.get("amount")
                amount = extract_signed_amount(price_raw)
                if amount:
                    normalized.append({"name": label, "price": amount})
                else:
                    normalized.append(label)
            else:
                normalized.append(str(addon))

    return normalized


def get_royal_sundaram_plans(
    data: Dict[str, Any], claim_status: str = ""
) -> List[Dict[str, Any]]:
    """Extract plans from Royal Sundaram data structure."""
    if not isinstance(data, dict):
        return []
    normalized_claim_status = normalize_claim_status(claim_status)

    car_details = data.get("car_details", {}) or {}
    plans_data = data.get("plans", {}) or {}
    idv_info = build_idv_info(car_details.get("idv", {}), car_details)
    plans: List[Dict[str, Any]] = []

    for plan_key, plan in plans_data.items():
        if not isinstance(plan, dict):
            continue

        plan_name = plan.get("plan_name") or plan_key.replace("_", " ").title()
        normalized_category = normalize_plan_category(plan_name or plan_key)

        premium_breakup = plan.get("premium_breakup", {}) or {}
        premium_value = extract_signed_amount(premium_breakup.get("total_premium"))
        premium_display = (
            format_premium(premium_value)
            if premium_value
            else format_premium(
                plan.get("premium_summary", {}).get("premium_excluding_gst")
            )
        )

        plan_info = {
            "plan_id": plan_key,
            "plan_name": plan_name,
            "category": normalized_category or plan_key,
            "category_display": get_plan_category_label(
                normalized_category, plan_name.title()
            ),
            "premium_display": premium_display,
            "premium_value": premium_value,
            "description": plan.get("description", ""),
            "is_selected": False,
            "badge": "",
            "addons": normalize_royal_sundaram_addons(plan.get("addons")),
            "benefits": format_selected_addons(plan.get("selected_addons", {})),
            "insurer": "Royal Sundaram",
            "idv": idv_info,
            "pricing_breakdown": build_royal_sundaram_pricing(plan),
            "claim_status": normalized_claim_status,
        }
        plans.append(plan_info)

    return plans


def get_godigit_plans(
    data: Dict[str, Any], claim_status: str = ""
) -> List[Dict[str, Any]]:
    """Extract plans from Go Digit data structure."""
    if not isinstance(data, dict):
        return []

    plans_offered = data.get("plans_offered", []) or []
    normalized_claim_status = normalize_claim_status(claim_status)

    idv_sources: List[Dict[str, Any]] = []
    for plan_entry in plans_offered:
        if not isinstance(plan_entry, dict):
            continue
        for _, details in plan_entry.items():
            if isinstance(details, dict) and isinstance(details.get("idv"), dict):
                idv_sources.append(details.get("idv") or {})
    shared_idv_info = build_idv_info(*idv_sources)

    plans: List[Dict[str, Any]] = []

    for plan_entry in plans_offered:
        if not isinstance(plan_entry, dict):
            continue

        for plan_name, details in plan_entry.items():
            if not isinstance(details, dict):
                continue

            plan_card = details.get("plan_card", {}) or {}
            premium_breakup = details.get("premium_breakup", {}) or {}
            addons_block = details.get("addons")
            idv_block = details.get("idv") or {}

            normalized_category = normalize_plan_category(plan_name)

            premium_value = extract_signed_amount(premium_breakup.get("final_premium"))
            premium_display = format_premium(premium_value) if premium_value else ""

            description = ", ".join(plan_card.get("details", []) or [])

            addons = _normalize_godigit_addons(addons_block)

            plan_info = {
                "plan_id": plan_name.lower().replace(" ", "_"),
                "plan_name": plan_name,
                "category": normalized_category or plan_name.lower(),
                "category_display": get_plan_category_label(
                    normalized_category, plan_name
                ),
                "premium_display": premium_display,
                "premium_value": premium_value,
                "description": description,
                "is_selected": "Most Popular" in description,
                "badge": "",
                "addons": addons,
                "benefits": plan_card.get("details", []) or [],
                "insurer": "Go Digit",
                "idv": build_idv_info(idv_block, shared_idv_info),
                "pricing_breakdown": build_godigit_pricing(premium_breakup),
                "claim_status": normalized_claim_status,
            }

            plans.append(plan_info)

    return plans


def normalize_make_display(make: str) -> str:
    """Normalize make for display (e.g., 'tata' -> 'Tata Motors')"""
    if not make:
        return ""
    make_lower = make.strip().lower()

    make_mappings = {
        "tata": "Tata Motors",
        "tata motors": "Tata Motors",
        "hyundai": "Hyundai",
        "hyundai motors": "Hyundai",
        "honda": "Honda",
        "honda motors": "Honda",
        "maruti": "Maruti Suzuki",
        "maruti suzuki": "Maruti Suzuki",
        "toyota": "Toyota",
        "toyota motors": "Toyota",
    }

    for key, value in make_mappings.items():
        if key in make_lower:
            return value

    return make.strip().title()


def normalize_model_display(model: str) -> str:
    """Normalize model for display (e.g., 'nexon' -> 'Nexon')"""
    model_lower = model.strip().lower()
    if "nexon" in model_lower:
        return "Nexon"

    if "i20" or "i 20" in model_lower:
        return "I20"
    if not model:
        return ""
    return model.strip().title()


def normalize_make_model(make: str, model: str) -> Tuple[str, str]:
    """Normalize make and model names for matching (returns normalized keys)"""
    make_norm = normalize_make_display(make)
    model_norm = normalize_model_display(model)

    return make_norm, model_norm


def split_model_variant(model_variant: str) -> Tuple[str, str]:
    if not model_variant:
        return "", ""

    cleaned = model_variant.strip()

    # Normalized model (e.g. "I 20" -> "I20")
    model = normalize_model_display(cleaned).strip()

    # Build a flexible regex: allow spaces between every character
    # Example: "I20" -> "I\s*2\s*0"
    spaced_pattern = r"\s*".join(map(re.escape, model))

    # Remove the model from the beginning OR anywhere in string
    pattern = re.compile(rf"^{spaced_pattern}[\s\-:–—]*", re.IGNORECASE)

    variant = pattern.sub("", cleaned).strip()

    return model, variant


def merge_insurer_data_into_car_map(
    car_data_map,
    insurer_data_list,
    insurer_key,
    entry_fields,
    extra_fields_func=None,
):
    """
    Merges data from a given insurer's data list into the car_data_map.

    Args:
        car_data_map (dict): The destination data map to update.
        insurer_data_list (list): List of insurer entry dicts.
        insurer_key (str): The key in car_data_map to use (e.g. "icici").
        entry_fields (list): List of fields to store, e.g. ["file", "registration"].
        extra_fields_func (callable, optional): If set, takes the entry and returns a dict of extra fields to add.
    """
    for entry in insurer_data_list:
        make = entry["make"]
        model = entry["model"]
        variant = entry["variant"]
        make_norm, model_norm = normalize_make_model(make, model)

        matched = False
        for (
            existing_make,
            existing_model,
            existing_variant,
        ), files in car_data_map.items():
            existing_make_norm, existing_model_norm = normalize_make_model(
                existing_make, existing_model
            )
            if (
                existing_make_norm == make_norm
                and (
                    existing_model_norm in model_norm
                    or model_norm in existing_model_norm
                )
                and (
                    existing_variant == variant
                    or variant in existing_variant
                    or existing_variant in variant
                )
            ):
                data_dict = {field: entry.get(field) for field in entry_fields}
                if extra_fields_func:
                    data_dict.update(extra_fields_func(entry))
                files[insurer_key].append(data_dict)
                matched = True
                break
        if not matched:
            key = (make, model, variant)
            if key not in car_data_map:
                car_data_map[key] = init_car_file_entry()
            data_dict = {field: entry.get(field) for field in entry_fields}
            if extra_fields_func:
                data_dict.update(extra_fields_func(entry))
            car_data_map[key][insurer_key].append(data_dict)


def scan_all_car_data() -> Dict[str, Any]:
    """Scan all data files and extract unique makes, models, and variants"""
    extracted_dir = Path("extracted")
    car_data_map = {}
    icici_data_list = []
    cholams_data_list = []
    royal_sundaram_data_list = []
    godigit_data_list = []

    acko_dir = extracted_dir / "acko"
    if acko_dir.exists():
        for file in acko_dir.glob("*.json"):
            try:
                data = load_json_data(str(file))
            except Exception:
                continue
            car_info = data.get("car_info", {})
            make_raw = car_info.get("vehicle_make", "").strip()
            model_raw = car_info.get("vehicle_model", "").strip()
            variant_raw = car_info.get("vehicle_variant", "").strip()

            make = normalize_make_display(make_raw)
            model = normalize_model_display(model_raw)
            _, variant = split_model_variant(variant_raw)

            if make and model and variant:
                key = (make, model, variant)
                if key not in car_data_map:
                    car_data_map[key] = init_car_file_entry()
                claim_status = infer_claim_status_from_filename(str(file))
                car_data_map[key]["acko"].append(
                    {
                        "file": str(file),
                        "claim_status": claim_status or "not_claimed",
                        "registration": car_info.get("registration_number", ""),
                    }
                )

    icici_dir = extracted_dir / "icici"
    if icici_dir.exists():
        for file in icici_dir.glob("*.json"):
            try:
                data = load_json_data(str(file))
            except Exception:
                continue
            make_raw = data.get("manufacturer", "").strip()
            model_raw = data.get("model", "").strip()

            make = normalize_make_display(make_raw)
            model = normalize_model_display(model_raw)
            _, variant = split_model_variant(model_raw)

            if make and model:
                claim_status = infer_claim_status_from_filename(str(file))
                icici_data_list.append(
                    {
                        "make": make,
                        "model": model,
                        "variant": variant,
                        "file": str(file),
                        "registration": (
                            file.stem.split("-")[0] if "-" in file.stem else ""
                        ),
                        "claim_status": claim_status,
                    }
                )

    cholams_dir = extracted_dir / "cholams"
    if cholams_dir.exists():
        for file in cholams_dir.glob("*.json"):
            try:
                data = load_json_data(str(file))
            except Exception:
                continue
            if isinstance(data, list) and len(data) > 0:
                car_info = data[0] if isinstance(data[0], dict) else {}
                make_raw = car_info.get("make", "").strip()
                model_raw = car_info.get("model", "").strip()
                variant_raw = car_info.get("variant", "").strip()

                make = normalize_make_display(make_raw)
                model = normalize_model_display(model_raw)
                _, variant = split_model_variant(variant_raw)

                if make and model:
                    claim_status = infer_claim_status_from_filename(str(file))
                    cholams_data_list.append(
                        {
                            "make": make,
                            "model": model,
                            "variant": variant,
                            "file": str(file),
                            "registration": car_info.get("registration_number", ""),
                            "claim_status": claim_status,
                        }
                    )

    royal_sundaram_dir = extracted_dir / "royal_sundaram"
    if royal_sundaram_dir.exists():
        for file in royal_sundaram_dir.glob("*.json"):
            try:
                data = load_json_data(str(file))
            except Exception:
                continue
            car_details = data.get("car_details", {}) or {}
            make_raw = car_details.get("manufacturer", "").strip()
            model_variant_raw = car_details.get("model_variant", "").strip()
            model_part, variant_part = split_model_variant(model_variant_raw)

            make = normalize_make_display(make_raw)
            model = normalize_model_display(model_part)
            variant = variant_part

            if make and model:
                claim_status = infer_claim_status_from_filename(str(file))
                royal_sundaram_data_list.append(
                    {
                        "make": make,
                        "model": model,
                        "variant": variant,
                        "file": str(file),
                        "registration": car_details.get("registration_number", ""),
                        "claim_status": claim_status,
                    }
                )

    godigit_dir = extracted_dir / "godigit"
    if godigit_dir.exists():
        for file in godigit_dir.glob("*.json"):
            try:
                data = load_json_data(str(file))
            except Exception:
                continue
            car_info = data.get("car_info", {}) or {}
            make_raw = str(car_info.get("vehicle_make", "")).strip()
            model_raw = str(car_info.get("vehicle_model", "")).strip()
            variant_raw = str(car_info.get("vehicle_variant", "")).strip()

            make = normalize_make_display(make_raw)
            model = normalize_model_display(model_raw)
            variant = variant_raw

            if make and model:
                claim_status = infer_claim_status_from_filename(str(file))
                godigit_data_list.append(
                    {
                        "make": make,
                        "model": model,
                        "variant": variant,
                        "file": str(file),
                        "registration": car_info.get("registration_number", ""),
                        "claim_status": claim_status,
                    }
                )

    merge_insurer_data_into_car_map(
        car_data_map,
        icici_data_list,
        "icici",
        ["file", "registration", "claim_status"],
    )
    merge_insurer_data_into_car_map(
        car_data_map,
        cholams_data_list,
        "cholams",
        ["file", "registration", "claim_status"],
    )
    merge_insurer_data_into_car_map(
        car_data_map,
        royal_sundaram_data_list,
        "royal_sundaram",
        ["file", "registration"],
        extra_fields_func=lambda entry: {
            "claim_status": normalize_claim_status(entry.get("claim_status", ""))
        },
    )

    merge_insurer_data_into_car_map(
        car_data_map,
        godigit_data_list,
        "godigit",
        ["file", "registration", "claim_status"],
    )

    return car_data_map


def get_unique_makes_models_variants(
    car_data_map: Dict[str, Any],
) -> Tuple[List[str], Dict[str, List[str]], Dict[str, Dict[str, List[str]]]]:
    """Extract unique makes, models, and variants from car data map using normalised car model names"""
    makes = set()
    models_by_make = {}
    variants_by_make_model = {}

    for (make, model, variant), _ in car_data_map.items():
        # Use normalized model here
        normalized_model = normalize_model_display(model)
        makes.add(make)
        if make not in models_by_make:
            models_by_make[make] = set()
        models_by_make[make].add(normalized_model)

        if make not in variants_by_make_model:
            variants_by_make_model[make] = {}
        if normalized_model not in variants_by_make_model[make]:
            variants_by_make_model[make][normalized_model] = set()
        variants_by_make_model[make][normalized_model].add(variant)

    makes_list = sorted(list(makes))
    models_by_make_sorted = {
        make: sorted(list(models)) for make, models in models_by_make.items()
    }
    variants_by_make_model_sorted = {
        make: {model: sorted(list(variants)) for model, variants in models.items()}
        for make, models in variants_by_make_model.items()
    }

    # print(makes_list, models_by_make_sorted, variants_by_make_model_sorted)
    return makes_list, models_by_make_sorted, variants_by_make_model_sorted


def format_premium(premium: Any) -> str:
    """Format premium for display"""
    if isinstance(premium, (int, float)):
        return f"₹{premium:,.0f}"
    if isinstance(premium, str):
        return premium
    return "N/A"


def save_normalized_data(
    car_key: Tuple[str, str, str],
    all_plans_by_insurer: Dict[str, List[Dict[str, Any]]],
    output_dir: str = "normalized_data",
) -> str:
    """Save normalized plan data to a JSON file.

    Args:
        car_key: Tuple of (make, model, variant)
        all_plans_by_insurer: Dictionary mapping insurer names to lists of plan dictionaries
        output_dir: Directory to save the JSON file (default: "normalized_data")

    Returns:
        Path to the saved JSON file
    """
    make, model, variant = car_key

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create a safe filename from car details
    safe_make = re.sub(r"[^\w\s-]", "", make).strip().replace(" ", "_")
    safe_model = re.sub(r"[^\w\s-]", "", model).strip().replace(" ", "_")
    safe_variant = re.sub(r"[^\w\s-]", "", variant).strip().replace(" ", "_")
    filename = f"{safe_make}_{safe_model}_{safe_variant}_normalized.json"
    file_path = output_path / filename

    # Prepare the data structure
    normalized_data = {
        "car_info": {
            "make": make,
            "model": model,
            "variant": variant,
        },
        "plans_by_insurer": all_plans_by_insurer,
        "summary": {
            "total_plans": sum(len(plans) for plans in all_plans_by_insurer.values()),
            "insurers": list(all_plans_by_insurer.keys()),
            "insurer_counts": {
                insurer: len(plans) for insurer, plans in all_plans_by_insurer.items()
            },
        },
    }

    # Save to JSON file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(normalized_data, f, indent=2, ensure_ascii=False)

    return str(file_path)
