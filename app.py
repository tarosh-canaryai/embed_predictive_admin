import streamlit as st
import requests
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
import os


# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000/api/v1/admin"
PAGE_LIMIT = 10


# SERVER_KEY = os.getenv("APP_SERVER_KEY")
SERVER_KEY = st.secrets["APP_SERVER_KEY"]
HEADERS = {"Authorization": f"Bearer {SERVER_KEY}"}

st.set_page_config(page_title="Admin Prediction Dashboard", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

    /* Detail panel card */
    .detail-card {
        background: #0f1117;
        border: 1px solid #2a2d3a;
        border-radius: 12px;
        padding: 24px 28px;
        margin-top: 8px;
    }
    .detail-label {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        color: #666;
        text-transform: uppercase;
        margin-bottom: 2px;
    }
    .detail-value {
        font-family: 'DM Mono', monospace;
        font-size: 0.85rem;
        color: #e0e0e0;
        margin-bottom: 14px;
    }
    .badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .badge-completed { background: #1a3a2a; color: #4caf82; border: 1px solid #2d6b46; }
    .badge-pending   { background: #3a2a1a; color: #f0a050; border: 1px solid #8a5a20; }
    .badge-failed    { background: #3a1a1a; color: #f05050; border: 1px solid #8a2020; }
    .badge-processing{ background: #1a2a3a; color: #5090f0; border: 1px solid #2050a0; }
    .section-title {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: #555;
        text-transform: uppercase;
        border-bottom: 1px solid #1e2130;
        padding-bottom: 6px;
        margin-bottom: 16px;
    }
    /* Make the dataframe selection highlight more visible */
    [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)





# --- Helpers ---
def fetch_data(endpoint: str, params: dict = None):
    try:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        r = requests.get(f"{API_BASE_URL}{endpoint}", params=clean_params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot connect to API at {API_BASE_URL}")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API error ({e.response.status_code}): {e.response.text}")
        return None
    except Exception as e:
        st.error(f"❌ {e}")
        return None


@st.cache_data(ttl=60)
def fetch_data_cached(endpoint: str, params_tuple: tuple = ()):
    return fetch_data(endpoint, dict(params_tuple) if params_tuple else None)


def format_stage(s): return s.replace("_", " ").title() if s else "—"

def badge_html(status):
    cls = f"badge-{status}" if status in ["completed","pending","failed","processing"] else "badge-pending"
    return f'<span class="badge {cls}">{status}</span>'



# --- Authentication Logic ---
def check_password():
    """Returns True if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if (
            st.session_state["username"] == st.secrets["auth"]["username"]
            and st.session_state["password"] == st.secrets["auth"]["password"]
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show inputs for username + password.
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 User not known or password incorrect")
        return False
    else:
        # Password correct.
        return True

# --- Main App Execution ---
if check_password():

    # ── Header ──────────────────────────────────────────────────────────────────
    st.title("🚀 Admin Prediction Dashboard")
    st.caption("Employee Churn Prediction · Job Management")

    # ── Stats ────────────────────────────────────────────────────────────────────
    st.subheader("📊 System Statistics")
    stats = fetch_data_cached("/stats")

    if stats:
        statuses = stats.get("statuses", {})
        stages   = stats.get("stages", {})
        total    = sum(statuses.values())

        cols = st.columns(len(statuses) + 1)
        cols[0].metric("Total Jobs", total)
        for i, (s, n) in enumerate(statuses.items()):
            cols[i+1].metric(f"{s.title()} Jobs", n)

        if stages:
            st.markdown("**Pipeline Stages**")
            scols = st.columns(len(stages))
            for i, (s, n) in enumerate(stages.items()):
                scols[i].metric(format_stage(s), n)

    st.divider()

    # ── Filters ──────────────────────────────────────────────────────────────────
    st.subheader("📋 Prediction Jobs")

    fc1, fc2, fc3 = st.columns([3, 1, 1])
    with fc1:
        search_query = st.text_input("🔍 Search (Email, Name, Company)", "")
    with fc2:
        status_choice = st.selectbox("Status", ["All","completed","pending","failed","processing"])
        status_filter = None if status_choice == "All" else status_choice
    with fc3:
        page_number = st.number_input("Page", min_value=1, value=1, step=1)

    params = {"page": page_number, "limit": PAGE_LIMIT}
    if status_filter:  params["status"] = status_filter
    if search_query:   params["search"] = search_query

    jobs_data = fetch_data_cached("/jobs", params_tuple=tuple(sorted(params.items())))

    if not jobs_data:
        st.warning("Could not load jobs.")
        st.stop()

    raw_items   = jobs_data.get("items", [])
    total_count = jobs_data.get("total_count", 0)
    total_pages = max(1, (total_count + PAGE_LIMIT - 1) // PAGE_LIMIT)

    st.caption(f"Showing {len(raw_items)} of {total_count} jobs · Page {page_number}/{total_pages}")

    if not raw_items:
        st.info("No jobs found matching your filters.")
        st.stop()

    # ── Build display DataFrame ───────────────────────────────────────────────────
    rows = []
    for item in raw_items:
        created = item.get("created_at", "")
        date_str = created[:10] if created else "—"
        time_str = created[11:16] if len(created) > 10 else ""

        m = item.get("metrics") or {}
        acc = f"{m['accuracy']*100:.1f}%" if "accuracy" in m else "—"
        tested = m.get("total_tested", "—")

        rows.append({
            "Name":        item.get("client_name", "—"),
            "Company":     item.get("company_name", "—"),
            "Email":       item.get("client_email", "—"),
            "Status":      item.get("status", "—").upper(),
            "Stage":       format_stage(item.get("current_stage", "")),
            "Accuracy":    acc,
            "Tested":      str(tested),
            "Date":        date_str,
            "Time":        time_str,
        })

    df = pd.DataFrame(rows)

    # ── Clickable table ───────────────────────────────────────────────────────────
    selection = st.dataframe(
        df,
        width='stretch',
        hide_index=True,
        height=min(40 + len(df) * 35, 420),
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Name":     st.column_config.TextColumn("Name",     width="medium"),
            "Company":  st.column_config.TextColumn("Company",  width="medium"),
            "Email":    st.column_config.TextColumn("Email",    width="large"),
            "Status":   st.column_config.TextColumn("Status",   width="small"),
            "Stage":    st.column_config.TextColumn("Stage",    width="large"),
            "Accuracy": st.column_config.TextColumn("Accuracy", width="small"),
            "Tested":   st.column_config.TextColumn("Tested",   width="small"),
            "Date":     st.column_config.TextColumn("Date",     width="small"),
            "Time":     st.column_config.TextColumn("Time",     width="small"),
        }
    )

    selected_rows = selection.selection.rows if selection and selection.selection else []

    # ── Detail panel ──────────────────────────────────────────────────────────────
    if not selected_rows:
        st.markdown(
            '<div style="text-align:center;padding:32px;color:#444;font-size:0.9rem;">'
            '↑ Click the checkbox on any row to view job details'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        idx  = selected_rows[0]
        item = raw_items[idx]

        job_id    = item.get("id", "")
        name      = item.get("client_name", "—")
        company   = item.get("company_name", "—")
        email     = item.get("client_email", "—")
        phone     = item.get("client_phone", "")
        status    = item.get("status", "pending")
        stage     = item.get("current_stage", "")
        created   = item.get("created_at", "")
        error_msg = item.get("error_message")
        metrics   = item.get("metrics") or {}
        blob_url  = item.get("blob_url")

        date_str = created[:10] if created else "—"
        time_str = created[11:19] if len(created) > 10 else ""

        st.markdown("---")
        st.markdown(f"#### 🔍 Job Detail — {name} · {company}")

        left, right = st.columns([1, 2])

        # ── Left: Identity + status ──
        with left:
            st.markdown('<div class="section-title">Client Info</div>', unsafe_allow_html=True)

            fields = [
                ("Name",    name),
                ("Company", company),
                ("Email",   email),
                ("Phone",   phone or "—"),
                ("Job ID",  job_id),
                ("Created", f"{date_str} {time_str}"),
            ]
            for label, val in fields:
                st.markdown(f'<div class="detail-label">{label}</div><div class="detail-value">{val}</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-title" style="margin-top:8px;">Status</div>', unsafe_allow_html=True)
            st.markdown(badge_html(status), unsafe_allow_html=True)
            st.markdown(f'<div class="detail-label" style="margin-top:10px;">Stage</div><div class="detail-value">{format_stage(stage)}</div>', unsafe_allow_html=True)

            if error_msg:
                st.error(f"⚠️ {error_msg}")

        # ── Right: Metrics + download ──
        with right:
            st.markdown('<div class="section-title">Result Metrics</div>', unsafe_allow_html=True)

            if metrics:
                has_actuals = metrics.get("has_actuals", False)
                scalar_keys = ["accuracy", "precision", "recall",
                            "total_tested", "predicted_churned", "predicted_retained"]
                displayable = {k: metrics[k] for k in scalar_keys if k in metrics}

                if displayable:
                    m_cols = st.columns(len(displayable))
                    for i, (m_name, m_val) in enumerate(displayable.items()):
                        label_str = m_name.replace("_", " ").title()
                        if isinstance(m_val, float) and 0.0 <= m_val <= 1.0:
                            m_cols[i].metric(label_str, f"{m_val*100:.1f}%")
                        else:
                            m_cols[i].metric(label_str, m_val)

                if not has_actuals:
                    st.caption("ℹ️ No actuals provided — accuracy metrics unavailable.")

                cm = metrics.get("confusion_matrix")
                if cm and len(cm) == 2:
                    st.markdown("**Confusion Matrix**")
                    cm_df = pd.DataFrame(
                        {"Predicted: Retained": [cm[0][0], cm[1][0]],
                        "Predicted: Churned":  [cm[0][1], cm[1][1]]},
                        index=["Actual: Retained", "Actual: Churned"]
                    )
                    st.dataframe(cm_df, width='content')
            else:
                st.info("No metrics available for this job yet.")

            st.markdown('<div class="section-title" style="margin-top:20px;">Download</div>', unsafe_allow_html=True)

            if blob_url:
                url_key = f"url_{job_id}"
                if url_key not in st.session_state:
                    st.session_state[url_key] = None

                if st.button("🔗 Generate Secure Download Link", key=f"dl_{job_id}"):
                    with st.spinner("Generating SAS token..."):
                        res = fetch_data(f"/download-results/{job_id}")
                        if res and "download_url" in res:
                            st.session_state[url_key] = res["download_url"]
                        else:
                            st.error("Could not generate download link.")

                if st.session_state.get(url_key):
                    st.success("✅ Secure link ready (valid 1 hour)")
                    st.markdown(f"[⬇️ **Download predictions.csv**]({st.session_state[url_key]})")
            else:
                st.caption("⚪ No result file generated yet.")