#!/usr/bin/env python3
"""
Extractor for ACKO storefront JSON plan snapshots.

Given a raw JSON dump (like the ones inside `insurer/acko/`), the script
collects high-level car information, plan cards (plan id, name, premium,
category, etc.), and the available add-ons per plan.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


CAR_INFO_FIELDS = [
    "registration_number",
    "vehicle_make",
    "vehicle_model",
    "vehicle_variant",
    "variant_id",
    "fuel_type",
    "engine_cc",
    "registration_year",
    "registration_month",
    "rto_zone",
    "is_commercial",
    "previous_policy_type",
    "previous_insurer",
    "previous_policy_expiry_date",
    "previous_policy_claims_count",
    "last_year_claim_flag",
    "current_idv",
    "recommended_idv",
    "min_idv",
    "max_idv",
    "idv_selected",
    "plan_selected",
]


def iter_objects(root: Any) -> Iterable[Dict[str, Any]]:
    """Yield every dictionary contained in `root` recursively."""
    stack: List[Any] = [root]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def parse_price(value: Any) -> Optional[float]:
    """Convert ACKO display prices like '9,020' or '₹ 12,454' into floats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        cleaned = re.sub(r"[^\d.]", "", cleaned)
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def extract_car_info(data: Any) -> Dict[str, Any]:
    """Find the dictionary that carries the registration details."""
    for obj in iter_objects(data):
        if {"registration_number", "vehicle_make"}.issubset(obj.keys()):
            return {field: obj.get(field) for field in CAR_INFO_FIELDS if field in obj}
    return {}


def extract_addon_map(data: Any) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a mapping of planId -> [addon objects].

    The plans expose their add-ons through modal definitions whose props contain
    `addonId` and an `optionId == 'addons'`.
    """
    addon_map: Dict[str, List[Dict[str, Any]]] = {}

    for obj in iter_objects(data):
        props = obj.get("data", {}).get("props", {})
        if not isinstance(props, dict):
            continue
        plan_addon_id = props.get("addonId")
        options = props.get("options")
        if not plan_addon_id or not isinstance(options, list):
            continue

        for option in options:
            if option.get("optionId") != "addons":
                continue
            iterable = option.get("iterableData") or []
            formatted: List[Dict[str, Any]] = []
            for item in iterable:
                price_block = item.get("price", {})
                formatted.append(
                    {
                        "id": item.get("id"),
                        "display_name": item.get("display_name"),
                        "description": item.get("description"),
                        "title": item.get("title"),
                        "net_premium": parse_price(price_block.get("net_premium")),
                        "gross_premium": parse_price(price_block.get("gross_premium")),
                        "display_net_premium": item.get("display_net_premium"),
                        "is_selected": item.get("is_selected"),
                        "badge": item.get("badge", {}).get("text"),
                    }
                )
            addon_map[plan_addon_id] = formatted

    return addon_map


def extract_plan_cards(data: Any) -> List[Dict[str, Any]]:
    """Extract ACKO plan cards along with their add-ons."""
    addon_map = extract_addon_map(data)
    plans: List[Dict[str, Any]] = []

    for obj in iter_objects(data):
        if obj.get("type") != "plan_card":
            continue
        props = obj.get("data", {}).get("props", {})
        if not isinstance(props, dict):
            continue

        plan_id = props.get("planId")
        plan = {
            "plan_id": plan_id,
            "plan_name": props.get("planName"),
            "category": props.get("category"),
            "premium_display": props.get("premium"),
            "premium_value": parse_price(props.get("premium")),
            "description": props.get("description"),
            "is_selected": props.get("isSelected"),
            "badge": props.get("badge", {}).get("text"),
            "variants_count": props.get("variantsLength"),
            "addons": addon_map.get(plan_id, []),
        }
        plans.append(plan)

    return plans


def extract_acko_snapshot(json_data: Any) -> Dict[str, Any]:
    """Return the normalized payload for a single ACKO JSON dump."""
    return {
        "car_info": extract_car_info(json_data),
        "plans": extract_plan_cards(json_data),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract ACKO plans and add-ons.")
    parser.add_argument(
        "input_json", type=Path, help="Path to the raw ACKO JSON file to parse."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path to store the extracted summary JSON.",
    )
    args = parser.parse_args()

    with args.input_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    extracted = extract_acko_snapshot(data)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(extracted, handle, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(extracted, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
