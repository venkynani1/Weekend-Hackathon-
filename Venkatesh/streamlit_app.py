"""Streamlit Community Cloud version of TalentGuard (bonus +5: free public deployment).

Same model, same outputs and same scoring code as the Flask app; only the UI
layer differs. Deploy: share.streamlit.io -> New app -> this repo, branch,
main file `streamlit_app.py`.

    streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from agent import load_queue
from scoring import CHOICE_FIELDS, FIELD_LABELS, INT_FIELDS, ROLES_BY_DEPARTMENT, ScoringService, ValidationError, validate_profile
from services import DEFAULT_OUTPUT_DIR, DashboardService, train_and_export

st.set_page_config(page_title="TalentGuard | Retention watch list", page_icon="static/img/favicon-32.png", layout="wide")


@st.cache_resource(show_spinner="Training the model on first start (about 10 seconds)...")
def services() -> tuple[DashboardService, ScoringService]:
    dashboard = DashboardService(DEFAULT_OUTPUT_DIR)
    if not dashboard.is_ready or not (DEFAULT_OUTPUT_DIR / "action_queue.json").exists():
        train_and_export()
    return dashboard, ScoringService()


dashboard, scorer = services()
data = dashboard.load()
metrics = data["metrics"]
ins = metrics["insights"]
biz = ins["business"]
watch = pd.DataFrame(data["watchlist"])

st.title("TalentGuard")
st.caption("Who is likely to resign next cycle, why, and what to do. Built on the public, synthetic IBM HR Analytics dataset.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Real leavers in the top 50", f"{biz['cycle']['leavers_reached']} of 50", f"{biz['cycle']['leavers_reached'] - round(biz['cycle']['leavers_reached_random'])} vs random")
c2.metric("Precision at 50", f"{metrics['selected_model_score']['precision_at_50']:.0%}", f"{metrics['selected_model_score']['lift_at_50']:.1f}x lift")
c3.metric("PR-AUC", f"{metrics['selected_model_score']['average_precision']:.3f}", metrics["selected_model"], delta_color="off")
c4.metric("Net savings per cycle", f"${biz['cycle']['net_savings']:,.0f}", f"{biz['cycle']['roi']:.1f}x return on HR time", delta_color="off")

tab_list, tab_score, tab_queue, tab_evidence = st.tabs(["Top 50 watch list", "Live scoring", "Approval queue", "Evidence"])

with tab_list:
    st.subheader("Top 50 watch list")
    view = watch[["Rank", "EmployeeNumber", "LeaveProbability", "Department", "JobRole", "RiskReason1", "RiskReason2", "RiskReason3", "PrimaryAction"]].copy()
    view["LeaveProbability"] = (view["LeaveProbability"] * 100).round(0).astype(int).astype(str) + "%"
    view.columns = ["Rank", "Employee", "Leave chance", "Department", "Role", "Reason 1", "Reason 2", "Reason 3", "First action"]
    st.dataframe(view, hide_index=True, use_container_width=True)
    st.download_button("Download watch list (CSV)", watch.to_csv(index=False), "TalentGuard_Top_50_Watchlist.csv", "text/csv")
    st.subheader("Top 10 action plan")
    for row in data["top_ten"]:
        with st.expander(f"#{int(row['Rank'])}  Employee {int(row['EmployeeNumber'])}, {row['JobRole']}: {row['PrimaryAction']}"):
            st.markdown("\n".join(f"{i}. {row[f'RiskReason{i}']}" for i in (1, 2, 3)))
            st.write(row["Recommendation"])

with tab_score:
    st.subheader("Score an employee and test interventions")
    options = [int(e) for e in watch["EmployeeNumber"]]
    employee = st.selectbox("Start from a watch-list employee", options, format_func=lambda e: f"Employee {e}")
    base = scorer.profile_for(employee)
    with st.form("score"):
        dept = st.selectbox(FIELD_LABELS["Department"], list(ROLES_BY_DEPARTMENT), index=list(ROLES_BY_DEPARTMENT).index(base["Department"]))
        roles = ROLES_BY_DEPARTMENT[dept]
        role = st.selectbox(FIELD_LABELS["JobRole"], roles, index=roles.index(base["JobRole"]) if base["JobRole"] in roles else 0)
        cols = st.columns(3)
        profile = {"Department": dept, "JobRole": role}
        for i, (field, choices) in enumerate(CHOICE_FIELDS.items()):
            profile[field] = cols[i % 3].selectbox(FIELD_LABELS[field], choices, index=choices.index(base[field]))
        for i, (field, (low, high)) in enumerate(INT_FIELDS.items(), start=len(CHOICE_FIELDS)):
            profile[field] = cols[i % 3].number_input(FIELD_LABELS[field], min_value=low, max_value=high, value=int(base[field]), step=1)
        submitted = st.form_submit_button("Score this employee", type="primary")
    if submitted:
        try:
            result = scorer.score(validate_profile(profile), employee)
        except ValidationError as error:
            for field, message in error.errors.items():
                st.error(f"{FIELD_LABELS.get(field, field)}: {message}")
        else:
            a, b, c = st.columns(3)
            a.metric("Leave chance", f"{result['leave_probability']:.0%}")
            b.metric("Replacement cost", f"${result['replacement_cost']:,.0f}")
            c.metric("Expected loss", f"${result['expected_loss']:,.0f}")
            st.markdown("**Top 3 reasons**\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(result["reasons"], 1)))
            st.info(f"**{result['primary_action']}**: {result['recommendation']}")
            if result["scenarios"]:
                table = pd.DataFrame(result["scenarios"])[["label", "risk_change_points", "cost", "net_value"]]
                table.columns = ["Intervention", "Risk change (pts)", "Cost ($)", "Net value ($)"]
                st.dataframe(table.round(1), hide_index=True, use_container_width=True)
            st.caption("Net value = drop in leave probability x replacement cost, minus intervention cost. Model sensitivity, not proof of cause.")

with tab_queue:
    st.subheader("Drafted outreach, PENDING_APPROVAL")
    st.caption("Nothing is sent. A named reviewer must approve each draft. Decisions here last for your browser session.")
    decisions = st.session_state.setdefault("decisions", {})
    for item in load_queue(DEFAULT_OUTPUT_DIR)[:10]:
        status = decisions.get(item["id"], item["status"])
        with st.expander(f"#{item['rank']} Employee {item['employee_number']}: {item['action']}  [{status}]"):
            left, right = st.columns(2)
            left.text(item["manager_brief"])
            right.markdown(f"**Subject:** {item['invite_subject']}")
            right.text(item["invite_body"])
            reviewer = st.text_input("Reviewer name", key=f"r-{item['id']}", max_chars=60)
            x, y = st.columns(2)
            if x.button("Approve", key=f"a-{item['id']}", disabled=len(reviewer.strip()) < 2):
                decisions[item["id"]] = f"APPROVED by {reviewer.strip()}"
                st.rerun()
            if y.button("Reject", key=f"x-{item['id']}", disabled=len(reviewer.strip()) < 2):
                decisions[item["id"]] = f"REJECTED by {reviewer.strip()}"
                st.rerun()

with tab_evidence:
    st.subheader("Model versus baselines (out-of-fold, capacity 50)")
    st.dataframe(pd.DataFrame(ins["baselines"])[["name", "caught_of_50", "precision_at_50", "average_precision", "roc_auc", "note"]],
                 hide_index=True, use_container_width=True)
    st.subheader("Data traps handled")
    st.table(pd.DataFrame(ins["eda"]["traps"]))
    st.subheader("Findings")
    for f in ins["eda"]["findings"]:
        st.markdown(f"**{f['title']}.** {f['evidence']} *{f['so_what']}*")
    st.subheader("Capacity curve")
    st.bar_chart(pd.DataFrame(ins["capacity_curve"]).set_index("k")["precision"])

st.divider()
st.caption("Prototype for a hackathon. Not for employment decisions. See the privacy policy and terms in the Flask app (/privacy, /terms).")
