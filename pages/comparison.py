from typing import Any, Dict, List

import streamlit as st
import pandas as pd

from app_v2_utils import format_claim_status, format_premium, save_normalized_data
from overview import apply_sidebar_filters, display_plan_card, plans_to_dataframe


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
        return

    # Apply shared sidebar filters
    filtered_plans, filter_meta = apply_sidebar_filters(all_plans)
    price_range = filter_meta.get("price_range")

    # Reorganize filtered plans by insurer for saving
    filtered_plans_by_insurer = {}
    for plan in filtered_plans:
        insurer = plan.get("insurer", "Unknown")
        if insurer not in filtered_plans_by_insurer:
            filtered_plans_by_insurer[insurer] = []
        filtered_plans_by_insurer[insurer].append(plan)

    # # Save button for filtered data
    # if st.button("💾 Save Filtered Data", use_container_width=False):
    #     try:
    #         saved_path = save_normalized_data(
    #             selected_car_key,
    #             filtered_plans_by_insurer,
    #             output_dir="normalized_data_filtered",
    #         )
    #         st.success(f"✅ Filtered data saved to: `{saved_path}`")
    #     except Exception as e:
    #         st.error(f"Error saving filtered data: {e}")

    # Download CSV for filtered data with flattened pricing/addons
    filtered_df = plans_to_dataframe(filtered_plans_by_insurer)
    if not filtered_df.empty:
        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Filtered CSV",
            data=csv_data,
            file_name=f"filtered_{make}_{model}_{variant}_plans.csv",
            mime="text/csv",
            use_container_width=False,
        )

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


# Streamlit pages automatically call the code when the page is selected
comparison_page()
