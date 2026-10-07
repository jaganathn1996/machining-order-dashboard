"""Local machining-order app with a login screen and a left-hand menu."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from access import (
    GROUPS,
    add_user,
    authenticate,
    can_edit,
    can_view,
    delete_user,
    editable_columns,
    ensure_users,
    group_label,
    list_users,
    merge_edits,
    rights_rows,
    update_user,
    visible_columns,
)
from brand import COMPANY_NAME, LOGO_PATH, TAGLINE, ensure_logo
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
    validate,
    workbook_bytes,
)
from neon_store import load_order_frame, save_order_frame

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
    ensure_users()
    ensure_workbook(DEFAULT_WORKBOOK)
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    if "customer" not in st.session_state:
        st.session_state.customer = None
    current = st.session_state.get("orders")
    missing = current is None or any(column not in getattr(current, "columns", []) for column in EDITOR_COLUMNS)
    if missing:
        st.session_state.orders = load_order_frame()
        st.session_state.editor_version += 1


def current_group() -> str:
    return st.session_state.get("group", "")


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
    with st.expander("Sign in"):
        st.caption("Use the admin account stored in Neon. Department users are added from the Users page.")
    if submitted:
        username = username.strip()
        if username == "" or password == "":
            st.error("Enter a username and password.")
        else:
            record = authenticate(username, password)
            if record:
                st.session_state.authenticated = True
                st.session_state.username = record["username"]
                st.session_state.display_name = record["name"]
                st.session_state.group = record["group"]
                st.session_state.page = "Dashboard"
                st.session_state.orders = None
                st.rerun()
            else:
                st.error("Unknown username or password.")


def ready_orders(orders: pd.DataFrame) -> pd.DataFrame:
    return analysis_frame(orders, date.today())


def visible_orders(orders: pd.DataFrame) -> pd.DataFrame:
    frame = ready_orders(orders)
    hidden = [
        column
        for column in frame.columns
        if column in EDITOR_COLUMNS and not can_view_column(column)
    ]
    if hidden:
        frame = frame.drop(columns=hidden)
    return frame


def can_view_column(column: str) -> bool:
    return can_view(current_group(), column)


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


def column_config(group: str, images: bool) -> dict:
    def locked(column: str) -> bool:
        return not can_edit(group, column)

    if images:
        photo = st.column_config.ImageColumn("Part Photo", help="Part picture", width=120)
    else:
        photo = st.column_config.TextColumn(
            "Part Photo",
            help="Picture file kept with the row. The image shows when editing is off.",
            disabled=locked("Part Photo"),
            width="medium",
        )
    return {
        "APM NO": st.column_config.TextColumn(width=120, disabled=locked("APM NO")),
        "PO Date": st.column_config.DateColumn(format="YYYY-MM-DD", disabled=locked("PO Date"), width=120),
        "PO Number": st.column_config.TextColumn(width=120, disabled=locked("PO Number")),
        "Part Number": st.column_config.TextColumn(width=120, disabled=locked("Part Number")),
        "Part Photo": photo,
        "Qty": st.column_config.NumberColumn(min_value=1, step=1, format="%d", disabled=locked("Qty")),
        "Dispatch Date": st.column_config.DateColumn(format="YYYY-MM-DD", disabled=locked("Dispatch Date")),
        "Specification": st.column_config.TextColumn(width="large", disabled=locked("Specification")),
        "Risk": st.column_config.SelectboxColumn(
            options=RISKS, default="Medium", required=True, disabled=locked("Risk")
        ),
        "RM Size": st.column_config.TextColumn(width="medium", disabled=locked("RM Size")),
        "Action Qty": st.column_config.NumberColumn(
            min_value=0, step=1, format="%d", default=0, disabled=locked("Action Qty")
        ),
        "RM Status": st.column_config.TextColumn(width="large", disabled=locked("RM Status")),
        "Process": st.column_config.TextColumn(width="large", disabled=locked("Process")),
        "Tools & Accessories": st.column_config.TextColumn(
            width="medium", disabled=locked("Tools & Accessories")
        ),
        "Special Process & Instruments": st.column_config.TextColumn(
            width="medium", disabled=locked("Special Process & Instruments")
        ),
        "Inserts": st.column_config.TextColumn(width="small", disabled=locked("Inserts")),
        "Enquiry": st.column_config.TextColumn(width="large", disabled=locked("Enquiry")),
        "Program Status": st.column_config.SelectboxColumn(
            options=PROGRAM_STATUSES,
            default="Incomplete",
            required=True,
            disabled=locked("Program Status"),
        ),
        "Planning": st.column_config.TextColumn(
            width="large",
            disabled=locked("Planning"),
            help="Free text, for example In-house, Turning out, or Milling in-house completed.",
        ),
        "Machining Status": st.column_config.TextColumn(width="large", disabled=locked("Machining Status")),
        "Review": st.column_config.TextColumn(width="large", disabled=locked("Review")),
        "Deviation": st.column_config.TextColumn(width="large", disabled=locked("Deviation")),
        "Customer": st.column_config.TextColumn(disabled=locked("Customer")),
        "Completed Status": st.column_config.SelectboxColumn(
            options=COMPLETED_STATUSES,
            default="Not started",
            required=True,
            disabled=locked("Completed Status"),
            help="Only Admin can change the completion status.",
        ),
        "RMA Status": st.column_config.SelectboxColumn(
            options=YES_NO, default="No", required=True, disabled=locked("RMA Status")
        ),
        "Is Aerospace Order": st.column_config.SelectboxColumn(
            options=YES_NO, default="No", required=True, disabled=locked("Is Aerospace Order")
        ),
        "Cost": st.column_config.NumberColumn(
            min_value=0,
            step=0.01,
            format="%.2f",
            default=0,
            disabled=locked("Cost"),
            help="Visible to Admin only.",
        ),
    }


def show_orders(frame: pd.DataFrame, columns: list[str], empty: str) -> None:
    if frame.empty:
        st.info(empty)
        return
    columns = [column for column in columns if column in frame.columns and can_view_column(column)]
    view = present(frame, columns)
    st.dataframe(
        style_orders(view),
        hide_index=True,
        width="stretch",
        height=640,
        row_height=68,
        column_config=column_config(current_group(), images=True),
    )


def dashboard(orders: pd.DataFrame) -> None:
    frame = visible_orders(orders)
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


def editor_page(orders: pd.DataFrame) -> None:
    group = current_group()
    editable = editable_columns(group)
    shown = visible_columns(group)
    st.caption(
        "Dropdowns: Risk, Program Status, Completed Status, RMA Status, and Is Aerospace Order. "
        "Aerospace rows are light blue in the view. "
        f"{group_label(group)} can edit: {', '.join(editable)}."
    )
    editing = st.toggle("Edit master table", key="edit_master")
    if editing:
        edited = st.data_editor(
            for_editor(orders)[shown],
            num_rows="dynamic" if group == "Admin" else "fixed",
            hide_index=True,
            width="stretch",
            height=640,
            row_height=48,
            key=f"orders_editor_{st.session_state.username}_{st.session_state.editor_version}",
            column_order=shown,
            column_config=column_config(group, images=False),
        )
        st.session_state.orders = for_editor(merge_edits(edited, orders, group))
    else:
        visible = visible_orders(orders)
        found = apply_search(visible, "search_master")
        if found is not None:
            show_orders(found, shown, "No orders in the workbook.")
        st.caption("Search filters this view. Saving still writes every order, and locked columns stay unchanged.")

    current = st.session_state.orders
    issues = validate(current)
    st.caption(f"{len(current)} rows in the workbook")
    if issues:
        st.warning("Fix these before saving:\n\n" + "\n".join(f"- {issue}" for issue in issues))

    save, download, reload = st.columns(3)
    if save.button("Save workbook", type="primary", width="stretch"):
        try:
            save_order_frame(current)
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("Could not save orders to the database.")
        else:
            st.success(f"Saved {len(current)} orders.")
    if issues:
        download.caption("Download is available after the rows pass validation.")
    else:
        shown_download = visible_columns(current_group())
        try:
            payload = workbook_bytes(current, shown_download)
        except Exception as exc:
            download.error(f"Could not prepare the Excel file: {exc}")
        else:
            download.download_button(
                "Download Excel",
                data=payload,
                file_name="part_machining_orders.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
            if "Cost" not in shown_download:
                download.caption("Cost is left out of this download.")
    if reload.button("Reload", width="stretch"):
        st.session_state.orders = load_order_frame()
        st.session_state.editor_version += 1
        st.rerun()


def customer_page(orders: pd.DataFrame, customer: str) -> None:
    frame = visible_orders(orders)
    frame = frame[frame["Customer"] == customer]
    metrics = st.columns(4)
    metrics[0].metric("Orders", f"{len(frame):,}")
    metrics[1].metric("Open", f"{(frame['Completed Status'] != 'Completed').sum():,}")
    metrics[2].metric("Closed", f"{(frame['Completed Status'] == 'Completed').sum():,}")
    metrics[3].metric("Aerospace", f"{(frame['Is Aerospace Order'] == 'Yes').sum():,}")
    found = apply_search(frame, f"search_customer_{customer}")
    if found is not None:
        show_orders(found.sort_values("Dispatch Date"), TABLE_COLUMNS, f"No orders for {customer}.")


def users_page() -> None:
    st.subheader("Users")
    st.caption("Each person belongs to one department. Column rights follow that department.")
    records = list_users()
    st.dataframe(
        pd.DataFrame(records).rename(columns={"username": "Username", "name": "Name", "group": "Group"}),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Column access"):
        st.dataframe(pd.DataFrame(rights_rows()), hide_index=True, width="stretch")

    st.subheader("Add user")
    with st.form("add_user"):
        left, right = st.columns(2)
        username = left.text_input("Username")
        name = right.text_input("Name")
        left, right = st.columns(2)
        password = left.text_input("Password", type="password")
        group = right.selectbox("Group", GROUPS, format_func=group_label)
        if st.form_submit_button("Add user", type="primary"):
            try:
                add_user(username, name, password, group)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"Added {username.strip()}.")
                st.rerun()

    st.subheader("Update user")
    selected = st.selectbox("User", [record["username"] for record in records])
    record = next(item for item in records if item["username"] == selected)
    with st.form(f"edit_user_{selected}"):
        left, right = st.columns(2)
        name = left.text_input("Name", value=record["name"], key=f"edit_name_{selected}")
        group = right.selectbox(
            "Group",
            GROUPS,
            index=GROUPS.index(record["group"]),
            format_func=group_label,
            key=f"edit_group_{selected}",
        )
        password = st.text_input(
            "New password",
            type="password",
            key=f"edit_password_{selected}",
            help="Leave blank to keep the current password.",
        )
        if st.form_submit_button("Save user", type="primary"):
            try:
                updated = update_user(selected, name=name, group=group, password=password)
            except ValueError as exc:
                st.error(str(exc))
            else:
                if selected == st.session_state.get("username"):
                    st.session_state.display_name = updated["name"]
                    st.session_state.group = updated["group"]
                st.success(f"Updated {selected}.")
                st.rerun()
    confirm = st.checkbox(f"Delete {selected}", key=f"confirm_delete_{selected}")
    if st.button("Delete user", disabled=not confirm):
        try:
            delete_user(selected, actor=st.session_state.get("username", ""))
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Deleted {selected}.")
            st.rerun()


def render_page(orders: pd.DataFrame) -> None:
    page = st.session_state.page
    if page == "Users" and current_group() != "Admin":
        st.session_state.page = "Dashboard"
        st.rerun()
    frame = visible_orders(orders)
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
        st.caption("View only. Orders whose completed status is Completed.")
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
    if page == "Users":
        users_page()
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
        name = st.session_state.get("display_name") or st.session_state.get("username", "")
        st.caption(f"Signed in as {name} · {group_label(current_group())}")
        st.markdown("**Menu**")
        menu = list(MENU)
        if current_group() == "Admin":
            menu.insert(2, "Users")
        for name in menu:
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
            st.session_state.group = ""
            st.session_state.orders = None
            st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1
            st.rerun()


def main() -> None:
    ensure_users()
    if not st.session_state.get("authenticated") or not st.session_state.get("group"):
        st.session_state.authenticated = False
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
