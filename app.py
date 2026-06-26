import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import traceback

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
CASES_FILE = DATA_DIR / "cases.csv"
LASTMILE_FILE = DATA_DIR / "lastmile.csv"
MOVES_FILE = DATA_DIR / "moves.csv"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

CASE_COLS = [
    "case_id", "created_at", "mawb", "customer", "broker", "port", "eta",
    "manifest_file", "status", "op_note", "billing_status"
]

LASTMILE_COLS = [
    "case_id", "lastmile", "total_ctns", "weight_lbs", "rate", "amount"
]

MOVES_COLS = [
    "move_id", "case_id", "lastmile", "move_time", "ctns_out", "note"
]


def init_file(path, cols):
    if not path.exists():
        pd.DataFrame(columns=cols).to_csv(path, index=False)


def load_csv(path, cols):
    init_file(path, cols)
    try:
        df = pd.read_csv(path)
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        return df[cols]
    except Exception:
        return pd.DataFrame(columns=cols)


def save_csv(df, path, cols):
    df = df[cols]
    df.to_csv(path, index=False)


def load_cases():
    return load_csv(CASES_FILE, CASE_COLS)


def load_lastmile():
    df = load_csv(LASTMILE_FILE, LASTMILE_COLS)
    for c in ["total_ctns", "weight_lbs", "rate", "amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def load_moves():
    df = load_csv(MOVES_FILE, MOVES_COLS)
    df["ctns_out"] = pd.to_numeric(df["ctns_out"], errors="coerce").fillna(0).astype(int)
    return df


def save_cases(df):
    save_csv(df, CASES_FILE, CASE_COLS)


def save_lastmile(df):
    save_csv(df, LASTMILE_FILE, LASTMILE_COLS)


def save_moves(df):
    save_csv(df, MOVES_FILE, MOVES_COLS)


def normalize_column_name(col):
    return (
        str(col)
        .lower()
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "")
    )


def read_manifest_file(file_path):
    file_path = str(file_path).lower()

    if file_path.endswith(".csv"):
        return pd.read_csv(file_path)

    if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
        return pd.read_excel(file_path)

    return pd.DataFrame()


def parse_manifest_lastmile(file_path, case_id):
    df = read_manifest_file(file_path)

    if df.empty:
        return pd.DataFrame(columns=LASTMILE_COLS)

    original_columns = list(df.columns)
    df.columns = [normalize_column_name(c) for c in df.columns]

    lastmile_candidates = [
        "last_mile",
        "lastmile",
        "last_mile_provider",
        "last_mile_carrier",
        "carrier",
        "carrier_name",
        "dsp",
        "delivery_provider",
        "service_provider",
        "provider",
        "lastmile_provider",
        "lm",
        "route",
        "route_code",
        "destination",
        "delivery_company",
        "courier",
    ]

    ctn_candidates = [
        "ctns",
        "ctn",
        "cartons",
        "carton",
        "boxes",
        "box",
        "pcs",
        "pieces",
        "piece",
        "qty",
        "quantity",
        "package_qty",
        "packages",
        "package_count",
        "count",
    ]

    lastmile_col = next((c for c in lastmile_candidates if c in df.columns), None)
    ctn_col = next((c for c in ctn_candidates if c in df.columns), None)

    if not lastmile_col:
        return pd.DataFrame(columns=LASTMILE_COLS)

    df[lastmile_col] = df[lastmile_col].astype(str).str.strip()
    df = df[df[lastmile_col] != ""]
    df = df[df[lastmile_col].str.lower() != "nan"]

    if df.empty:
        return pd.DataFrame(columns=LASTMILE_COLS)

    if ctn_col:
        df[ctn_col] = pd.to_numeric(df[ctn_col], errors="coerce").fillna(0)
        result = df.groupby(lastmile_col, dropna=False)[ctn_col].sum().reset_index()
        result.columns = ["lastmile", "total_ctns"]
    else:
        result = df.groupby(lastmile_col, dropna=False).size().reset_index(name="total_ctns")
        result.columns = ["lastmile", "total_ctns"]

    result["total_ctns"] = pd.to_numeric(result["total_ctns"], errors="coerce").fillna(0).astype(int)
    result = result[result["total_ctns"] > 0]

    if result.empty:
        return pd.DataFrame(columns=LASTMILE_COLS)

    result["case_id"] = case_id
    result["weight_lbs"] = 0.0
    result["rate"] = 0.0
    result["amount"] = 0.0

    return result[LASTMILE_COLS]


def download_manifest(case_row):
    file_path = str(case_row.get("manifest_file", ""))
    if file_path and Path(file_path).exists():
        with open(file_path, "rb") as f:
            st.download_button(
                "Download Manifest",
                data=f,
                file_name=Path(file_path).name,
                mime="application/octet-stream",
                key=f"download_{case_row['case_id']}_{st.session_state.get('role_key', '')}"
            )
    else:
        st.warning("No manifest file uploaded.")


def create_case(mawb, customer, broker, port, eta, uploaded_file):
    cases = load_cases()

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
        "mawb": mawb.strip(),
        "customer": customer.strip(),
        "broker": broker,
        "port": port.strip(),
        "eta": eta.strftime("%Y-%m-%d"),
        "manifest_file": file_path,
        "status": "New",
        "op_note": "",
        "billing_status": "Pending",
    }

    cases = pd.concat([cases, pd.DataFrame([new_case])], ignore_index=True)
    save_cases(cases)

    if file_path:
        parsed_lm = parse_manifest_lastmile(file_path, case_id)
        if not parsed_lm.empty:
            lm = load_lastmile()
            lm = lm[lm["case_id"] != case_id]
            lm = pd.concat([lm, parsed_lm], ignore_index=True)
            save_lastmile(lm)

    return case_id


def get_case_lastmile(case_id):
    lm = load_lastmile()
    moves = load_moves()

    case_lm = lm[lm["case_id"] == case_id].copy()
    case_moves = moves[moves["case_id"] == case_id].copy()

    if case_lm.empty:
        return case_lm

    shipped = (
        case_moves.groupby("lastmile")["ctns_out"]
        .sum()
        .reset_index()
        .rename(columns={"ctns_out": "shipped_ctns"})
    )

    case_lm = case_lm.merge(shipped, on="lastmile", how="left")
    case_lm["shipped_ctns"] = case_lm["shipped_ctns"].fillna(0).astype(int)
    case_lm["remaining_ctns"] = case_lm["total_ctns"].astype(int) - case_lm["shipped_ctns"]
    case_lm["amount"] = case_lm["weight_lbs"] * case_lm["rate"]

    return case_lm


st.set_page_config(page_title="Customs Workflow MVP", layout="wide")

st.title("Customs Workflow Platform - MVP")
st.caption("客户上传 Manifest → 自动识别 Last Mile 箱数 → Broker 清关 → OP 出货 → Billing 计费")

role = st.sidebar.selectbox(
    "选择角色",
    ["Customer Portal", "Broker Dashboard", "OP Dashboard", "Billing Dashboard"]
)

st.session_state["role_key"] = role

cases = load_cases()


if role == "Customer Portal":
    st.header("Customer Portal")

    with st.form("new_case_form"):
        col1, col2 = st.columns(2)

        with col1:
            mawb = st.text_input("MAWB", "123-45678901")
            customer = st.text_input("Customer / Importer", "ABC Import LLC")
            port = st.text_input("Port", "JFK")

        with col2:
            broker = st.selectbox("Assigned Broker", ["Theo Customs", "Boston Broker", "NY Broker"])
            eta = st.date_input("ETA")

        uploaded_file = st.file_uploader(
            "Upload Manifest / Invoice / Packing List",
            type=["csv", "xlsx", "xls", "pdf"]
        )

        submitted = st.form_submit_button("Submit Case", type="primary")

    if submitted:
        try:
            if not mawb.strip():
                st.error("MAWB cannot be empty.")
            elif not customer.strip():
                st.error("Customer cannot be empty.")
            elif not port.strip():
                st.error("Port cannot be empty.")
            else:
                case_id = create_case(mawb, customer, broker, port, eta, uploaded_file)
                st.success(f"Case created: {case_id}")

                parsed = get_case_lastmile(case_id)
                if not parsed.empty:
                    st.info("Manifest parsed successfully. Last Mile CTNS were created automatically.")
                    st.dataframe(
                        parsed[["lastmile", "total_ctns"]],
                        use_container_width=True
                    )
                else:
                    st.warning("Case created, but no Last Mile CTNS were detected from the manifest. You can add them manually in OP Dashboard.")

                cases = load_cases()

        except Exception:
            st.error("Submit failed.")
            st.code(traceback.format_exc())

    st.subheader("Cases")

    if cases.empty:
        st.info("No cases yet.")
    else:
        st.dataframe(cases, use_container_width=True)

        selected = st.selectbox("Select case to download manifest", cases["case_id"].tolist())
        row = cases[cases["case_id"] == selected].iloc[0]

        download_manifest(row)


elif role == "Broker Dashboard":
    st.header("Broker Dashboard")

    if cases.empty:
        st.info("No cases yet.")
    else:
        selected = st.selectbox("Select Case", cases["case_id"].tolist())
        row = cases[cases["case_id"] == selected].iloc[0]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("MAWB", row["mawb"])
        col2.metric("Customer", row["customer"])
        col3.metric("Port", row["port"])
        col4.metric("ETA", row["eta"])

        download_manifest(row)

        st.subheader("Detected Last Mile CTNS")
        case_lm = get_case_lastmile(selected)

        if case_lm.empty:
            st.info("No Last Mile data detected yet.")
        else:
            st.dataframe(
                case_lm[["lastmile", "total_ctns", "shipped_ctns", "remaining_ctns"]],
                use_container_width=True
            )

        statuses = [
            "New",
            "Documents Received",
            "Waiting Customer Info",
            "Entry Filed",
            "Customs Hold",
            "Released",
            "Closed"
        ]

        current_index = statuses.index(row["status"]) if row["status"] in statuses else 0

        new_status = st.selectbox("Clearance Status", statuses, index=current_index)

        note = st.text_area(
            "Broker / OP Note",
            value="" if pd.isna(row["op_note"]) else str(row["op_note"])
        )

        if st.button("Save Broker Update", type="primary"):
            cases.loc[cases["case_id"] == selected, "status"] = new_status
            cases.loc[cases["case_id"] == selected, "op_note"] = note
            save_cases(cases)
            st.success("Broker update saved.")


elif role == "OP Dashboard":
    st.header("OP Dashboard")

    if cases.empty:
        st.info("No cases yet.")
    else:
        selected = st.selectbox("Select MAWB / Case", cases["case_id"].tolist())
        row = cases[cases["case_id"] == selected].iloc[0]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("MAWB", row["mawb"])
        col2.metric("Customer", row["customer"])
        col3.metric("Status", row["status"])
        col4.metric("ETA", row["eta"])

        download_manifest(row)

        st.subheader("Last Mile Plan")

        lm = load_lastmile()
        case_lm = get_case_lastmile(selected)

        if case_lm.empty:
            st.warning("No Last Mile plan found. Add it manually below.")
        else:
            st.dataframe(
                case_lm[["lastmile", "total_ctns", "shipped_ctns", "remaining_ctns"]],
                use_container_width=True
            )

        with st.form("add_lastmile_form"):
            c1, c2 = st.columns(2)

            with c1:
                lastmile = st.text_input("Last Mile", "SpeedX")

            with c2:
                total_ctns = st.number_input("Total CTNS for this Last Mile", min_value=0, step=1)

            add_lm = st.form_submit_button("Add / Update Last Mile", type="primary")

        if add_lm:
            if not lastmile.strip():
                st.error("Last Mile cannot be empty.")
            else:
                mask = (lm["case_id"] == selected) & (lm["lastmile"] == lastmile.strip())

                if mask.any():
                    lm.loc[mask, "total_ctns"] = int(total_ctns)
                else:
                    new_lm = {
                        "case_id": selected,
                        "lastmile": lastmile.strip(),
                        "total_ctns": int(total_ctns),
                        "weight_lbs": 0,
                        "rate": 0,
                        "amount": 0,
                    }
                    lm = pd.concat([lm, pd.DataFrame([new_lm])], ignore_index=True)

                save_lastmile(lm)
                st.success("Last Mile plan saved.")

        case_lm = get_case_lastmile(selected)

        if not case_lm.empty:
            st.subheader("Record Outbound Movement")

            moves = load_moves()
            lastmile_options = case_lm["lastmile"].tolist()

            with st.form("move_form"):
                c1, c2, c3 = st.columns(3)

                with c1:
                    move_lastmile = st.selectbox("Which Last Mile", lastmile_options)

                with c2:
                    move_time = st.datetime_input("Outbound Time", datetime.now())

                with c3:
                    ctns_out = st.number_input("CTNS Out", min_value=0, step=1)

                move_note = st.text_input("Note", "")
                save_move = st.form_submit_button("Save Outbound Movement", type="primary")

            if save_move:
                current = get_case_lastmile(selected)
                remaining = int(current[current["lastmile"] == move_lastmile]["remaining_ctns"].iloc[0])

                if ctns_out <= 0:
                    st.error("CTNS Out must be greater than 0.")
                elif ctns_out > remaining:
                    st.error(f"Cannot ship {ctns_out} CTNS. Remaining only {remaining}.")
                else:
                    move_id = f"MOVE-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

                    new_move = {
                        "move_id": move_id,
                        "case_id": selected,
                        "lastmile": move_lastmile,
                        "move_time": move_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "ctns_out": int(ctns_out),
                        "note": move_note,
                    }

                    moves = pd.concat([moves, pd.DataFrame([new_move])], ignore_index=True)
                    save_moves(moves)
                    st.success("Outbound movement saved.")

            st.subheader("Outbound History")

            moves = load_moves()
            case_moves = moves[moves["case_id"] == selected].copy()

            if case_moves.empty:
                st.info("No outbound movements yet.")
            else:
                st.dataframe(
                    case_moves[["move_time", "lastmile", "ctns_out", "note"]],
                    use_container_width=True
                )

            st.subheader("Updated Remaining")

            st.dataframe(
                get_case_lastmile(selected)[["lastmile", "total_ctns", "shipped_ctns", "remaining_ctns"]],
                use_container_width=True
            )


elif role == "Billing Dashboard":
    st.header("Billing Dashboard")

    if cases.empty:
        st.info("No cases yet.")
    else:
        selected = st.selectbox("Select MAWB / Case", cases["case_id"].tolist())
        row = cases[cases["case_id"] == selected].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("MAWB", row["mawb"])
        col2.metric("Customer", row["customer"])
        col3.metric("Billing Status", row["billing_status"])

        download_manifest(row)

        lm = load_lastmile()
        case_lm = get_case_lastmile(selected)

        if case_lm.empty:
            st.warning("No Last Mile data yet. OP needs to add Last Mile plan first.")
        else:
            st.subheader("Billing by Last Mile")

            edited = st.data_editor(
                case_lm[[
                    "lastmile",
                    "total_ctns",
                    "shipped_ctns",
                    "remaining_ctns",
                    "weight_lbs",
                    "rate",
                    "amount"
                ]],
                column_config={
                    "lastmile": st.column_config.TextColumn("Last Mile", disabled=True),
                    "total_ctns": st.column_config.NumberColumn("Total CTNS", disabled=True),
                    "shipped_ctns": st.column_config.NumberColumn("Shipped CTNS", disabled=True),
                    "remaining_ctns": st.column_config.NumberColumn("Remaining CTNS", disabled=True),
                    "weight_lbs": st.column_config.NumberColumn("Weight lbs"),
                    "rate": st.column_config.NumberColumn("Rate"),
                    "amount": st.column_config.NumberColumn("Amount", disabled=True),
                },
                hide_index=True,
                use_container_width=True,
                key="billing_editor"
            )

            billing_status = st.selectbox(
                "Billing Status",
                ["Pending", "Ready to Bill", "Invoiced", "Paid"]
            )

            if st.button("Save Billing", type="primary"):
                for _, r in edited.iterrows():
                    mask = (lm["case_id"] == selected) & (lm["lastmile"] == r["lastmile"])

                    lm.loc[mask, "weight_lbs"] = float(r["weight_lbs"])
                    lm.loc[mask, "rate"] = float(r["rate"])
                    lm.loc[mask, "amount"] = float(r["weight_lbs"]) * float(r["rate"])

                save_lastmile(lm)

                cases.loc[cases["case_id"] == selected, "billing_status"] = billing_status
                save_cases(cases)

                st.success("Billing saved.")

            refreshed = get_case_lastmile(selected)
            refreshed["amount"] = refreshed["weight_lbs"] * refreshed["rate"]

            total_amount = float(refreshed["amount"].sum())
            total_weight = float(refreshed["weight_lbs"].sum())
            total_ctns = int(refreshed["total_ctns"].sum())

            c1, c2, c3 = st.columns(3)
            c1.metric("Total CTNS", total_ctns)
            c2.metric("Total Weight lbs", f"{total_weight:,.2f}")
            c3.metric("Total Amount", f"${total_amount:,.2f}")

            st.subheader("Invoice Preview")

            invoice = refreshed[[
                "lastmile",
                "total_ctns",
                "shipped_ctns",
                "remaining_ctns",
                "weight_lbs",
                "rate",
                "amount"
            ]].copy()

            st.dataframe(invoice, use_container_width=True)
