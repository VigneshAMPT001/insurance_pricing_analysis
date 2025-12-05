import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd

from app_v2_utils import (
    format_claim_status,
    normalize_claim_status,
    format_premium,
    get_acko_plans,
    get_cholams_plans,
    get_icici_plans,
    get_royal_sundaram_plans,
    get_godigit_plans,
    get_plan_category_label,
    get_unique_makes_models_variants,
    load_json_data,
    scan_all_car_data,
    save_normalized_data,
)


def format_signed_currency(value: Optional[float]) -> str:
    """Format currency values while preserving the sign for discounts."""
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    return f"{sign}{format_premium(abs(value))}"


def build_pricing_rows(pricing_breakdown: Dict[str, Any]) -> List[Dict[str, str]]:
    """Convert pricing breakdown dictionary into table rows."""
    if not isinstance(pricing_breakdown, dict):
        return []

    rows = []

    row_map = [
        ("Base Premium", "base_premium"),
        ("Own Damage Premium", "own_damage_premium"),
        ("Third Party Premium", "third_party_premium"),
        ("Add-ons", "addons_total"),
        ("Discounts", "discounts_total"),
        ("GST Amount", "gst_amount"),
        ("Net Premium", "net_premium"),
        ("Total Premium", "total_premium"),
    ]

    for label, key in row_map:
        value = pricing_breakdown.get(key)
        if value is None:
            continue
        rows.append({"Component": label, "Amount": format_signed_currency(value)})

    gst_rate = pricing_breakdown.get("gst_rate")
    gst_amount = pricing_breakdown.get("gst_amount")
    if gst_rate and gst_amount is None:
        rows.append({"Component": f"GST ({gst_rate})", "Amount": gst_rate})

    return rows


def render_idv_info(plan: Dict[str, Any]):
    """Render IDV information when present."""
    idv = plan.get("idv") or {}
    if not idv:
        return

    selected = idv.get("selected") or idv.get("current")
    idv_min = idv.get("min")
    idv_max = idv.get("max")
    recommended = idv.get("recommended")

    pieces = []
    if selected:
        pieces.append(f"Selected: {format_premium(selected)}")
    if idv_min and idv_max:
        pieces.append(f"Range: {format_premium(idv_min)} – {format_premium(idv_max)}")
    if recommended:
        pieces.append(f"Recommended: {format_premium(recommended)}")

    if pieces:
        st.markdown(f"**IDV Details:** {' | '.join(pieces)}")


def display_plan_card_compact(plan: Dict[str, Any]):
    """Display a compact plan card for homepage"""
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.markdown(f"**{plan.get('plan_name', 'Unknown Plan')}**")
            category = plan.get("category_display") or plan.get("category", "").upper()
            if category:
                st.caption(f"Type: {category}")
            status_label = format_claim_status(plan.get("claim_status", ""))
            if status_label:
                st.caption(f"Claim Status: {status_label}")

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
        header_col1, header_col2 = st.columns([3, 1])
        plan_type = plan.get("category_display") or plan.get("category", "").upper()
        plan_name = plan.get("plan_name", "Unknown Plan")
        badge = plan.get("badge", "")
        insurer_label = insurer or plan.get("insurer", "")

        with header_col1:
            if insurer_label:
                st.markdown(
                    f"<div style='display:inline-block;padding:0.15rem 0.55rem;border-radius:999px;background:#e0f2fe;color:#0369a1;font-size:0.75rem;font-weight:600;text-transform:uppercase;margin-bottom:0.35rem;'>{insurer_label}</div>",
                    unsafe_allow_html=True,
                )
            if plan_type:
                st.markdown(
                    f"<div style='font-size:1.15rem;font-weight:700;text-transform:uppercase;color:#0f172a;'>{plan_type}</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"<div style='font-size:1rem;color:#475569;margin-bottom:0.25rem;'>{plan_name}</div>",
                unsafe_allow_html=True,
            )
            meta_bits = []
            if insurer:
                meta_bits.append(insurer)
            plan_id = plan.get("plan_id", "")
            if plan_id:
                meta_bits.append(plan_id.upper())
            status_label = format_claim_status(plan.get("claim_status", ""))
            if status_label:
                meta_bits.append(f"Claim Status: {status_label}")
            if meta_bits:
                st.caption(" • ".join(meta_bits))

        with header_col2:
            premium_value = plan.get("premium_value", 0.0)
            premium_display = plan.get("premium_display", format_premium(premium_value))
            st.markdown(
                f"<div style='text-align:right;font-size:1.2rem;font-weight:700;color:#0f172a;'> {premium_display} </div>",
                unsafe_allow_html=True,
            )
            st.caption("Total Premium")
            if badge:
                st.markdown(
                    f"<div style='text-align:right;'><span style='background-color: #ff6b6b; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75em;'>{badge}</span></div>",
                    unsafe_allow_html=True,
                )

        render_idv_info(plan)

        # Description
        description = plan.get("description", "")
        if description:
            clean_desc = re.sub(r"<[^>]+>", "", description)
            if len(clean_desc) > 120:
                clean_desc = clean_desc[:120] + "..."
            st.markdown(f"*{clean_desc}*")

        pricing_rows = build_pricing_rows(plan.get("pricing_breakdown", {}))
        if pricing_rows:
            st.markdown("**Pricing Breakdown**")
            st.table(pd.DataFrame(pricing_rows))

        # Benefits/Addons
        benefits = plan.get("benefits", [])
        addons = plan.get("addons", [])

        if benefits:
            with st.expander("Benefits", expanded=False):
                for benefit in benefits:
                    st.markdown(f"• {benefit}")

        if addons:
            with st.expander("Add-ons & Covers", expanded=False):
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


def _format_addons_csv(addons: Any) -> str:
    """Flatten addons into a readable string for CSV export."""
    if not addons:
        return ""
    parts: List[str] = []
    for addon in addons:
        if isinstance(addon, dict):
            name = addon.get("name") or addon.get("display_name") or "Addon"
            price = addon.get("price") or addon.get("net_premium") or ""
            if price not in ("", None):
                parts.append(f"{name} ({price})")
            else:
                parts.append(str(name))
        else:
            parts.append(str(addon))
    return "; ".join(parts)


def plans_to_dataframe(
    all_plans_by_insurer: Dict[str, List[Dict[str, Any]]],
) -> pd.DataFrame:
    """Convert plans grouped by insurer into a flat DataFrame suitable for CSV."""
    rows: List[Dict[str, Any]] = []
    for insurer, plans in all_plans_by_insurer.items():
        for plan in plans:
            pricing = plan.get("pricing_breakdown", {}) or {}
            row = {
                "insurer": insurer,
                "plan_id": plan.get("plan_id", ""),
                "plan_name": plan.get("plan_name", ""),
                "plan_type": plan.get("category_display") or plan.get("category", ""),
                "premium_value": plan.get("premium_value", 0),
                # "premium_display": plan.get("premium_display", ""),
                "claim_status": plan.get("claim_status", ""),
                # "badge": plan.get("badge", ""),
                # "description": plan.get("description", ""),
                # "addons": _format_addons_csv(plan.get("addons")),
                # "benefits": "; ".join(map(str, plan.get("benefits", []))),
                # Pricing breakdown columns
                "base_premium": pricing.get("base_premium"),
                "own_damage_premium": pricing.get("own_damage_premium"),
                "third_party_premium": pricing.get("third_party_premium"),
                "addons_total": pricing.get("addons_total"),
                "discounts_total": pricing.get("discounts_total"),
                "gst_amount": pricing.get("gst_amount"),
                "gst_rate": pricing.get("gst_rate"),
                "net_premium": pricing.get("net_premium"),
                "total_premium": pricing.get("total_premium"),
            }
            rows.append(row)
    return pd.DataFrame(rows)


def homepage():
    """Homepage with car selection dropdowns"""
    st.title("Insurance Plans Overview")
    st.markdown(
        "Select your car to view all available insurance plans from different insurers"
    )

    # JSON view for car data map (for debugging or exploration)
    if "car_data_map" not in st.session_state:
        with st.spinner("Loading car data..."):
            st.session_state.car_data_map = scan_all_car_data()

    # JSON/dict preview: show as list of strings of the key triple, to avoid serialization error
    # car_data_map_preview = [
    #     f"{make} | {model} | {variant}:\n{files}"
    #     for (make, model, variant), files in st.session_state.car_data_map.items()
    # ]
    # st.write("Car data map keys and files:")
    # st.write(car_data_map_preview)

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
        selected_make = st.selectbox(
            "Car Make", makes, index=None, placeholder="Select Make"
        )

    selected_model = ""
    if selected_make:
        with col2:
            available_models = models_by_make.get(selected_make, [])
            selected_model = st.selectbox(
                "Car Model", available_models, index=None, placeholder="Select Model"
            )

    selected_variant = ""
    if selected_make and selected_model:
        with col3:
            available_variants = variants_by_make_model.get(selected_make, {}).get(
                selected_model, []
            )
            selected_variant = st.selectbox(
                "Car Variant",
                available_variants,
                index=None,
                placeholder="Select Variant",
            )

    # Display plans when all three are selected
    if selected_make and selected_model and selected_variant:
        key = (selected_make, selected_model, selected_variant)
        car_files = car_data_map.get(key, {})

        if (
            not car_files.get("acko")
            and not car_files.get("icici")
            and not car_files.get("cholams")
            and not car_files.get("royal_sundaram")
            and not car_files.get("godigit")
        ):
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

        # Load Acko plans (all available claim statuses)
        acko_plans: List[Dict[str, Any]] = []
        if car_files.get("acko"):
            for acko_file_info in car_files["acko"]:
                try:
                    acko_data = load_json_data(acko_file_info["file"])
                    acko_plans.extend(
                        get_acko_plans(
                            acko_data, acko_file_info.get("claim_status", "")
                        )
                    )
                except Exception as e:
                    st.error(
                        f"Error loading Acko data from {acko_file_info['file']}: {e}"
                    )
            if acko_plans:
                all_plans_by_insurer["Acko"] = acko_plans

        # Load ICICI plans (all available claim statuses)
        icici_plans: List[Dict[str, Any]] = []
        if car_files.get("icici"):
            for icici_file_info in car_files["icici"]:
                try:
                    icici_data = load_json_data(icici_file_info["file"])
                    icici_plans.extend(
                        get_icici_plans(
                            icici_data, icici_file_info.get("claim_status", "")
                        )
                    )
                except Exception as e:
                    st.error(
                        f"Error loading ICICI data from {icici_file_info['file']}: {e}"
                    )
            if icici_plans:
                all_plans_by_insurer["ICICI"] = icici_plans

        # Load Cholams plans (all available claim statuses)
        cholams_plans: List[Dict[str, Any]] = []
        if car_files.get("cholams"):
            for cholams_file_info in car_files["cholams"]:
                try:
                    cholams_data = load_json_data(cholams_file_info["file"])
                    cholams_plans.extend(
                        get_cholams_plans(
                            cholams_data, cholams_file_info.get("claim_status", "")
                        )
                    )
                except Exception as e:
                    st.error(
                        f"Error loading Cholams data from {cholams_file_info['file']}: {e}"
                    )
            if cholams_plans:
                all_plans_by_insurer["Cholams"] = cholams_plans

        # Load Royal Sundaram plans (all available claim statuses)
        royal_sundaram_plans: List[Dict[str, Any]] = []
        if car_files.get("royal_sundaram"):
            for royal_file_info in car_files["royal_sundaram"]:
                try:
                    royal_data = load_json_data(royal_file_info["file"])
                    royal_sundaram_plans.extend(
                        get_royal_sundaram_plans(
                            royal_data, royal_file_info.get("claim_status", "")
                        )
                    )
                except Exception as e:
                    st.error(
                        f"Error loading Royal Sundaram data from {royal_file_info['file']}: {e}"
                    )
            if royal_sundaram_plans:
                all_plans_by_insurer["Royal Sundaram"] = royal_sundaram_plans

        # Load Go Digit plans (all available claim statuses)
        godigit_plans: List[Dict[str, Any]] = []
        if car_files.get("godigit"):
            for godigit_file_info in car_files["godigit"]:
                try:
                    godigit_data = load_json_data(godigit_file_info["file"])
                    godigit_plans.extend(
                        get_godigit_plans(
                            godigit_data, godigit_file_info.get("claim_status", "")
                        )
                    )
                except Exception as e:
                    st.error(
                        f"Error loading Go Digit data from {godigit_file_info['file']}: {e}"
                    )
            if godigit_plans:
                all_plans_by_insurer["Go Digit"] = godigit_plans

        # Build and display summary statistics
        summary_stats = build_summary_stats(all_plans_by_insurer)
        display_summary_table(summary_stats)

        st.markdown("---")

        # Display plans in tabs grouped by insurer
        if all_plans_by_insurer:
            tab_names = [
                f"{insurer} ({len(plans)} plans)"
                for insurer, plans in sorted(all_plans_by_insurer.items())
            ]
            tabs = st.tabs(tab_names)

            sorted_insurers = sorted(all_plans_by_insurer.keys())
            for idx, insurer_name in enumerate(sorted_insurers):
                with tabs[idx]:
                    plans = all_plans_by_insurer[insurer_name]
                    if plans:
                        for plan in plans:
                            display_plan_card(plan, insurer_name)
                            st.divider()
                    else:
                        st.info(f"No plans available from {insurer_name}")

        # Store selected car info in session state for comparison and insights pages
        st.session_state.selected_car_key = key
        st.session_state.selected_car_files = car_files
        st.session_state.all_plans_by_insurer = all_plans_by_insurer

        # CSV exports
        plans_df = plans_to_dataframe(all_plans_by_insurer)
        csv_data = plans_df.to_csv(index=False).encode("utf-8")

        # Use Streamlit columns for download buttons
        cols = st.columns(2)
        with cols[0]:
            st.download_button(
                "⬇️ Download Plans CSV",
                data=csv_data,
                file_name=f"plans_{selected_make}_{selected_model}_{selected_variant}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # Grouped CSV by insurer and plan type
        if not plans_df.empty:
            grouped_df = (
                plans_df.groupby(["insurer", "plan_type"], dropna=False)
                .agg(
                    plan_count=("plan_id", "count"),
                    min_premium=("premium_value", "min"),
                    max_premium=("premium_value", "max"),
                    avg_premium=("premium_value", "mean"),
                )
                .reset_index()
            )
            grouped_csv = grouped_df.to_csv(index=False).encode("utf-8")
            with cols[1]:
                st.download_button(
                    "⬇️ Download Grouped CSV (Insurer x Plan Type)",
                    data=grouped_csv,
                    file_name=f"plans_sum_{selected_make}_{selected_model}_{selected_variant}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        # # Save normalized data button
        # if st.button("💾 Save Normalized Data", use_container_width=True):
        #     try:
        #         saved_path = save_normalized_data(key, all_plans_by_insurer)
        #         st.success(f"✅ Data saved to: `{saved_path}`")
        #     except Exception as e:
        #         st.error(f"Error saving data: {e}")


def build_summary_stats(
    all_plans_by_insurer: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Build summary statistics from all plans grouped by insurer."""
    total_plans = sum(len(plans) for plans in all_plans_by_insurer.values())
    insurers = sorted(all_plans_by_insurer.keys())
    insurer_counts = {
        insurer: len(plans) for insurer, plans in all_plans_by_insurer.items()
    }

    # Count plans by category
    plan_type_counts = {"tp": 0, "comp": 0, "zd": 0, "od": 0}
    for plans in all_plans_by_insurer.values():
        for plan in plans:
            category = plan.get("category", "").lower()
            if category in plan_type_counts:
                plan_type_counts[category] += 1

    return {
        "total_plans": total_plans,
        "insurers": insurers,
        "insurer_counts": insurer_counts,
        "plan_type_counts": plan_type_counts,
    }


def display_summary_table(summary_stats: Dict[str, Any]):
    """Display a summary table with plan statistics."""
    st.markdown("### 📊 Summary")

    # Create summary data for table
    summary_data = {
        "Metric": [
            "Total Plans",
            "Acko",
            "ICICI",
            "Cholams",
            "Royal Sundaram",
            "Go Digit",
            "Third Party (TP)",
            "Comprehensive (COMP)",
            "Zero Depreciation (ZD)",
            "Own Damage (OD)",
        ],
        "Count": [
            summary_stats["total_plans"],
            summary_stats["insurer_counts"].get("Acko", 0),
            summary_stats["insurer_counts"].get("ICICI", 0),
            summary_stats["insurer_counts"].get("Cholams", 0),
            summary_stats["insurer_counts"].get("Royal Sundaram", 0),
            summary_stats["insurer_counts"].get("Go Digit", 0),
            summary_stats["plan_type_counts"].get("tp", 0),
            summary_stats["plan_type_counts"].get("comp", 0),
            summary_stats["plan_type_counts"].get("zd", 0),
            summary_stats["plan_type_counts"].get("od", 0),
        ],
    }

    df_summary = pd.DataFrame(summary_data)

    # Display in columns for better layout
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Insurer Breakdown**")
        insurer_df = df_summary.iloc[0:6]
        st.dataframe(insurer_df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**Plan Type Breakdown**")
        plan_type_df = df_summary.iloc[6:10]
        st.dataframe(plan_type_df, use_container_width=True, hide_index=True)


def _collect_all_plans_for_current_car() -> List[Dict[str, Any]]:
    """Helper to collect all plans with insurer name for the car in session."""
    if (
        "selected_car_key" not in st.session_state
        or "all_plans_by_insurer" not in st.session_state
    ):
        return []

    all_plans_by_insurer = st.session_state.all_plans_by_insurer
    all_plans: List[Dict[str, Any]] = []
    for insurer, plans in all_plans_by_insurer.items():
        for plan in plans:
            plan_copy = plan.copy()
            plan_copy["insurer"] = insurer
            all_plans.append(plan_copy)
    return all_plans


def apply_sidebar_filters(
    all_plans: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Apply sidebar filters (plan type, insurer, claim status, price range).

    Returns filtered plans and metadata (e.g., price_range) for downstream use.
    """
    if not all_plans:
        return [], {"price_range": None}

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

    # Filter plans by type
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

    # Claim status filter
    claim_status_option = st.sidebar.radio(
        "Claim Status", options=["Both", "Not Claimed", "Claimed"], index=0
    )
    if claim_status_option != "Both":
        target_status = (
            "not_claimed" if claim_status_option == "Not Claimed" else "claimed"
        )
        filtered_plans = [
            p
            for p in filtered_plans
            if normalize_claim_status(p.get("claim_status")) == target_status
        ]

    # Price range filter
    price_range = None
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

    return filtered_plans, {"price_range": price_range}


def main():
    st.set_page_config(
        page_title="Insurance Plans Comparison",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Homepage is the default page
    homepage()


if __name__ == "__main__":
    main()
