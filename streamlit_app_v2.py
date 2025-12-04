import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd
import altair as alt

from app_v2_utils import (
    format_claim_status,
    normalize_claim_status,
    format_premium,
    get_acko_plans,
    get_cholams_plans,
    get_icici_plans,
    get_royal_sundaram_plans,
    get_plan_category_label,
    get_unique_makes_models_variants,
    load_acko_data,
    load_cholams_data,
    load_icici_data,
    load_royal_sundaram_data,
    scan_all_car_data,
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

        # Load Acko plans
        acko_plans = []
        if car_files.get("acko"):
            # Use not_claimed by default, or first available
            acko_file_info = next(
                (
                    f
                    for f in car_files["acko"]
                    if f.get("claim_status") == "not_claimed"
                ),
                car_files["acko"][0],
            )
            try:
                acko_data = load_acko_data(acko_file_info["file"])
                acko_plans = get_acko_plans(
                    acko_data, acko_file_info.get("claim_status", "")
                )
                all_plans_by_insurer["Acko"] = acko_plans
            except Exception as e:
                st.error(f"Error loading Acko data: {e}")

        # Load ICICI plans
        icici_plans = []
        if car_files.get("icici"):
            icici_file_info = car_files["icici"][0]
            try:
                icici_data = load_icici_data(icici_file_info["file"])
                icici_plans = get_icici_plans(
                    icici_data, icici_file_info.get("claim_status", "")
                )
                all_plans_by_insurer["ICICI"] = icici_plans
            except Exception as e:
                st.error(f"Error loading ICICI data: {e}")

        # Load Cholams plans
        cholams_plans = []
        if car_files.get("cholams"):
            cholams_file_info = car_files["cholams"][0]
            try:
                cholams_data = load_cholams_data(cholams_file_info["file"])
                cholams_plans = get_cholams_plans(
                    cholams_data, cholams_file_info.get("claim_status", "")
                )
                all_plans_by_insurer["Cholams"] = cholams_plans
            except Exception as e:
                st.error(f"Error loading Cholams data: {e}")

        royal_sundaram_plans = []
        if car_files.get("royal_sundaram"):
            royal_file_info = next(
                (
                    f
                    for f in car_files["royal_sundaram"]
                    if f.get("claim_status") == "not_claimed"
                ),
                car_files["royal_sundaram"][0],
            )
            try:
                royal_data = load_royal_sundaram_data(royal_file_info["file"])
                royal_sundaram_plans = get_royal_sundaram_plans(
                    royal_data, royal_file_info.get("claim_status", "")
                )
                all_plans_by_insurer["Royal Sundaram"] = royal_sundaram_plans
            except Exception as e:
                st.error(f"Error loading Royal Sundaram data: {e}")

        # Display plans in accordions grouped by insurer
        for insurer_name, plans in all_plans_by_insurer.items():
            with st.expander(
                f"{insurer_name} Insurance ({len(plans)} plans)", expanded=True
            ):
                if plans:
                    for plan in plans:
                        display_plan_card(plan, insurer_name)
                        st.divider()
                else:
                    st.info(f"No plans available from {insurer_name}")

        # Store selected car info in session state for comparison page
        st.session_state.selected_car_key = key
        st.session_state.selected_car_files = car_files
        st.session_state.all_plans_by_insurer = all_plans_by_insurer

        # Button to go to comparison page
        if st.button("Compare Plans", type="primary", use_container_width=True):
            st.session_state.page = "comparison"
            st.rerun()


def comparison_page():
    """Plan comparison page"""
    st.title("Plan Comparison")
    st.markdown(
        "<p style='color:#475569'>Fine-tune filters in the sidebar to narrow down plans and compare premiums at a glance.</p>",
        unsafe_allow_html=True,
    )

    if (
        "selected_car_key" not in st.session_state
        or "all_plans_by_insurer" not in st.session_state
    ):
        st.warning("Please select a car from the homepage first.")
        if st.button("Back to Homepage"):
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
        if st.button("Back to Homepage"):
            st.session_state.page = "homepage"
            st.rerun()
        return

    # Apply shared sidebar filters
    filtered_plans, filter_meta = apply_sidebar_filters(all_plans)
    price_range = filter_meta.get("price_range")

    # Display comparison
    st.markdown("---")

    if not filtered_plans:
        st.info("No plans match the selected filters.")
        return

    # Summary metrics
    st.subheader("At a Glance")
    summary_cols = st.columns(3)
    summary_cols[0].metric("Plans Available", len(filtered_plans))
    if price_range:
        summary_cols[1].metric("Price Floor", format_premium(price_range[0]))
        summary_cols[2].metric("Price Ceiling", format_premium(price_range[1]))
    else:
        premiums = [p.get("premium_value", 0) for p in filtered_plans]
        summary_cols[1].metric("Lowest Premium", format_premium(min(premiums)))
        summary_cols[2].metric("Highest Premium", format_premium(max(premiums)))

    insurer_counts = {}
    for plan in filtered_plans:
        insurer_counts.setdefault(plan.get("insurer", "Unknown"), []).append(plan)

    st.markdown(
        "<div style='display:flex;gap:1rem;flex-wrap:wrap;'>"
        + "".join(
            f"<div style='flex:1 1 220px;border:1px solid #e2e8f0;border-radius:0.75rem;padding:0.75rem;background:#f8fafc;'>"
            f"<div style='font-size:0.85rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;'>{insurer}</div>"
            f"<div style='font-size:1.4rem;font-weight:700;color:#0f172a;margin:0.2rem 0;'>{len(plans)} plans</div>"
            f"<div style='font-size:0.8rem;color:#64748b;'>₹{int(min(p.get('premium_value', 0) for p in plans)):,} – ₹{int(max(p.get('premium_value', 0) for p in plans)):,}</div>"
            "</div>"
            for insurer, plans in insurer_counts.items()
        )
        + "</div>",
        unsafe_allow_html=True,
    )

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
                "Claim Status": format_claim_status(plan.get("claim_status", "")),
                # "Badge": plan.get("badge", ""),
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

    # Back button
    if st.button("Back to Homepage"):
        st.session_state.page = "homepage"
        st.rerun()


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


def insights_page():
    """Insights page showing higher-level analytics for the filtered plans."""
    st.title("Plan Insights")
    st.markdown(
        "<p style='color:#475569'>Use the same sidebar filters to uncover where the real value lies across insurers, plan types, and add‑ons.</p>",
        unsafe_allow_html=True,
    )

    if (
        "selected_car_key" not in st.session_state
        or "all_plans_by_insurer" not in st.session_state
    ):
        st.warning("Please select a car from the homepage first.")
        if st.button("Back to Homepage"):
            st.session_state.page = "homepage"
            st.rerun()
        return

    selected_car_key = st.session_state.selected_car_key
    make, model, variant = selected_car_key
    st.markdown(f"**Insights for:** {make} {model} {variant}")

    all_plans = _collect_all_plans_for_current_car()
    if not all_plans:
        st.warning("No plans available to generate insights.")
        if st.button("Back to Homepage"):
            st.session_state.page = "homepage"
            st.rerun()
        return

    # Apply same sidebar filters used on comparison page
    filtered_plans, filter_meta = apply_sidebar_filters(all_plans)
    price_range = filter_meta.get("price_range")

    if not filtered_plans:
        st.info("No plans match the selected filters for insights.")
        return

    # ---- Key numerical insights ----
    premiums = [p.get("premium_value", 0) for p in filtered_plans]
    min_premium = min(premiums)
    max_premium = max(premiums)
    avg_premium = sum(premiums) / len(premiums) if premiums else 0
    premium_saving_pct = (
        (max_premium - min_premium) / max_premium * 100 if max_premium else 0
    )

    unique_insurers = sorted(set(p.get("insurer", "") for p in filtered_plans))

    def _addons_count(plan: Dict[str, Any]) -> int:
        addons = plan.get("addons") or []
        if isinstance(addons, list):
            return len(addons)
        return 0

    addons_counts = [_addons_count(p) for p in filtered_plans]
    avg_addons = sum(addons_counts) / len(addons_counts) if addons_counts else 0

    # Simple heuristic: how often do strong protection add‑ons appear?
    protection_keywords = ["zero dep", "zero depreciation", "engine", "ncb", "rsa"]

    def _has_protection_addon(plan: Dict[str, Any]) -> bool:
        addons = plan.get("addons") or []
        addon_names: List[str] = []
        for addon in addons:
            if isinstance(addon, dict):
                name = addon.get("name") or addon.get("display_name") or ""
                addon_names.append(str(name).lower())
            else:
                addon_names.append(str(addon).lower())
        return any(
            any(keyword in name for keyword in protection_keywords)
            for name in addon_names
        )

    protection_plans = [p for p in filtered_plans if _has_protection_addon(p)]
    protection_share = (
        len(protection_plans) / len(filtered_plans) * 100 if filtered_plans else 0
    )

    st.subheader("Key Insights at a Glance")
    kpi_cols = st.columns(4)
    kpi_cols[0].metric(
        "Cheapest vs Costliest",
        f"{format_premium(min_premium)} – {format_premium(max_premium)}",
        f"{premium_saving_pct:.1f}% savings potential",
    )
    kpi_cols[1].metric("Average Premium (Filtered)", format_premium(avg_premium))
    kpi_cols[2].metric("Insurers in Play", len(unique_insurers))
    kpi_cols[3].metric(
        "Avg Add-ons per Plan",
        f"{avg_addons:.1f}",
        f"{protection_share:.1f}% include strong protection add-ons",
    )

    # ---- Charts section ----
    st.markdown("---")
    st.subheader("Premium & Mix Overview")

    # Bar: average premium by insurer
    insurer_stats = []
    for insurer in unique_insurers:
        insurer_plans = [p for p in filtered_plans if p.get("insurer") == insurer]
        if not insurer_plans:
            continue
        ips = [p.get("premium_value", 0) for p in insurer_plans]
        insurer_stats.append(
            {
                "Insurer": insurer,
                "Average Premium": sum(ips) / len(ips) if ips else 0,
                "Cheapest Premium": min(ips) if ips else 0,
                "Costliest Premium": max(ips) if ips else 0,
                "Number of Plans": len(insurer_plans),
            }
        )

    if insurer_stats:
        df_insurer = pd.DataFrame(insurer_stats)
        left_col, right_col = st.columns(2)

        with left_col:
            st.caption("Average premium by insurer (after filters)")
            bar_chart = (
                alt.Chart(df_insurer)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("Insurer:N", sort="-y", title="Insurer"),
                    y=alt.Y("Average Premium:Q", title="Average Premium (₹)"),
                    color=alt.Color("Insurer:N", legend=None),
                    tooltip=[
                        "Insurer",
                        alt.Tooltip("Average Premium:Q", format=",.0f"),
                        alt.Tooltip("Cheapest Premium:Q", format=",.0f"),
                        alt.Tooltip("Costliest Premium:Q", format=",.0f"),
                        "Number of Plans",
                    ],
                )
                .properties(height=320)
            )
            st.altair_chart(bar_chart, use_container_width=True)

        # Donut: plan mix by type (or fallback to insurer if type missing)
        plan_type_rows = []
        for p in filtered_plans:
            p_type = p.get("category_display") or p.get("category") or "Other"
            plan_type_rows.append({"Plan Type": str(p_type)})

        df_types = pd.DataFrame(plan_type_rows)
        with right_col:
            st.caption("Mix of plan types in your filtered view")
            type_chart = (
                alt.Chart(df_types)
                .mark_arc(innerRadius=60)
                .encode(
                    theta=alt.Theta("count():Q", stack=True),
                    color=alt.Color("Plan Type:N", legend=alt.Legend(title="Plan Type")),
                    tooltip=[alt.Tooltip("Plan Type:N"), alt.Tooltip("count():Q", title="Number of Plans")],
                )
                .properties(height=320)
            )
            st.altair_chart(type_chart, use_container_width=True)

    # ---- Table: richer insurer-level view ----
    st.markdown("---")
    st.subheader("Insurer Value Summary Table")

    table_rows = []
    for insurer in unique_insurers:
        insurer_plans = [p for p in filtered_plans if p.get("insurer") == insurer]
        if not insurer_plans:
            continue

        ips = [p.get("premium_value", 0) for p in insurer_plans]
        addon_counts = [_addons_count(p) for p in insurer_plans]
        claimed_share = (
            sum(
                1
                for p in insurer_plans
                if normalize_claim_status(p.get("claim_status")) == "claimed"
            )
            / len(insurer_plans)
            * 100
            if insurer_plans
            else 0
        )

        table_rows.append(
            {
                "Insurer": insurer,
                "Plans": len(insurer_plans),
                "Cheapest Premium": format_premium(min(ips) if ips else 0),
                "Average Premium": format_premium(
                    sum(ips) / len(ips) if ips else 0
                ),
                "Costliest Premium": format_premium(max(ips) if ips else 0),
                "Avg Add-ons per Plan": round(
                    sum(addon_counts) / len(addon_counts), 1
                )
                if addon_counts
                else 0.0,
                "% Plans with Claims History": f"{claimed_share:.1f}%",
            }
        )

    if table_rows:
        df_table = pd.DataFrame(table_rows)
        st.dataframe(df_table, use_container_width=True, hide_index=True)

    # Optional contextual note if user narrowed with price slider
    if price_range:
        st.caption(
            f"Insights are based on plans priced between {format_premium(price_range[0])} and {format_premium(price_range[1])}."
        )


def main():
    st.set_page_config(
        page_title="Insurance Plans Comparison",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize page state
    if "page" not in st.session_state:
        st.session_state.page = "homepage"

    # Sidebar navigation
    page_labels = {
        "homepage": "Overview",
        "comparison": "Comparison",
        "insights": "Insights",
    }
    current_label = page_labels.get(st.session_state.page, "Overview")
    label_list = list(page_labels.values())
    current_index = label_list.index(current_label)
    selected_label = st.sidebar.radio("Navigation", options=label_list, index=current_index)

    # Sync selected label back to internal page key
    for key, label in page_labels.items():
        if label == selected_label:
            st.session_state.page = key
            break

    # Navigation
    if st.session_state.page == "homepage":
        homepage()
    elif st.session_state.page == "comparison":
        comparison_page()
    elif st.session_state.page == "insights":
        insights_page()


if __name__ == "__main__":
    main()
