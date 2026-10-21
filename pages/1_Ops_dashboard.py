import json
import os

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ops dashboard", layout="wide")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st.title("Ops dashboard — what does AI mean for the paralegal's job?")
st.warning("Synthetic demo data")

df = pd.DataFrame(json.load(open(os.path.join(HERE, "data", "pipeline.json"), encoding="utf-8")))
df["source"] = "pipeline"
df["new_from_app"] = ""

store = os.path.join(HERE, "data", "claims_store.json")
if os.path.exists(store):
    try:
        app_rows = []
        for r in json.load(open(store, encoding="utf-8")):
            c, a = r.get("claim") or {}, r.get("assessment") or {}
            g = (a.get("grounds") or [{}])[0] or {}
            app_rows.append({
                "id": r.get("id"), "received_at": str(r.get("created", ""))[:16],
                "issuer_type": c.get("issuer_type") or "private", "issuer_name": c.get("issuer_name") or "",
                "amount_dkk": c.get("amount_dkk") or 0, "category": g.get("category", ""),
                "model_probability": a.get("success_probability", 0), "model_verdict": a.get("verdict", ""),
                "human_decision": "pending", "status": r.get("status", "new"),
                "minutes_human_review": None, "source": "app", "new_from_app": "📱 new from app",
                "top_ground": g.get("title", ""),
            })
        if app_rows:
            df = pd.concat([df, pd.DataFrame(app_rows)], ignore_index=True)
    except Exception as e:
        st.caption(f"Could not read claims_store.json: {e}")
if "top_ground" not in df:
    df["top_ground"] = ""
df["top_ground"] = df["top_ground"].fillna("")
df["amount_dkk"] = pd.to_numeric(df["amount_dkk"], errors="coerce").fillna(0)
df["model_probability"] = pd.to_numeric(df["model_probability"], errors="coerce").fillna(0)

with st.sidebar:
    cats = sorted(c for c in df.category.unique() if c)
    sel_c = st.multiselect("Category", cats, default=cats)
    types = sorted(df.issuer_type.unique())
    sel_t = st.multiselect("Issuer type", types, default=types)
df = df[(df.category.isin(sel_c) | (df.category == "")) & df.issuer_type.isin(sel_t)]

FILED = ["filed", "won", "lost"]
decided = df[df.status.isin(["won", "lost"])]
band = df.model_probability.between(40, 60)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Open claims", int(df.status.isin(["new", "pending", "review", "filed"]).sum()))
c2.metric("Win rate of filed", f"{(decided.status == 'won').mean():.0%}" if len(decided) else "–")
c3.metric("DKK recovered", f"{int(df.loc[df.status == 'won', 'amount_dkk'].sum()):,}")
c4.metric("Avg human minutes / case", f"{df.minutes_human_review.mean():.1f}" if df.minutes_human_review.notna().any() else "–")
c5.metric("Cases needing human review", f"{band.mean():.0%}" if len(df) else "–")

order = ["strong", "medium", "weak"]
st.subheader("Does the model's verdict predict outcomes?")
l, r = st.columns(2)
fd = df[df.status.isin(FILED)]
wr = (fd.assign(w=fd.status.eq("won")).groupby("model_verdict").w.mean().reindex(order).fillna(0) * 100)
with l:
    st.caption("Win rate % by verdict (filed cases)")
    st.bar_chart(wr)
with r:
    st.dataframe(pd.crosstab(df.model_verdict, df.status).reindex([o for o in order if o in set(df.model_verdict)]),
                 width="stretch")

st.subheader("Where the paralegal's time goes now")
mins = df.groupby("model_verdict").minutes_human_review.mean().reindex(order).fillna(0)
st.caption("Avg human minutes per case by verdict band — time concentrates in the medium band")
st.bar_chart(mins)

st.subheader("Review queue (40–60% band)")
st.caption("Model drafts and recommends; a human files.")
q = df[band & df.status.isin(["new", "pending"])].sort_values("received_at", ascending=False)
q = q[["id", "received_at", "issuer_name", "amount_dkk", "category", "model_probability", "top_ground", "new_from_app"]].copy()
q = q.rename(columns={"top_ground": "summary"})
q["Human decision"] = q["id"].map(st.session_state.get("decisions", {}))
edited = st.data_editor(
    q, hide_index=True, width="stretch", key="queue",
    disabled=[c for c in q.columns if c != "Human decision"],
    column_config={"Human decision": st.column_config.SelectboxColumn(
        "Human decision", options=["file", "decline", "needs more evidence"])})
st.session_state["decisions"] = {i: d for i, d in zip(edited["id"], edited["Human decision"]) if d}
st.caption(f"{len(q)} cases in queue; {len(st.session_state['decisions'])} decided this session.")
