
import streamlit as st
import pandas as pd

from contextiq.answering.generator import generate_answer
from contextiq.config import Settings
from contextiq.engine import ContextEngine


st.set_page_config(
    page_title="ContextIQ",
    page_icon="🔎",
    layout="wide",
)

st.title("ContextIQ")
st.subheader("Governed, context-aware business intelligence")
st.caption(
    "Ask business questions and retrieve evidence through role-based access control."
)

ROLES = [
    "support_analyst",
    "quality_engineer",
    "finance_manager",
    "executive",
]

ROLE_DESCRIPTIONS = {
    "support_analyst": "Customer complaints and support information",
    "quality_engineer": "Product quality and incident information",
    "finance_manager": "Financial and business information",
    "executive": "Executive-level business information",
}


@st.cache_resource
def get_engine():
    return ContextEngine(Settings())


engine = get_engine()


def run_governed_query(query, selected_role):
    result = engine.sql(query, selected_role)

    return pd.DataFrame(
        result.rows,
        columns=result.columns,
    )


with st.sidebar:
    st.header("Access settings")

    role = st.selectbox(
        "Select your role",
        ROLES,
    )

    st.caption(ROLE_DESCRIPTIONS[role])

    st.divider()

    st.info(
        "ContextIQ applies access policies before returning evidence."
    )


st.markdown("### Ask a business question")

question = st.text_area(
    "Enter your question",
    value=(
        "Why did customer complaints increase last month, "
        "which products were affected, and what should we do?"
    ),
    height=110,
)


if st.button("Retrieve context", type="primary"):
    if not question.strip():
        st.warning("Please enter a question.")

    else:
        try:
            with st.spinner("Retrieving governed context..."):
                bundle = engine.ask(
                    question=question,
                    role=role,
                    plain=False,
                    top_k=8,
                )

            st.success("Context retrieval completed.")

            answer = generate_answer(bundle)

            # BUSINESS ANALYTICS
            st.markdown("### Business analytics")

            # 1. Monthly complaint trend
            st.markdown("#### Monthly complaint trend")

            monthly_query = """
                SELECT
                    month,
                    SUM(complaints) AS complaints,
                    ROUND(
                        100.0 * SUM(complaints) /
                        NULLIF(SUM(orders), 0),
                        2
                    ) AS complaint_rate_pct
                FROM complaints_monthly
                GROUP BY month
                ORDER BY month
            """

            monthly_df = run_governed_query(monthly_query, role)

            if not monthly_df.empty:
                st.line_chart(
                    monthly_df.set_index("month")["complaint_rate_pct"]
                )
                st.dataframe(monthly_df, hide_index=True)
            else:
                st.info("No monthly complaint data is available.")

            # 2. Product-wise complaint rates
            st.markdown("#### Product-wise complaint rates")

            product_query = """
                SELECT
                    p.product_id,
                    p.name AS product_name,
                    SUM(cm.orders) AS orders,
                    SUM(cm.complaints) AS complaints,
                    ROUND(
                        100.0 * SUM(cm.complaints) /
                        NULLIF(SUM(cm.orders), 0),
                        2
                    ) AS complaint_rate_pct
                FROM complaints_monthly cm
                JOIN products p
                    ON cm.product_id = p.product_id
                WHERE cm.month = '2026-10'
                GROUP BY p.product_id, p.name
                ORDER BY complaint_rate_pct DESC
            """

            try:
                product_df = run_governed_query(product_query, role)

                if not product_df.empty:
                    st.bar_chart(
                        product_df.set_index("product_name")[
                            "complaint_rate_pct"
                        ]
                    )
                    st.dataframe(product_df, hide_index=True)
                else:
                    st.info("No product complaint data is available.")

            except Exception as error:
                st.warning(
                    f"Product analytics are not available for this role: {error}"
                )

            # 3. Revenue performance
            if role in ["finance_manager", "executive"]:
                st.markdown("#### Monthly revenue performance")

                revenue_query = """
                    SELECT
                        month,
                        SUM(gross_revenue) AS gross_revenue,
                        SUM(refunds) AS refunds,
                        SUM(net_revenue) AS net_revenue
                    FROM revenue_monthly
                    GROUP BY month
                    ORDER BY month
                """

                try:
                    revenue_df = run_governed_query(revenue_query, role)

                    if not revenue_df.empty:
                        st.line_chart(
                            revenue_df.set_index("month")[
                                ["gross_revenue", "net_revenue"]
                            ]
                        )
                        st.dataframe(revenue_df, hide_index=True)
                    else:
                        st.info("No revenue data is available.")

                except Exception as error:
                    st.warning(
                        f"Revenue analytics are not available: {error}"
                    )

            else:
                st.info(
                    "Revenue analytics are restricted to finance_manager "
                    "and executive roles."
                )

            st.divider()

            # GENERATED ANSWER REPORT
            st.markdown("### Generated answer report")

            st.write(answer["summary"])

            st.markdown("#### Key observations")

            if answer["key_observations"]:
                for observation in answer["key_observations"]:
                    st.write(
                        f"{observation['citation']} "
                        f"{observation['text']}"
                    )
            else:
                st.info("No key observations are available.")

            st.markdown("#### Affected products")

            if answer["affected_products"]:
                for product in answer["affected_products"]:
                    citations = ", ".join(product["citations"])
                    st.write(
                        f"**{product['product']}** "
                        f"(Evidence: {citations})"
                    )
            else:
                st.info(
                    "No affected products were confirmed by the retrieved evidence."
                )

            if answer["findings"]:
                for finding in answer["findings"]:
                    st.markdown(
                        f"**{finding['citation']} {finding['title']}**"
                    )
                    st.write(finding["text"])
                    st.caption(
                        f"Source: {finding['source_id']} | "
                        f"Period: {finding['period']}"
                    )
            else:
                st.info("No permitted evidence is available.")

            with st.expander("Report limitations"):
                for limitation in answer["limitations"]:
                    st.write("- ", limitation)

            # RETRIEVAL SUMMARY
            st.markdown("### Retrieval summary")

            col1, col2, col3 = st.columns(3)

            col1.metric("Evidence chunks", len(bundle.evidence))
            col2.metric("Resolved periods", len(bundle.periods))
            col3.metric("Relevant products", len(bundle.products))

            # RESOLVED CONTEXT
            st.markdown("### Resolved context")

            st.write("**Periods:**", ", ".join(bundle.periods) or "None")
            st.write("**Products:**", ", ".join(bundle.products) or "None")
            st.write("**Business terms:**", ", ".join(bundle.terms) or "None")

            # READABLE DATA SCHEMAS
            st.markdown("### Readable data schemas")

            if bundle.schemas:
                for table, columns in bundle.schemas.items():
                    with st.expander(f"Table: {table}"):
                        st.dataframe(columns, width="stretch")
            else:
                st.info("No readable schemas were returned.")

            # EVIDENCE
            st.markdown("### Evidence")

            if bundle.evidence:
                for i, evidence in enumerate(bundle.evidence, start=1):
                    with st.expander(
                        f"{i}. {evidence.title} | Score: {evidence.score:.3f}"
                    ):
                        st.write("**Source:**", evidence.source_id)
                        st.write("**Document ID:**", evidence.doc_id)
                        st.write("**Access tier:**", evidence.tier)
                        st.write("**Period:**", evidence.month)
                        st.write("**Evidence text:**")
                        st.write(evidence.text)
            else:
                st.info("No evidence was found for this question and role.")

            # GOVERNANCE INFORMATION
            st.markdown("### Governance information")

            st.info(bundle.access_notice)

            if bundle.lineage:
                with st.expander("View data lineage"):
                    for item in bundle.lineage:
                        st.write("- ", item)

            if bundle.dropped_deprecated:
                with st.expander("Deprecated sources excluded"):
                    for item in bundle.dropped_deprecated:
                        st.write(item)

        except Exception as error:
            st.error(f"Retrieval failed: {error}")


st.divider()

st.caption(
    "ContextIQ | Governed retrieval prototype | Synthetic business data"
)
