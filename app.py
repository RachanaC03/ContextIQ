import streamlit as st

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
    value="Why did customer complaints increase last month, which products were affected, and what should we do?",
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

            st.markdown("### Generated answer report")

            st.write(answer["summary"])

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

            st.markdown("### Retrieval summary")

            col1, col2, col3 = st.columns(3)

            col1.metric("Evidence chunks", len(bundle.evidence))
            col2.metric("Resolved periods", len(bundle.periods))
            col3.metric("Relevant products", len(bundle.products))

            st.markdown("### Resolved context")

            st.write("**Periods:**", ", ".join(bundle.periods) or "None")
            st.write("**Products:**", ", ".join(bundle.products) or "None")
            st.write("**Business terms:**", ", ".join(bundle.terms) or "None")

            st.markdown("### Readable data schemas")

            if bundle.schemas:
                for table, columns in bundle.schemas.items():
                    with st.expander(f"Table: {table}"):
                        st.dataframe(columns, width="stretch")
            else:
                st.info("No readable schemas were returned.")

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