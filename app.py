import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import traceback

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
CASES_FILE = DATA_DIR / "cases.csv"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

DEFAULT_COLUMNS = [
    "case_id", "created_at", "customer", "broker", "port", "eta",
    "manifest_file", "status", "op_note", "billing_status",
    "broker_fee", "duty", "mpf", "total"
]

def init_data():
    if not CASES_FILE.exists():
        pd.DataFrame(columns=DEFAULT_COLUMNS).to_csv(CASES_FILE, index=False)

def load_cases():
    init_data()
    try:
        return pd.read_csv(CASES_FILE)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=DEFAULT_COLUMNS)

def save_cases(df):
    df = df[DEFAULT_COLUMNS]
    df.to_csv(CASES_FILE, index=False)

def create_case(customer, broker, port, eta, uploaded_file):
    df = load_cases()

    case_id = f"CUS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    file_path = ""

    if uploaded_file is not None:
        safe_name = uploaded_file.name.replace(" ", "_")
        file_path = str(UPLOAD_DIR / f"{case_id}_{safe_name}")
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

    new_case = {
        "case_id": case_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer": customer.strip(),
        "broker": broker,
        "port": port.strip(),
        "eta": eta.strftime("%Y-%m-%d"),
        "manifest_file": file_path,
        "status": "New",
        "op_note": "",
        "billing_status": "Pending",
        "broker_fee": 125.00,
        "duty": 0.00,
        "mpf": 0.00,
        "total": 125.00,
    }

    df = pd.concat([df, pd.DataFrame([new_case])], ignore_index=True)
    save_cases(df)
    return case_id

st.set_page_config(page_title="Customs Workflow MVP", layout="wide")

st.title("Customs Workflow Platform - MVP")
st.caption("客户上传 Manifest → Broker 处理 → OP 跟踪 → Billing 出账")

role = st.sidebar.selectbox(
    "选择角色",
    ["Customer Portal", "Broker Dashboard", "OP Dashboard", "Billing Dashboard"]
)

df = load_cases()

if role == "Customer Portal":
    st.header("Customer Portal")
    st.subheader("Create New Clearance Case")

    with st.form("new_case_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            customer = st.text_input("Customer / Importer", "ABC Import LLC")
            port = st.text_input("Port", "LAX")
        with col2:
            broker = st.selectbox("Assigned Broker", ["Theo Customs", "Boston Broker", "NY Broker"])
            eta = st.date_input("ETA")

        uploaded_file = st.file_uploader(
            "Upload Manifest / Invoice / Packing List",
            type=["csv", "xlsx", "pdf"]
        )

        submitted = st.form_submit_button("Submit Case", type="primary")

    if submitted:
        try:
            if not customer.strip():
                st.error("Customer / Importer cannot be empty.")
            elif not port.strip():
                st.error("Port cannot be empty.")
            else:
                case_id = create_case(customer, broker, port, eta, uploaded_file)
                st.success(f"Case created successfully: {case_id}")
                st.balloons()
                df = load_cases()
        except Exception:
            st.error("Submit failed. Full error below:")
            st.code(traceback.format_exc())

    st.subheader("All Cases")
    df = load_cases()
    if df.empty:
        st.info("No cases yet.")
    else:
        st.dataframe(df, use_container_width=True)

elif role == "Broker Dashboard":
    st.header("Broker Dashboard")
    st.caption("Broker 在这里接收案件、更新清关状态、上传 Entry 信息。")

    df = load_cases()
    if df.empty:
        st.info("No cases yet.")
    else:
        selected = st.selectbox("Select Case", df["case_id"].tolist())
        row = df[df["case_id"] == selected].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Customer", row["customer"])
        col2.metric("Port", row["port"])
        col3.metric("ETA", row["eta"])

        st.write("Current Status:", row["status"])

        statuses = ["New", "Documents Received", "Waiting Customer Info", "Entry Filed", "Customs Hold", "Released", "Closed"]
        current_index = statuses.index(row["status"]) if row["status"] in statuses else 0

        new_status = st.selectbox("Update Clearance Status", statuses, index=current_index)
        note = st.text_area("Broker / OP Note", value="" if pd.isna(row["op_note"]) else str(row["op_note"]))

        if st.button("Save Broker Update", type="primary"):
            df.loc[df["case_id"] == selected, "status"] = new_status
            df.loc[df["case_id"] == selected, "op_note"] = note
            save_cases(df)
            st.success("Case updated.")

elif role == "OP Dashboard":
    st.header("OP Dashboard")
    st.caption("运营查看所有 shipment 状态、异常、SLA。")

    df = load_cases()
    if df.empty:
        st.info("No cases yet.")
    else:
        status_list = sorted(df["status"].dropna().unique().tolist())
        status_filter = st.multiselect("Filter by Status", status_list, default=status_list)
        filtered = df[df["status"].isin(status_filter)]

        st.dataframe(
            filtered[["case_id", "created_at", "customer", "broker", "port", "eta", "status", "op_note"]],
            use_container_width=True
        )

        st.subheader("Status Summary")
        st.bar_chart(df["status"].value_counts())

elif role == "Billing Dashboard":
    st.header("Billing Dashboard")
    st.caption("财务根据 case 自动计算 broker fee、duty、MPF，并生成账单。")

    df = load_cases()
    if df.empty:
        st.info("No cases yet.")
    else:
        selected = st.selectbox("Select Case", df["case_id"].tolist())
        row = df[df["case_id"] == selected].iloc[0]

        with st.form("billing_form"):
            broker_fee = st.number_input("Broker Fee", min_value=0.0, value=float(row["broker_fee"]))
            duty = st.number_input("Duty", min_value=0.0, value=float(row["duty"]))
            mpf = st.number_input("MPF", min_value=0.0, value=float(row["mpf"]))
            billing_status = st.selectbox("Billing Status", ["Pending", "Ready to Bill", "Invoiced", "Paid"])

            submitted = st.form_submit_button("Save Billing", type="primary")

        if submitted:
            total = broker_fee + duty + mpf
            df.loc[df["case_id"] == selected, "broker_fee"] = broker_fee
            df.loc[df["case_id"] == selected, "duty"] = duty
            df.loc[df["case_id"] == selected, "mpf"] = mpf
            df.loc[df["case_id"] == selected, "total"] = total
            df.loc[df["case_id"] == selected, "billing_status"] = billing_status
            save_cases(df)
            st.success(f"Billing updated. Total: ${total:,.2f}")
            row = load_cases()[load_cases()["case_id"] == selected].iloc[0]

        st.subheader("Invoice Preview")
        invoice = pd.DataFrame([
            {"Item": "Broker Fee", "Amount": float(row["broker_fee"])},
            {"Item": "Duty", "Amount": float(row["duty"])},
            {"Item": "MPF", "Amount": float(row["mpf"])},
            {"Item": "Total", "Amount": float(row["total"])},
        ])
        st.table(invoice)
