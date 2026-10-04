"""Local machining-order app with a login screen and a left-hand menu."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from brand import COMPANY_NAME, LOGO_PATH, TAGLINE, USERS, ensure_logo
from parts import photo_data_uri
from workbook import (
    COMPLETED_COLORS,
    COMPLETED_STATUSES,
    DEFAULT_WORKBOOK,
    EDITOR_COLUMNS,
    PROGRAM_STATUSES,
    RISK_COLORS,
    RISKS,
    YES_NO,
    analysis_frame,
    ensure_workbook,
    for_editor,
    load_orders,
    save_orders,
    validate,
    workbook_bytes,
)

ensure_logo()
st.set_page_config(
    page_title=COMPANY_NAME,
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

MENU = [
    "Dashboard",
    "Master table",
    "Rejection data",
    "All open orders",
    "All closed",
    "RMA orders",
]
AEROSPACE_BLUE = "#D6EAF8"
TABLE_COLUMNS = EDITOR_COLUMNS
SUMMARY_COLUMNS = [
    "APM NO",
    "Part Photo",
    "Customer",
    "Part Number",
    "Qty",
    "Dispatch Date",
    "Risk",
    "Planning",
    "Completed Status",
    "RMA Status",
    "Is Aerospace Order",
]


def init_state() -> None:
    ensure_workbook(DEFAULT_WORKBOOK)
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    if "customer" not in st.session_state:
        st.session_state.customer = None
    if st.session_state.get("authenticated") and "role" not in st.session_state:
        st.session_state.role = "planner"
        st.session_state.username = "admin"
    current = st.session_state.get("orders")
    missing = current is None or any(column not in getattr(current, "columns", []) for column in EDITOR_COLUMNS)
    if missing:
        st.session_state.orders = load_orders(DEFAULT_WORKBOOK)
        st.session_state.editor_version += 1


def is_elevated() -> bool:
    return st.session_state.get("role") == "elevated"


def brand_lockup(compact: bool = False) -> None:
    logo, title = st.columns([1, 8], vertical_alignment="center")
    logo.image(str(LOGO_PATH), width=56 if compact else 84)
    if compact:
        title.markdown(f"**{COMPANY_NAME}**")
    else:
        title.markdown(f"### {COMPANY_NAME}")
        title.caption(TAGLINE)


def login_page() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
        .block-container {max-width: 460px; padding-top: 8vh;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.image(str(LOGO_PATH), width=96)
    st.markdown(f"# {COMPANY_NAME}")
    st.caption(TAGLINE)
    st.markdown(
        "<div style='height:3px;background:linear-gradient(90deg,#C47B2B,#1F4E79);"
        "border-radius:2px;margin:0.6rem 0 1.2rem 0;'></div>",
        unsafe_allow_html=True,
    )
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
    st.caption("Leave both fields blank to sign in, or use admin / machining.")
    st.caption("Elevated user, can set Completed Status: lead / precision")
    if submitted:
        username = username.strip()
        if username == "" and password == "":
            st.session_state.authenticated = True
            st.session_state.username = "guest"
            st.session_state.role = "planner"
            st.rerun()
        record = USERS.get(username)
        if record and password == record["password"]:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.role = record["role"]
            st.rerun()
        else:
            st.error("Unknown username or password.")


def ready_orders(orders: pd.DataFrame) -> pd.DataFrame:
    return analysis_frame(orders, date.today())


def filter_search(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    text = query.strip().lower()
    if not text or frame.empty:
        return frame
    columns = [
        column
        for column in frame.columns
        if column not in {"Part Photo", "Overdue", "Internal Reject"}
    ]
    mask = pd.Series(False, index=frame.index)
    for column in columns:
        values = frame[column].fillna("").astype(str).str.lower()
        mask = mask | values.str.contains(text, regex=False, na=False)
    return frame.loc[mask]


def apply_search(frame: pd.DataFrame, key: str) -> pd.DataFrame | None:
    query = st.text_input(
        "Search",
        placeholder="APM, PO, part, customer, process, status…",
        key=key,
    )
    found = filter_search(frame, query)
    if query.strip():
        st.caption(f"{len(found)} of {len(frame)} orders")
    if query.strip() and found.empty:
        st.info(f"No orders match “{query.strip()}”.")
        return None
    return found


def style_orders(frame: pd.DataFrame):
    def paint(row: pd.Series) -> list[str]:
        if str(row.get("Is Aerospace Order", "")).strip() == "Yes":
            return [f"background-color: {AEROSPACE_BLUE}"] * len(row)
        return [""] * len(row)

    return frame.style.apply(paint, axis=1)


def present(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    view = frame.copy()
    for column in ("PO Date", "Dispatch Date"):
        if column in view:
            view[column] = [
                None
                if pd.isna(value)
                else value.date()
                if hasattr(value, "date")
                else value
                for value in view[column]
            ]
    if "Part Photo" in view:
        view["Part Photo"] = [photo_data_uri(str(value)) if value else "" for value in view["Part Photo"]]
    return view[columns]


def column_config(elevated: bool, images: bool) -> dict:
    photo = (
        st.column_config.ImageColumn("Part Photo", help="Part picture", width="small")
        if images
        else st.column_config.TextColumn(
            "Part Photo",
            help="Picture file kept with the row. The image shows when editing is off.",
            disabled=True,
            width="medium",
        )
    )
    return {
        "APM NO": st.column_config.TextColumn(width="small"),
        "PO Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "PO Number": st.column_config.TextColumn(width="small"),
        "Part Number": st.column_config.TextColumn(width="small"),
        "Part Photo": photo,
        "Qty": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
        "Dispatch Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "Specification": st.column_config.TextColumn(width="large"),
        "Risk": st.column_config.SelectboxColumn(options=RISKS, default="Medium", required=True),
        "RM Size": st.column_config.TextColumn(width="medium"),
        "Action Qty": st.column_config.NumberColumn(min_value=0, step=1, format="%d", default=0),
        "RM Status": st.column_config.TextColumn(width="large"),
        "Process": st.column_config.TextColumn(width="large"),
        "Tools & Accessories": st.column_config.TextColumn(width="medium"),
        "Special Process & Instruments": st.column_config.TextColumn(width="medium"),
        "Inserts": st.column_config.TextColumn(width="small"),
        "Enquiry": st.column_config.TextColumn(width="large"),
        "Program Status": st.column_config.SelectboxColumn(
            options=PROGRAM_STATUSES, default="Incomplete", required=True
        ),
        "Planning": st.column_config.TextColumn(
            width="large",
            help="Free text, for example In-house, Turning out, or Milling in-house completed.",
        ),
        "Machining Status": st.column_config.TextColumn(width="large"),
        "Review": st.column_config.TextColumn(width="large"),
        "Deviation": st.column_config.TextColumn(width="large"),
        "Customer": st.column_config.TextColumn(),
        "Completed Status": st.column_config.SelectboxColumn(
            options=COMPLETED_STATUSES,
            default="Not started",
            required=True,
            disabled=not elevated,
            help="Only an elevated user can change the completion status.",
        ),
        "RMA Status": st.column_config.SelectboxColumn(options=YES_NO, default="No", required=True),
        "Is Aerospace Order": st.column_config.SelectboxColumn(
            options=YES_NO, default="No", required=True
        ),
    }


def show_orders(frame: pd.DataFrame, columns: list[str], empty: str) -> None:
    if frame.empty:
        st.info(empty)
        return
    view = present(frame, columns)
    st.dataframe(
        style_orders(view),
        hide_index=True,
        width="stretch",
        height=640,
        row_height=72,
        column_config=column_config(True, images=True),
    )


def dashboard(orders: pd.DataFrame) -> None:
    frame = ready_orders(orders)
    if frame.empty:
        st.info("Add a complete order on the master table to see the dashboard.")
        return

    filters = st.columns(3)
    customers = filters[0].multiselect(
        "Customer", sorted(frame["Customer"].unique()), placeholder="All customers"
    )
    risks = filters[1].multiselect("Risk", [risk for risk in RISKS if risk in set(frame["Risk"])], placeholder="All risks")
    aerospace = filters[2].multiselect(
        "Aerospace",
        [value for value in YES_NO if value in set(frame["Is Aerospace Order"])],
        placeholder="Aerospace and others",
    )
    if customers:
        frame = frame[frame["Customer"].isin(customers)]
    if risks:
        frame = frame[frame["Risk"].isin(risks)]
    if aerospace:
        frame = frame[frame["Is Aerospace Order"].isin(aerospace)]
    if frame.empty:
        st.info("No orders match these filters.")
        return
    found = apply_search(frame, "search_dashboard")
    if found is None:
        return
    frame = found

    open_orders = frame[frame["Completed Status"] != "Completed"]
    overdue = frame[frame["Overdue"]]
    metrics = st.columns(4)
    metrics[0].metric("Orders", f"{len(frame):,}")
    metrics[1].metric("Open", f"{len(open_orders):,}")
    metrics[2].metric("Closed", f"{(frame['Completed Status'] == 'Completed').sum():,}")
    metrics[3].metric("Overdue", f"{len(overdue):,}")
    metrics = st.columns(4)
    metrics[0].metric("Aerospace", f"{(frame['Is Aerospace Order'] == 'Yes').sum():,}")
    metrics[1].metric("Internal rejects", f"{int(frame['Internal Reject'].sum()):,}")
    metrics[2].metric("RMA", f"{(frame['RMA Status'] == 'Yes').sum():,}")
    metrics[3].metric("High risk", f"{(frame['Risk'] == 'High').sum():,}")

    left, right = st.columns(2)
    by_status = (
        frame["Completed Status"].value_counts().rename_axis("Completed Status").reset_index(name="Orders")
    )
    status_chart = px.pie(
        by_status,
        names="Completed Status",
        values="Orders",
        hole=0.55,
        color="Completed Status",
        color_discrete_map=COMPLETED_COLORS,
        title="Orders by completion",
    )
    status_chart.update_layout(margin=dict(l=10, r=10, t=48, b=10), height=360)
    left.plotly_chart(status_chart, width="stretch")

    by_customer = (
        frame.groupby("Customer", as_index=False)
        .size()
        .rename(columns={"size": "Orders"})
        .sort_values("Orders")
    )
    customer_chart = px.bar(
        by_customer, x="Orders", y="Customer", orientation="h", title="Orders by customer"
    )
    customer_chart.update_layout(margin=dict(l=10, r=10, t=48, b=10), height=360, yaxis_title="")
    customer_chart.update_traces(marker_color="#1F4E79")
    right.plotly_chart(customer_chart, width="stretch")

    left, right = st.columns(2)
    by_risk = frame["Risk"].value_counts().rename_axis("Risk").reset_index(name="Orders")
    risk_chart = px.pie(
        by_risk,
        names="Risk",
        values="Orders",
        hole=0.55,
        color="Risk",
        color_discrete_map=RISK_COLORS,
        title="Orders by risk",
    )
    risk_chart.update_layout(margin=dict(l=10, r=10, t=48, b=10), height=360)
    left.plotly_chart(risk_chart, width="stretch")

    by_plan = (
        frame.groupby("Planning", as_index=False)
        .size()
        .rename(columns={"size": "Orders"})
        .sort_values("Orders", ascending=False)
    )
    plan_chart = px.bar(by_plan, x="Planning", y="Orders", title="Planning")
    plan_chart.update_layout(margin=dict(l=10, r=10, t=48, b=10), height=360, xaxis_title="")
    plan_chart.update_traces(marker_color="#4C78A8")
    right.plotly_chart(plan_chart, width="stretch")

    st.subheader("Overdue open orders")
    show_orders(
        overdue.sort_values("Dispatch Date"),
        SUMMARY_COLUMNS,
        "No open orders are past the dispatch date.",
    )


def lock_completed_status(edited: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    """Keep completion status unchanged for a planner, including when the APM number is edited."""
    locked = edited.copy()
    previous_status = list(previous["Completed Status"])
    if len(edited) == len(previous):
        locked["Completed Status"] = previous_status
        return locked
    by_apm = {
        str(apm).strip(): status
        for apm, status in zip(previous["APM NO"], previous["Completed Status"])
        if str(apm).strip()
    }
    locked["Completed Status"] = [
        by_apm.get(str(apm).strip(), "Not started") for apm in edited["APM NO"]
    ]
    return locked


def editor_page(orders: pd.DataFrame) -> None:
    st.caption(
        "Dropdowns: Risk, Program Status, Completed Status, RMA Status, and Is Aerospace Order. "
        "Planning, process, materials, enquiry, machining, review, and deviation are free text. "
        "Aerospace rows are light blue in the view. "
        "Only an elevated user can change Completed Status."
    )
    editing = st.toggle("Edit master table", key="edit_master")
    if editing:
        edited = st.data_editor(
            for_editor(orders),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            height=640,
            row_height=48,
            key=f"orders_editor_{st.session_state.editor_version}",
            column_order=EDITOR_COLUMNS,
            column_config=column_config(is_elevated(), images=False),
        )
        if not is_elevated():
            edited = lock_completed_status(edited, orders)
        st.session_state.orders = for_editor(edited)
    else:
        visible = ready_orders(orders)
        found = apply_search(visible, "search_master")
        if found is not None:
            show_orders(found, TABLE_COLUMNS, "No orders in the workbook.")
        st.caption("Search filters this view. Saving still writes every order.")

    current = st.session_state.orders
    issues = validate(current)
    st.caption(f"{len(current)} rows in the workbook")
    if issues:
        st.warning("Fix these before saving:\n\n" + "\n".join(f"- {issue}" for issue in issues))

    save, download, reload = st.columns(3)
    if save.button("Save workbook", type="primary", width="stretch"):
        try:
            save_orders(current, DEFAULT_WORKBOOK)
        except ValueError as exc:
            st.error(str(exc))
        except PermissionError:
            st.error("Close the file in Excel, then save again.")
        else:
            st.success(f"Saved {len(current)} orders.")
    if issues:
        download.caption("Download is available after the rows pass validation.")
    else:
        download.download_button(
            "Download Excel",
            data=workbook_bytes(current),
            file_name="part_machining_orders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    if reload.button("Reload from disk", width="stretch"):
        st.session_state.orders = load_orders(DEFAULT_WORKBOOK)
        st.session_state.editor_version += 1
        st.rerun()


def customer_page(orders: pd.DataFrame, customer: str) -> None:
    frame = ready_orders(orders)
    frame = frame[frame["Customer"] == customer]
    metrics = st.columns(4)
    metrics[0].metric("Orders", f"{len(frame):,}")
    metrics[1].metric("Open", f"{(frame['Completed Status'] != 'Completed').sum():,}")
    metrics[2].metric("Closed", f"{(frame['Completed Status'] == 'Completed').sum():,}")
    metrics[3].metric("Aerospace", f"{(frame['Is Aerospace Order'] == 'Yes').sum():,}")
    found = apply_search(frame, f"search_customer_{customer}")
    if found is not None:
        show_orders(found.sort_values("Dispatch Date"), TABLE_COLUMNS, f"No orders for {customer}.")


def render_page(orders: pd.DataFrame) -> None:
    page = st.session_state.page
    frame = ready_orders(orders)
    if page == "Master table":
        st.subheader("Master table")
        editor_page(orders)
        return
    if page == "Dashboard":
        st.subheader("Dashboard")
        dashboard(orders)
        return
    if page == "Rejection data":
        st.subheader("Rejection data")
        st.caption("View only. Parts rejected inside the shop.")
        rejected = frame[frame["Internal Reject"]].sort_values("APM NO")
        found = apply_search(rejected, "search_rejection")
        if found is not None:
            show_orders(found, TABLE_COLUMNS, "No internally rejected parts.")
        return
    if page == "All open orders":
        st.subheader("All open orders")
        st.caption("View only. Orders whose completed status is not Completed.")
        opened = frame[frame["Completed Status"] != "Completed"].sort_values("Dispatch Date")
        found = apply_search(opened, "search_open")
        if found is not None:
            show_orders(found, TABLE_COLUMNS, "No open orders.")
        return
    if page == "All closed":
        st.subheader("All closed")
        st.caption("View only. Orders marked Completed by an elevated user.")
        closed = frame[frame["Completed Status"] == "Completed"].sort_values("PO Date", ascending=False)
        found = apply_search(closed, "search_closed")
        if found is not None:
            show_orders(found, TABLE_COLUMNS, "No closed orders.")
        return
    if page == "RMA orders":
        st.subheader("RMA orders")
        st.caption("View only. RMA Status is Yes when the customer rejected the part and it needs remanufacture.")
        rma = frame[frame["RMA Status"] == "Yes"].sort_values("APM NO")
        found = apply_search(rma, "search_rma")
        if found is not None:
            show_orders(found, TABLE_COLUMNS, "No customer RMA orders.")
        return
    if page == "Customer":
        customer = st.session_state.customer
        st.subheader(customer or "Customer")
        st.caption("View only. Orders for this customer.")
        if customer:
            customer_page(orders, customer)


def sidebar(orders: pd.DataFrame) -> None:
    with st.sidebar:
        brand_lockup(compact=True)
        title = USERS.get(st.session_state.get("username", ""), {}).get("title", "Planner")
        st.caption(f"Signed in as {st.session_state.get('username', '')} · {title}")
        st.markdown("**Menu**")
        for name in MENU:
            selected = st.session_state.page == name
            if st.button(
                name,
                key=f"nav-{name}",
                type="primary" if selected else "secondary",
                width="stretch",
            ) and not selected:
                st.session_state.page = name
                st.session_state.customer = None
                st.rerun()

        customers = sorted(
            {
                str(name).strip()
                for name in orders["Customer"]
                if str(name).strip() and str(name).strip().lower() != "nan"
            }
        )
        with st.expander("Customer wise", expanded=True):
            if not customers:
                st.caption("Customers appear after the master table has orders.")
            for name in customers:
                selected = st.session_state.page == "Customer" and st.session_state.customer == name
                if st.button(
                    name,
                    key=f"nav-customer-{name}",
                    type="primary" if selected else "secondary",
                    width="stretch",
                ) and not selected:
                    st.session_state.page = "Customer"
                    st.session_state.customer = name
                    st.rerun()

        st.divider()
        if st.button("Sign out", width="stretch"):
            st.session_state.authenticated = False
            st.rerun()


def main() -> None:
    if not st.session_state.get("authenticated"):
        login_page()
        return
    init_state()
    st.markdown(
        """
        <style>
        div[data-testid="stSidebar"] .stButton button {justify-content: flex-start;}
        div[data-testid="stSidebar"] .stButton button p {text-align: left; width: 100%;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    brand_lockup()
    st.markdown(
        "<div style='height:3px;background:linear-gradient(90deg,#C47B2B,#1F4E79);"
        "border-radius:2px;margin:0.2rem 0 1rem 0;'></div>",
        unsafe_allow_html=True,
    )
    if st.session_state.page == "Master table":
        render_page(st.session_state.orders)
        sidebar(st.session_state.orders)
    else:
        sidebar(st.session_state.orders)
        render_page(st.session_state.orders)


if __name__ == "__main__":
    main()
