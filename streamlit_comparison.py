import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st


PLAN_CATEGORY_LABELS = {
    "comp": "Comprehensive",
    "od": "Own Damage",
    "tp": "Third Party",
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


def get_available_cars() -> Dict[str, List[str]]:
    """Get list of available cars for each insurer"""
    extracted_dir = Path("extracted")
    cars_by_insurer = {}

    for insurer_dir in ["acko", "icici"]:
        insurer_path = extracted_dir / insurer_dir
        if insurer_path.exists():
            files = list(insurer_path.glob("*.json"))
            # Extract unique car registration numbers
            cars = set()
            for file in files:
                # Extract registration number from filename (e.g., MH04KW1827-claimed.json -> MH04KW1827)
                reg_num = file.stem.split("-")[0]
                cars.add(reg_num)
            cars_by_insurer[insurer_dir] = sorted(list(cars))

    return cars_by_insurer


def format_premium(premium: Any) -> str:
    """Format premium for display"""
    if isinstance(premium, (int, float)):
        return f"₹{premium:,.0f}"
    if isinstance(premium, str):
        return premium
    return "N/A"


def display_plan_card(
    plan: Dict[str, Any], insurer: str, car_info: Optional[Dict[str, Any]] = None
):
    """Display a single plan card"""
    with st.container():
        # Card styling
        st.markdown(
            """
            <style>
            .plan-card {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                margin: 10px 0;
                background-color: #f9f9f9;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

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
            # Clean HTML tags for display
            import re

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


def main():
    st.set_page_config(
        page_title="Insurance Plans Comparison",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Insurance Plans Comparison")
    st.markdown("Compare insurance plans from different insurers side-by-side")

    # Get available cars
    cars_by_insurer = get_available_cars()

    if not cars_by_insurer:
        st.error("No insurance data found. Please check the 'extracted' directory.")
        st.stop()

    # Sidebar filters
    st.sidebar.header("Filters")

    # Select car registration number
    all_cars = set()
    for cars in cars_by_insurer.values():
        all_cars.update(cars)

    selected_car = st.sidebar.selectbox(
        "Select Car Registration", options=sorted(list(all_cars)), index=0
    )

    # Check which insurers have data for this car
    available_insurers = []
    for insurer in ["acko", "icici"]:
        if selected_car in cars_by_insurer.get(insurer, []):
            available_insurers.append(insurer)

    if not available_insurers:
        st.warning(f"No insurance data found for car {selected_car}")
        st.stop()

    # Select claim status (for acko)
    claim_status = st.sidebar.selectbox(
        "Claim Status (for Acko)", options=["not_claimed", "claimed"], index=0
    )

    # Load data for selected car
    acko_data = None
    icici_data = None

    extracted_dir = Path("extracted")

    # Load Acko data
    if "acko" in available_insurers:
        acko_file = extracted_dir / "acko" / f"{selected_car}-{claim_status}.json"
        if acko_file.exists():
            try:
                acko_data = load_acko_data(str(acko_file))
            except Exception as e:
                st.error(f"Error loading Acko data: {e}")

    # Load ICICI data
    if "icici" in available_insurers:
        icici_file = extracted_dir / "icici" / f"{selected_car}-not_claimed.json"
        if icici_file.exists():
            try:
                icici_data = load_icici_data(str(icici_file))
            except Exception as e:
                st.error(f"Error loading ICICI data: {e}")

    # Get plans
    acko_plans = []
    icici_plans = []

    if acko_data:
        acko_plans = get_acko_plans(acko_data)

    if icici_data:
        icici_plans = get_icici_plans(icici_data)

    # Plan selection
    st.sidebar.header("Plan Selection")

    combined_categories = sorted(
        {
            plan.get("category")
            for plan in (acko_plans + icici_plans)
            if plan.get("category")
        }
    )

    selected_plan_category = ""
    if combined_categories:
        plan_category_options = [("All Plan Types", "")]
        for category_value in combined_categories:
            plan_category_options.append(
                (get_plan_category_label(category_value), category_value)
            )
        selected_category_label = st.sidebar.selectbox(
            "Plan Type Filter",
            options=[label for label, _ in plan_category_options],
            index=0,
        )
        selected_plan_category = dict(plan_category_options).get(
            selected_category_label, ""
        )

    acko_plan_options: List[Tuple[str, int]] = []
    for idx, plan in enumerate(acko_plans):
        if selected_plan_category and plan.get("category") != selected_plan_category:
            continue
        label = f"{len(acko_plan_options)+1}. {plan.get('plan_name', 'Unknown')}"
        acko_plan_options.append((label, idx))

    icici_plan_options: List[Tuple[str, int]] = []
    for idx, plan in enumerate(icici_plans):
        if selected_plan_category and plan.get("category") != selected_plan_category:
            continue
        label = f"{len(icici_plan_options)+1}. {plan.get('plan_name', 'Unknown')}"
        icici_plan_options.append((label, idx))

    acko_plan_names = [label for label, _ in acko_plan_options]
    icici_plan_names = [label for label, _ in icici_plan_options]

    selected_acko_idx = None
    selected_acko2_idx = None
    selected_icici_idx = None
    selected_icici2_idx = None

    if acko_plan_names:
        acko_plan_lookup = dict(acko_plan_options)
        selected_acko = st.sidebar.selectbox(
            "Acko Plan 1", options=acko_plan_names, index=0
        )
        selected_acko_idx = acko_plan_lookup.get(selected_acko)

        if len(acko_plan_names) > 1:
            # Filter out the first selected plan from options
            remaining_acko = [name for name in acko_plan_names if name != selected_acko]
            selected_acko2 = st.sidebar.selectbox(
                "Acko Plan 2",
                options=remaining_acko,
                index=0 if remaining_acko else None,
            )
            if selected_acko2:
                selected_acko2_idx = acko_plan_lookup.get(selected_acko2)
    elif acko_plans:
        st.sidebar.info("No Acko plans available for the selected plan type.")

    if icici_plan_names:
        selected_icici = st.sidebar.selectbox(
            "ICICI Plan 1", options=icici_plan_names, index=0
        )
        icici_plan_lookup = dict(icici_plan_options)
        selected_icici_idx = icici_plan_lookup.get(selected_icici)

        if len(icici_plan_names) > 1:
            # Filter out the first selected plan from options
            remaining_icici = [
                name for name in icici_plan_names if name != selected_icici
            ]
            selected_icici2 = st.sidebar.selectbox(
                "ICICI Plan 2",
                options=remaining_icici,
                index=0 if remaining_icici else None,
            )
            if selected_icici2:
                selected_icici2_idx = icici_plan_lookup.get(selected_icici2)
    elif icici_plans:
        st.sidebar.info("No ICICI plans available for the selected plan type.")

    # Display car info
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Car Information")

    if acko_data:
        car_info = acko_data.get("car_info", {})
        st.sidebar.write(
            f"**Registration:** {car_info.get('registration_number', selected_car)}"
        )
        st.sidebar.write(f"**Make:** {car_info.get('vehicle_make', 'N/A')}")
        st.sidebar.write(f"**Model:** {car_info.get('vehicle_model', 'N/A')}")
        st.sidebar.write(f"**Variant:** {car_info.get('vehicle_variant', 'N/A')}")
        idv = car_info.get("idv_selected", car_info.get("idv", 0))
        if idv:
            st.sidebar.write(f"**IDV:** ₹{idv:,}")
    elif icici_data:
        st.sidebar.write(f"**Registration:** {selected_car}")
        st.sidebar.write(f"**Manufacturer:** {icici_data.get('manufacturer', 'N/A')}")
        st.sidebar.write(f"**Model:** {icici_data.get('model', 'N/A')}")
        st.sidebar.write(f"**City:** {icici_data.get('city_of_registration', 'N/A')}")
        idv = icici_data.get("idv", 0)
        if idv:
            st.sidebar.write(f"**IDV:** ₹{idv:,}")
    else:
        st.sidebar.write(f"**Registration:** {selected_car}")

    # 2x2 Grid Display
    st.markdown("---")
    st.subheader(f"Plan Comparison for {selected_car}")

    # Create 2x2 grid layout
    # Top row: Plan 1 from each insurer
    col1_top, col2_top = st.columns(2)

    with col1_top:
        st.markdown("### 🏢 Acko Insurance - Plan 1")
        if selected_acko_idx is not None and selected_acko_idx < len(acko_plans):
            display_plan_card(
                acko_plans[selected_acko_idx],
                "acko",
                acko_data.get("car_info") if acko_data else None,
            )
        elif not acko_plans:
            st.info("No Acko plans available")
        else:
            st.warning("Please select a plan")

    with col2_top:
        st.markdown("### 🏢 ICICI Insurance - Plan 1")
        if selected_icici_idx is not None and selected_icici_idx < len(icici_plans):
            display_plan_card(icici_plans[selected_icici_idx], "icici", icici_data)
        elif not icici_plans:
            st.info("No ICICI plans available")
        else:
            st.warning("Please select a plan")

    # Bottom row: Plan 2 from each insurer (if available)
    if selected_acko2_idx is not None or selected_icici2_idx is not None:
        st.markdown("---")
        col1_bottom, col2_bottom = st.columns(2)

        with col1_bottom:
            st.markdown("### 🏢 Acko Insurance - Plan 2")
            if selected_acko2_idx is not None and selected_acko2_idx < len(acko_plans):
                display_plan_card(
                    acko_plans[selected_acko2_idx],
                    "acko",
                    acko_data.get("car_info") if acko_data else None,
                )
            else:
                st.info("Only one plan available")

        with col2_bottom:
            st.markdown("### 🏢 ICICI Insurance - Plan 2")
            if selected_icici2_idx is not None and selected_icici2_idx < len(
                icici_plans
            ):
                display_plan_card(icici_plans[selected_icici2_idx], "icici", icici_data)
            else:
                st.info("Only one plan available")

    # Summary comparison table
    st.markdown("---")
    st.subheader("Premium Comparison Summary")

    comparison_data = []

    if selected_acko_idx is not None and selected_acko_idx < len(acko_plans):
        plan = acko_plans[selected_acko_idx]
        comparison_data.append(
            {
                "Insurer": "Acko",
                "Plan": plan.get("plan_name", "Unknown"),
                "Premium": format_premium(plan.get("premium_value", 0)),
                "Category": plan.get("category_display")
                or plan.get("category", "").upper(),
            }
        )

    if selected_acko2_idx is not None and selected_acko2_idx < len(acko_plans):
        plan = acko_plans[selected_acko2_idx]
        comparison_data.append(
            {
                "Insurer": "Acko",
                "Plan": plan.get("plan_name", "Unknown"),
                "Premium": format_premium(plan.get("premium_value", 0)),
                "Category": plan.get("category_display")
                or plan.get("category", "").upper(),
            }
        )

    if selected_icici_idx is not None and selected_icici_idx < len(icici_plans):
        plan = icici_plans[selected_icici_idx]
        comparison_data.append(
            {
                "Insurer": "ICICI",
                "Plan": plan.get("plan_name", "Unknown"),
                "Premium": format_premium(plan.get("premium_value", 0)),
                "Category": plan.get("category_display")
                or plan.get("category", "").upper(),
            }
        )

    if selected_icici2_idx is not None and selected_icici2_idx < len(icici_plans):
        plan = icici_plans[selected_icici2_idx]
        comparison_data.append(
            {
                "Insurer": "ICICI",
                "Plan": plan.get("plan_name", "Unknown"),
                "Premium": format_premium(plan.get("premium_value", 0)),
                "Category": plan.get("category_display")
                or plan.get("category", "").upper(),
            }
        )

    if comparison_data:
        import pandas as pd

        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
