import json
import os
from typing import Dict, Any, List, Tuple

import pandas as pd
import streamlit as st


NORMALIZED_FILE = "normalized_plans.json"


@st.cache_data(show_spinner=False)
def load_normalized_data(path: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_rows_for_table(
    company: str,
    model: str,
    plans: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for plan_name, plan_payload in plans.items():
        price = plan_payload.get("price", {})
        rows.append(
            {
                "Company": company,
                "Model": model,
                "Plan": plan_name,
                "Total Premium": price.get("total_premium"),
                "Net Premium": price.get("net_premium"),
                "Tax Amount": price.get("tax_amount"),
                "Currency": price.get("currency"),
                # "Source File": plan_payload.get("source_file"),
            }
        )
    return rows


def main() -> None:
    st.set_page_config(page_title="Insurance Plans Browser", layout="wide")
    st.title("Insurance Plans Browser")

    if not os.path.exists(NORMALIZED_FILE):
        st.error(f"Normalized data file not found: {NORMALIZED_FILE}")
        st.stop()

    data = load_normalized_data(NORMALIZED_FILE)

    # Sidebar: mode selector
    st.sidebar.header("Filters")
    mode = st.sidebar.radio(
        "Mode",
        options=["Browse", "Compare across companies"],
        index=0,
    )

    company_names = sorted(list(data.keys()))
    if not company_names:
        st.warning("No companies found in data")
        st.stop()

    if mode == "Browse":
        selected_company = st.sidebar.selectbox("Company", options=company_names)
        models_for_company = data.get(selected_company, {})
        model_names = sorted(list(models_for_company.keys()))
        if not model_names:
            st.warning("No car models found for selected company")
            st.stop()

        selected_model = st.sidebar.selectbox("Car Model", options=model_names)
        plans_for_model = models_for_company.get(selected_model, {})
        plan_names = sorted(list(plans_for_model.keys()))

        selected_plans = st.sidebar.multiselect(
            "Plans", options=plan_names, default=plan_names
        )

        # Build table
        filtered_plans: Dict[str, Dict[str, Any]] = {
            k: v for k, v in plans_for_model.items() if k in selected_plans
        }
        table_rows = build_rows_for_table(
            selected_company, selected_model, filtered_plans
        )
        df = pd.DataFrame(table_rows)

        st.subheader("Plans and Pricing")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

    else:
        # Compare across companies
        company_multi = st.sidebar.multiselect(
            "Companies", options=company_names, default=company_names
        )
        plan_query = st.sidebar.text_input(
            "Plan name contains",
            value="",
            placeholder="e.g., comprehensive, bumper, 360",
        ).strip()
        model_query = st.sidebar.text_input(
            "Model contains (optional)",
            value="",
            placeholder="e.g., SWIFT, CURVV, Nexon",
        ).strip()

        rows: List[Dict[str, Any]] = []
        plan_q = plan_query.lower()
        model_q = model_query.lower()
        for comp in company_multi:
            for model, plans in data.get(comp, {}).items():
                if model_q and model_q not in model.lower():
                    continue
                for plan_name, payload in plans.items():
                    if plan_q and plan_q not in plan_name.lower():
                        continue
                    price = payload.get("price", {})
                    rows.append(
                        {
                            "Company": comp,
                            "Model": model,
                            "Plan": plan_name,
                            "Total Premium": price.get("total_premium"),
                            "Net Premium": price.get("net_premium"),
                            "Tax Amount": price.get("tax_amount"),
                            "Currency": price.get("currency"),
                            # "Source File": payload.get("source_file"),
                        }
                    )

        df = pd.DataFrame(rows)

        st.subheader("Cross-company comparison")
        if df.empty:
            st.info("No plans matched your filters.")
        else:
            sort_by = st.selectbox(
                "Sort by",
                options=["Total Premium", "Net Premium", "Company", "Model", "Plan"],
                index=0,
            )
            ascending = st.checkbox("Ascending", value=True)
            if sort_by in df.columns:
                df = df.sort_values(by=sort_by, ascending=ascending, na_position="last")

            st.dataframe(df, use_container_width=True, hide_index=True)

            # Optional: quick price summary by company
            st.markdown("**Summary by company (min / max total premium)**")
            summary = (
                df.groupby("Company")["Total Premium"].agg(["min", "max"]).reset_index()
            )
            st.dataframe(summary, use_container_width=True, hide_index=True)

    # Summary stats
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Plans", len(df))
        with col2:
            st.metric(
                "Min Total Premium",
                (
                    f"{df['Total Premium'].min():,.2f}"
                    if pd.notnull(df["Total Premium"]).any()
                    else "-"
                ),
            )
        with col3:
            st.metric(
                "Max Total Premium",
                (
                    f"{df['Total Premium'].max():,.2f}"
                    if pd.notnull(df["Total Premium"]).any()
                    else "-"
                ),
            )

    st.divider()
    st.subheader("Raw JSON Preview")
    if mode == "Browse":
        with st.expander("Show company JSON", expanded=False):
            st.json(data.get(selected_company, {}))
        with st.expander("Show model JSON", expanded=False):
            st.json(plans_for_model)

    # Download CSV
    if not df.empty:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        if mode == "Browse":
            file_name = f"{selected_company}_{selected_model}_plans.csv"
        else:
            file_name = "insurance_plans_comparison.csv"
        st.download_button(
            label="Download as CSV",
            data=csv_bytes,
            file_name=file_name,
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
