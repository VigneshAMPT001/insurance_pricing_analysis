from typing import Any, Dict, List

import streamlit as st
import pandas as pd
import altair as alt

from app_v2_utils import format_premium, normalize_claim_status
from overview import apply_sidebar_filters, _collect_all_plans_for_current_car


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
        return

    selected_car_key = st.session_state.selected_car_key
    make, model, variant = selected_car_key
    st.markdown(f"**Insights for:** {make} {model} {variant}")

    all_plans = _collect_all_plans_for_current_car()
    if not all_plans:
        st.warning("No plans available to generate insights.")
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
                    color=alt.Color(
                        "Plan Type:N", legend=alt.Legend(title="Plan Type")
                    ),
                    tooltip=[
                        alt.Tooltip("Plan Type:N"),
                        alt.Tooltip("count():Q", title="Number of Plans"),
                    ],
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
                "Average Premium": format_premium(sum(ips) / len(ips) if ips else 0),
                "Costliest Premium": format_premium(max(ips) if ips else 0),
                "Avg Add-ons per Plan": (
                    round(sum(addon_counts) / len(addon_counts), 1)
                    if addon_counts
                    else 0.0
                ),
                # "% Plans with Claims History": f"{claimed_share:.1f}%",
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


# Streamlit pages automatically call the code when the page is selected
insights_page()
