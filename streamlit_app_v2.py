import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st
import pandas as pd


PLAN_CATEGORY_LABELS = {
    "comp": "Comprehensive",
    "od": "Own Damage",
    "tp": "Third Party",
    "zd": "Zero Depreciation",
}


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
    # Remove currency symbols and commas, extract number
    numbers = re.findall(r"[\d,]+", premium_str.replace("₹", "").replace(",", ""))
    if numbers:
        try:
            return float(numbers[0].replace(",", ""))
        except:
            return 0.0
    return 0.0


def load_acko_data(file_path: str) -> Dict[str, Any]:
    """Load and parse Acko insurance data"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_icici_data(file_path: str) -> Dict[str, Any]:
    """Load and parse ICICI insurance data"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_acko_plans(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract plans from Acko data structure"""
    plans = []
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
            "badge": plan.get("badge", ""),
            "addons": plan.get("addons", []),
            "insurer": "Acko",
        }
        plans.append(plan_info)
    return plans


def get_icici_plans(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract plans from ICICI data structure"""
    plans = []
    plans_offered = data.get("plans_offered", {})
    premiums_list = plans_offered.get("premiums", [])

    for premium_info in premiums_list:
        plan_type = premium_info.get("plan_type", "")
        button_text = premium_info.get("button_text", "")
        title = button_text.split("\n")[0].replace("Recommended\n", "").strip()
        normalized_category = normalize_plan_category(plan_type)

        premium_summary = premium_info.get("premium", {}).get("premium_summary", {})
        total_premium_str = premium_summary.get("total_premium", "₹0")
        base_premium_str = premium_summary.get("base_premium", "₹0")

        # Extract description from additional_covers_breakdown
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
            "badge": "Recommended" if "Recommended" in button_text else "",
            "addons": premium_summary.get("additional_covers_breakdown", []),
            "benefits": [],
            "insurer": "ICICI",
        }

        # Get benefits from plans structure
        plans_list = plans_offered.get("plans", [])
        if plans_list and len(plans_list) > 0:
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


def normalize_make_model(make: str, model: str) -> Tuple[str, str]:
    """Normalize make and model names for matching"""
    make_norm = make.strip().lower()
    model_norm = model.strip().lower()

    # Handle common variations
    make_mappings = {
        "tata motors": "tata",
        "tata": "tata",
    }

    for key, value in make_mappings.items():
        if key in make_norm:
            make_norm = value
            break

    return make_norm, model_norm


def scan_all_car_data() -> Dict[str, Any]:
    """Scan all data files and extract unique makes, models, and variants"""
    extracted_dir = Path("extracted")
    car_data_map = {}  # Maps (make, model, variant) -> list of file paths
    icici_data_list = []  # Store ICICI data separately for matching

    # Scan Acko files
    acko_dir = extracted_dir / "acko"
    if acko_dir.exists():
        for file in acko_dir.glob("*.json"):
            try:
                data = load_acko_data(str(file))
                car_info = data.get("car_info", {})
                make = car_info.get("vehicle_make", "").strip()
                model = car_info.get("vehicle_model", "").strip()
                variant = car_info.get("vehicle_variant", "").strip()

                if make and model and variant:
                    key = (make, model, variant)
                    if key not in car_data_map:
                        car_data_map[key] = {"acko": [], "icici": []}
                    car_data_map[key]["acko"].append(
                        {
                            "file": str(file),
                            "claim_status": (
                                file.stem.split("-")[-1]
                                if "-" in file.stem
                                else "not_claimed"
                            ),
                            "registration": car_info.get("registration_number", ""),
                        }
                    )
            except Exception as e:
                continue

    # Scan ICICI files
    icici_dir = extracted_dir / "icici"
    if icici_dir.exists():
        for file in icici_dir.glob("*.json"):
            try:
                data = load_icici_data(str(file))
                make = data.get("manufacturer", "").strip()
                model = data.get("model", "").strip()

                if make and model:
                    icici_data_list.append(
                        {
                            "make": make,
                            "model": model,
                            "file": str(file),
                            "registration": (
                                file.stem.split("-")[0] if "-" in file.stem else ""
                            ),
                        }
                    )
            except Exception as e:
                continue

    # Match ICICI data with Acko entries based on make and model
    for icici_entry in icici_data_list:
        icici_make = icici_entry["make"]
        icici_model = icici_entry["model"]
        icici_make_norm, icici_model_norm = normalize_make_model(
            icici_make, icici_model
        )

        matched = False
        for (acko_make, acko_model, acko_variant), files in car_data_map.items():
            acko_make_norm, acko_model_norm = normalize_make_model(
                acko_make, acko_model
            )

            # Match if make matches and model is similar
            if acko_make_norm == icici_make_norm and (
                acko_model_norm in icici_model_norm
                or icici_model_norm in acko_model_norm
            ):
                files["icici"].append(
                    {
                        "file": icici_entry["file"],
                        "registration": icici_entry["registration"],
                    }
                )
                matched = True
                break

        # If no match found, create a new entry with model as variant
        if not matched:
            key = (icici_make, icici_model, icici_model)
            if key not in car_data_map:
                car_data_map[key] = {"acko": [], "icici": []}
            car_data_map[key]["icici"].append(
                {
                    "file": icici_entry["file"],
                    "registration": icici_entry["registration"],
                }
            )

    return car_data_map


def get_unique_makes_models_variants(
    car_data_map: Dict[str, Any],
) -> Tuple[List[str], Dict[str, List[str]], Dict[str, Dict[str, List[str]]]]:
    """Extract unique makes, models, and variants from car data map"""
    makes = set()
    models_by_make = {}
    variants_by_make_model = {}

    for (make, model, variant), _ in car_data_map.items():
        makes.add(make)
        if make not in models_by_make:
            models_by_make[make] = set()
        models_by_make[make].add(model)

        if make not in variants_by_make_model:
            variants_by_make_model[make] = {}
        if model not in variants_by_make_model[make]:
            variants_by_make_model[make][model] = set()
        variants_by_make_model[make][model].add(variant)

    # Convert sets to sorted lists
    makes_list = sorted(list(makes))
    models_by_make_sorted = {
        make: sorted(list(models)) for make, models in models_by_make.items()
    }
    variants_by_make_model_sorted = {
        make: {model: sorted(list(variants)) for model, variants in models.items()}
        for make, models in variants_by_make_model.items()
    }

    return makes_list, models_by_make_sorted, variants_by_make_model_sorted


def format_premium(premium: Any) -> str:
    """Format premium for display"""
    if isinstance(premium, (int, float)):
        return f"₹{premium:,.0f}"
    if isinstance(premium, str):
        return premium
    return "N/A"


def display_plan_card_compact(plan: Dict[str, Any]):
    """Display a compact plan card for homepage"""
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.markdown(f"**{plan.get('plan_name', 'Unknown Plan')}**")
            category = plan.get("category_display") or plan.get("category", "").upper()
            if category:
                st.caption(f"Type: {category}")

        with col2:
            premium_value = plan.get("premium_value", 0.0)
            premium_display = plan.get("premium_display", format_premium(premium_value))
            st.markdown(f"**{premium_display}**")

        with col3:
            badge = plan.get("badge", "")
            if badge:
                st.markdown(
                    f"<span style='background-color: #ff6b6b; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75em;'>{badge}</span>",
                    unsafe_allow_html=True,
                )


def display_plan_card(
    plan: Dict[str, Any], insurer: str, car_info: Optional[Dict[str, Any]] = None
):
    """Display a single plan card"""
    with st.container():
        # Header with plan name and badge
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.markdown(f"#### {plan.get('plan_name', 'Unknown Plan')}")
        with header_col2:
            badge = plan.get("badge", "")
            if badge:
                st.markdown(
                    f"<span style='background-color: #ff6b6b; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75em;'>{badge}</span>",
                    unsafe_allow_html=True,
                )

        # Premium - highlight
        premium_value = plan.get("premium_value", 0.0)
        premium_display = plan.get("premium_display", format_premium(premium_value))
        st.markdown(f"**💰 Premium:** `{premium_display}`")

        # Category
        category = plan.get("category_display") or plan.get("category", "").upper()
        if category:
            st.markdown(f"**📋 Type:** {category}")

        # Description
        description = plan.get("description", "")
        if description:
            clean_desc = re.sub(r"<[^>]+>", "", description)
            if len(clean_desc) > 120:
                clean_desc = clean_desc[:120] + "..."
            st.markdown(f"*{clean_desc}*")

        # Benefits/Addons
        benefits = plan.get("benefits", [])
        addons = plan.get("addons", [])

        if benefits:
            with st.expander("✨ Benefits", expanded=False):
                for benefit in benefits:
                    st.markdown(f"• {benefit}")

        if addons:
            with st.expander("🔧 Add-ons & Covers", expanded=False):
                for addon in addons:
                    if isinstance(addon, dict):
                        name = addon.get("name", addon.get("display_name", "Unknown"))
                        price = addon.get("price", addon.get("net_premium", 0))
                        if price:
                            price_str = format_premium(price)
                            st.markdown(f"• **{name}**: {price_str}")
                        else:
                            st.markdown(f"• **{name}**")
                    else:
                        st.markdown(f"• {addon}")


def homepage():
    """Homepage with car selection dropdowns"""
    st.title("🏠 Insurance Plans Overview")
    st.markdown(
        "Select your car to view all available insurance plans from different insurers"
    )

    # Initialize session state
    if "car_data_map" not in st.session_state:
        with st.spinner("Loading car data..."):
            st.session_state.car_data_map = scan_all_car_data()

    car_data_map = st.session_state.car_data_map

    if not car_data_map:
        st.error("No insurance data found. Please check the 'extracted' directory.")
        return

    # Get unique makes, models, variants
    makes, models_by_make, variants_by_make_model = get_unique_makes_models_variants(
        car_data_map
    )

    if not makes:
        st.error("No car data available.")
        return

    # Car selection dropdowns
    st.markdown("### Select Your Car")
    col1, col2, col3 = st.columns(3)

    with col1:
        selected_make = st.selectbox("Car Make", options=[""] + makes, index=0)

    selected_model = ""
    if selected_make:
        with col2:
            available_models = models_by_make.get(selected_make, [])
            selected_model = st.selectbox(
                "Car Model", options=[""] + available_models, index=0
            )

    selected_variant = ""
    if selected_make and selected_model:
        with col3:
            available_variants = variants_by_make_model.get(selected_make, {}).get(
                selected_model, []
            )
            selected_variant = st.selectbox(
                "Car Variant", options=[""] + available_variants, index=0
            )

    # Display plans when all three are selected
    if selected_make and selected_model and selected_variant:
        key = (selected_make, selected_model, selected_variant)
        car_files = car_data_map.get(key, {})

        if not car_files.get("acko") and not car_files.get("icici"):
            st.warning(
                f"No insurance data found for {selected_make} {selected_model} {selected_variant}"
            )
            return

        st.markdown("---")
        st.subheader(
            f"Available Plans for {selected_make} {selected_model} {selected_variant}"
        )

        # Load and display plans grouped by insurer
        all_plans_by_insurer = {}

        # Load Acko plans
        acko_plans = []
        if car_files.get("acko"):
            # Use not_claimed by default, or first available
            acko_file_info = next(
                (f for f in car_files["acko"] if f["claim_status"] == "not_claimed"),
                car_files["acko"][0],
            )
            try:
                acko_data = load_acko_data(acko_file_info["file"])
                acko_plans = get_acko_plans(acko_data)
                all_plans_by_insurer["Acko"] = acko_plans
            except Exception as e:
                st.error(f"Error loading Acko data: {e}")

        # Load ICICI plans
        icici_plans = []
        if car_files.get("icici"):
            icici_file_info = car_files["icici"][0]
            try:
                icici_data = load_icici_data(icici_file_info["file"])
                icici_plans = get_icici_plans(icici_data)
                all_plans_by_insurer["ICICI"] = icici_plans
            except Exception as e:
                st.error(f"Error loading ICICI data: {e}")

        # Display plans in accordions grouped by insurer
        for insurer_name, plans in all_plans_by_insurer.items():
            with st.expander(
                f"🏢 {insurer_name} Insurance ({len(plans)} plans)", expanded=True
            ):
                if plans:
                    for plan in plans:
                        display_plan_card_compact(plan)
                        st.markdown("---")
                else:
                    st.info(f"No plans available from {insurer_name}")

        # Store selected car info in session state for comparison page
        st.session_state.selected_car_key = key
        st.session_state.selected_car_files = car_files
        st.session_state.all_plans_by_insurer = all_plans_by_insurer

        # Button to go to comparison page
        if st.button("🔍 Compare Plans", type="primary", use_container_width=True):
            st.session_state.page = "comparison"
            st.rerun()


def comparison_page():
    """Plan comparison page"""
    st.title("🔍 Plan Comparison")

    if (
        "selected_car_key" not in st.session_state
        or "all_plans_by_insurer" not in st.session_state
    ):
        st.warning("Please select a car from the homepage first.")
        if st.button("← Go to Homepage"):
            st.session_state.page = "homepage"
            st.rerun()
        return

    selected_car_key = st.session_state.selected_car_key
    all_plans_by_insurer = st.session_state.all_plans_by_insurer

    make, model, variant = selected_car_key
    st.markdown(f"**Comparing plans for:** {make} {model} {variant}")

    # Collect all plans
    all_plans = []
    for insurer, plans in all_plans_by_insurer.items():
        for plan in plans:
            plan_copy = plan.copy()
            plan_copy["insurer"] = insurer
            all_plans.append(plan_copy)

    if not all_plans:
        st.warning("No plans available for comparison.")
        if st.button("← Go to Homepage"):
            st.session_state.page = "homepage"
            st.rerun()
        return

    # Filters
    st.sidebar.header("Filters")

    # Plan type filter
    available_categories = sorted(
        set(plan.get("category", "") for plan in all_plans if plan.get("category"))
    )
    category_options = ["All Plan Types"] + [
        get_plan_category_label(cat) for cat in available_categories
    ]
    selected_category_label = st.sidebar.selectbox(
        "Plan Type", options=category_options, index=0
    )

    selected_category = ""
    if selected_category_label != "All Plan Types":
        # Find the category key for the selected label
        for cat in available_categories:
            if get_plan_category_label(cat) == selected_category_label:
                selected_category = cat
                break

    # Filter plans
    filtered_plans = all_plans
    if selected_category:
        filtered_plans = [
            p for p in all_plans if p.get("category") == selected_category
        ]

    # Insurer filter
    available_insurers = sorted(set(plan.get("insurer", "") for plan in filtered_plans))
    selected_insurers = st.sidebar.multiselect(
        "Insurers", options=available_insurers, default=available_insurers
    )

    if selected_insurers:
        filtered_plans = [
            p for p in filtered_plans if p.get("insurer") in selected_insurers
        ]

    # Price range filter
    if filtered_plans:
        premiums = [p.get("premium_value", 0) for p in filtered_plans]
        min_premium = min(premiums)
        max_premium = max(premiums)

        price_range = st.sidebar.slider(
            "Price Range (₹)",
            min_value=int(min_premium),
            max_value=int(max_premium),
            value=(int(min_premium), int(max_premium)),
        )

        filtered_plans = [
            p
            for p in filtered_plans
            if price_range[0] <= p.get("premium_value", 0) <= price_range[1]
        ]

    # Display comparison
    st.markdown("---")

    if not filtered_plans:
        st.info("No plans match the selected filters.")
        return

    # Group by plan type for better comparison
    plans_by_category = {}
    for plan in filtered_plans:
        category = plan.get("category_display") or plan.get("category", "Other")
        if category not in plans_by_category:
            plans_by_category[category] = []
        plans_by_category[category].append(plan)

    # Display comparison table
    st.subheader("Premium Comparison Table")
    comparison_data = []
    for plan in filtered_plans:
        comparison_data.append(
            {
                "Insurer": plan.get("insurer", ""),
                "Plan Name": plan.get("plan_name", ""),
                "Type": plan.get("category_display")
                or plan.get("category", "").upper(),
                "Premium": format_premium(plan.get("premium_value", 0)),
                "Badge": plan.get("badge", ""),
            }
        )

    if comparison_data:
        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Detailed comparison by category
    st.markdown("---")
    st.subheader("Detailed Plan Comparison")

    for category, plans in sorted(plans_by_category.items()):
        st.markdown(f"### {category} Plans")

        # Sort plans by premium
        plans_sorted = sorted(plans, key=lambda x: x.get("premium_value", 0))

        # Display in columns
        num_cols = min(len(plans_sorted), 3)
        if num_cols > 0:
            cols = st.columns(num_cols)
            for idx, plan in enumerate(plans_sorted):
                with cols[idx % num_cols]:
                    display_plan_card(plan, plan.get("insurer", ""))

        st.markdown("---")

    # Add-ons comparison
    st.markdown("---")
    st.subheader("Add-ons Comparison")

    # Collect all unique add-ons
    all_addons_map = {}
    for plan in filtered_plans:
        insurer = plan.get("insurer", "")
        plan_name = plan.get("plan_name", "")
        addons = plan.get("addons", [])

        for addon in addons:
            if isinstance(addon, dict):
                addon_name = addon.get("name", addon.get("display_name", "Unknown"))
                addon_price = addon.get("price", addon.get("net_premium", 0))

                if addon_name not in all_addons_map:
                    all_addons_map[addon_name] = []

                all_addons_map[addon_name].append(
                    {
                        "insurer": insurer,
                        "plan": plan_name,
                        "price": addon_price,
                    }
                )

    if all_addons_map:
        for addon_name, addon_info in sorted(all_addons_map.items()):
            with st.expander(f"🔧 {addon_name}"):
                for info in addon_info:
                    price_str = (
                        format_premium(info["price"]) if info["price"] else "Included"
                    )
                    st.markdown(f"**{info['insurer']} - {info['plan']}**: {price_str}")

    # Back button
    if st.button("← Back to Homepage"):
        st.session_state.page = "homepage"
        st.rerun()


def main():
    st.set_page_config(
        page_title="Insurance Plans Comparison",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize page state
    if "page" not in st.session_state:
        st.session_state.page = "homepage"

    # Navigation
    if st.session_state.page == "homepage":
        homepage()
    elif st.session_state.page == "comparison":
        comparison_page()


if __name__ == "__main__":
    main()
