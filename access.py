"""Department groups, column rights, and the local user list."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from neon_store import connect, fetch_users, password_hash, password_matches
from workbook import EDITOR_COLUMNS

GROUPS = [
    "Quality",
    "Production",
    "Purchase",
    "PPC",
    "Tool room",
    "Engineering",
    "NPD",
    "Admin",
    "In process QC",
]
GROUP_NOTES = {
    "PPC": "PPC (production planning and control)",
    "NPD": "NPD (new product development)",
}

# None means every group. Otherwise the named groups, and Admin is included explicitly.
COLUMN_EDIT: dict[str, frozenset[str] | None] = {
    "APM NO": frozenset({"Admin"}),
    "PO Date": frozenset({"Admin"}),
    "PO Number": frozenset({"Admin"}),
    "Part Number": frozenset({"Admin"}),
    "Part Photo": frozenset({"Admin"}),
    "Qty": frozenset({"Admin"}),
    "Dispatch Date": frozenset({"Admin"}),
    "Specification": frozenset({"Admin"}),
    "Risk": frozenset({"Admin"}),
    "RM Size": frozenset({"Admin", "Engineering"}),
    "Action Qty": frozenset({"Admin", "Engineering"}),
    "RM Status": frozenset({"Admin", "Purchase"}),
    "Process": frozenset({"Admin", "Engineering"}),
    "Tools & Accessories": frozenset({"Admin", "Tool room"}),
    "Special Process & Instruments": frozenset({"Admin", "Quality"}),
    "Inserts": frozenset({"Admin", "Tool room", "Quality"}),
    "Enquiry": frozenset({"Admin", "Engineering"}),
    "Program Status": frozenset({"Admin", "Engineering"}),
    "Planning": frozenset({"Admin", "PPC"}),
    "Machining Status": frozenset({"Admin", "PPC"}),
    "Review": None,
    "Deviation": None,
    "Customer": frozenset({"Admin"}),
    "Completed Status": frozenset({"Admin"}),
    "RMA Status": frozenset({"Admin"}),
    "Is Aerospace Order": frozenset({"Admin"}),
    "Cost": frozenset({"Admin"}),
}
COLUMN_VIEW: dict[str, frozenset[str] | None] = {
    "Cost": frozenset({"Admin"}),
}

_MISSING_RIGHTS = [column for column in EDITOR_COLUMNS if column not in COLUMN_EDIT]
if _MISSING_RIGHTS:
    raise RuntimeError("Missing column rights: " + ", ".join(_MISSING_RIGHTS))

ROOT = Path(__file__).resolve().parent
USERS_PATH = ROOT / "data" / "users.json"
SEED_USERS = [
    {"username": "admin", "password": "admin", "group": "Admin", "name": "Admin"},
    {"username": "quality", "password": "quality", "group": "Quality", "name": "Quality"},
    {"username": "production", "password": "production", "group": "Production", "name": "Production"},
    {"username": "purchase", "password": "purchase", "group": "Purchase", "name": "Purchase"},
    {"username": "ppc", "password": "ppc", "group": "PPC", "name": "PPC"},
    {"username": "toolroom", "password": "toolroom", "group": "Tool room", "name": "Tool room"},
    {"username": "engineering", "password": "engineering", "group": "Engineering", "name": "Engineering"},
    {"username": "npd", "password": "npd", "group": "NPD", "name": "NPD"},
    {"username": "ipqc", "password": "ipqc", "group": "In process QC", "name": "In process QC"},
]


def group_label(group: str) -> str:
    return GROUP_NOTES.get(group, group)


def can_view(group: str, column: str) -> bool:
    allowed = COLUMN_VIEW.get(column)
    return allowed is None or group in allowed


def can_edit(group: str, column: str) -> bool:
    if not can_view(group, column):
        return False
    allowed = COLUMN_EDIT[column]
    return allowed is None or group in allowed


def visible_columns(group: str, columns: list[str] | None = None) -> list[str]:
    source = columns if columns is not None else EDITOR_COLUMNS
    return [column for column in source if can_view(group, column)]


def editable_columns(group: str, columns: list[str] | None = None) -> list[str]:
    source = columns if columns is not None else EDITOR_COLUMNS
    return [column for column in source if can_edit(group, column)]


def rights_rows() -> list[dict[str, str]]:
    rows = []
    for column in EDITOR_COLUMNS:
        view = COLUMN_VIEW.get(column)
        edit = COLUMN_EDIT[column]
        rows.append(
            {
                "Column": column,
                "View": "All" if view is None else _join_groups(view),
                "Edit": "All" if edit is None else _join_groups(edit),
            }
        )
    return rows


def _join_groups(allowed: frozenset[str]) -> str:
    ordered = ["Admin", *[group for group in GROUPS if group != "Admin"]]
    return " or ".join(group for group in ordered if group in allowed)


def merge_edits(edited: pd.DataFrame, previous: pd.DataFrame, group: str) -> pd.DataFrame:
    """Keep columns this group cannot edit, including columns they cannot see."""
    previous = previous.reset_index(drop=True)
    edited = edited.reset_index(drop=True)
    if group != "Admin":
        if len(edited) != len(previous):
            return previous.copy()
        out = previous.copy()
        for column in editable_columns(group):
            if column in edited.columns:
                out[column] = edited[column].to_numpy()
        return out
    if len(edited) == len(previous):
        out = previous.copy()
        for column in edited.columns:
            if column in out.columns:
                out[column] = edited[column].to_numpy()
        return out
    out = edited.copy()
    for column in previous.columns:
        if column not in out.columns:
            out[column] = pd.NA
    return out


def ensure_users(path: Path = USERS_PATH) -> list[dict]:
    return list_users()


def list_users(path: Path = USERS_PATH) -> list[dict]:
    order = {group: index for index, group in enumerate(GROUPS)}
    public = [_public(user) for user in fetch_users()]
    return sorted(public, key=lambda user: (order.get(user["group"], 99), user["username"]))


def authenticate(username: str, password: str, path: Path = USERS_PATH) -> dict | None:
    username = username.strip()
    for user in fetch_users():
        if user["username"] == username and password_matches(password, user["password_hash"]):
            return _public(user)
    return None


def add_user(
    username: str,
    name: str,
    password: str,
    group: str,
    path: Path = USERS_PATH,
) -> dict:
    username = _clean_username(username)
    password = _clean_password(password, required=True)
    group = _clean_group(group)
    users = fetch_users()
    if any(user["username"].casefold() == username.casefold() for user in users):
        raise ValueError(f"{username} already exists.")
    record = {
        "username": username,
        "name": _clean_name(name, username),
        "group": group,
    }
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, display_name, department)
                VALUES (%s, %s, %s, %s)
                """,
                (record["username"], password_hash(password), record["name"], record["group"]),
            )
        connection.commit()
    return record


def update_user(
    username: str,
    *,
    name: str,
    group: str,
    password: str = "",
    path: Path = USERS_PATH,
) -> dict:
    users = fetch_users()
    record = _find(users, username)
    group = _clean_group(group)
    _keep_an_admin(users, record, group)
    record["name"] = _clean_name(name, record["username"])
    record["group"] = group
    with connect() as connection:
        with connection.cursor() as cursor:
            if password != "":
                password = _clean_password(password, required=True)
                cursor.execute(
                    """
                    UPDATE users
                    SET display_name = %s, department = %s, password_hash = %s
                    WHERE username = %s
                    """,
                    (record["name"], record["group"], password_hash(password), record["username"]),
                )
            else:
                cursor.execute(
                    """
                    UPDATE users
                    SET display_name = %s, department = %s
                    WHERE username = %s
                    """,
                    (record["name"], record["group"], record["username"]),
                )
        connection.commit()
    return _public(record)


def delete_user(username: str, *, actor: str, path: Path = USERS_PATH) -> None:
    users = fetch_users()
    record = _find(users, username)
    if record["username"] == actor:
        raise ValueError("You cannot delete the account you are signed in with.")
    if record["group"] == "Admin" and _admin_count(users) <= 1:
        raise ValueError("Keep at least one Admin user.")
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE username = %s", (record["username"],))
        connection.commit()


def _public(user: dict) -> dict:
    return {"username": user["username"], "name": user["name"], "group": user["group"]}


def _find(users: list[dict], username: str) -> dict:
    for user in users:
        if user["username"] == username:
            return user
    raise ValueError(f"No user named {username}.")


def _admin_count(users: list[dict]) -> int:
    return sum(1 for user in users if user["group"] == "Admin")


def _keep_an_admin(users: list[dict], record: dict, new_group: str) -> None:
    if record["group"] == "Admin" and new_group != "Admin" and _admin_count(users) <= 1:
        raise ValueError("Keep at least one Admin user.")


def _clean_username(username: str) -> str:
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{2,40}", username):
        raise ValueError(
            "Username must be 2-40 characters: letters, numbers, dots, underscores, or hyphens."
        )
    return username


def _clean_password(password: str, *, required: bool) -> str:
    if password == "" and not required:
        return ""
    if len(password) < 3:
        raise ValueError("Password must be at least 3 characters.")
    return password


def _clean_name(name: str, username: str) -> str:
    name = name.strip() or username
    if len(name) > 80:
        raise ValueError("Name must be 80 characters or fewer.")
    return name


def _clean_group(group: str) -> str:
    if group not in GROUPS:
        raise ValueError("Choose a group from the list.")
    return group


def _read_users(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
        users = payload["users"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"Could not read {path.name}.") from exc
    if not isinstance(users, list) or not users:
        raise ValueError(f"{path.name} has no users.")
    cleaned = []
    for user in users:
        record = {
            "username": _clean_username(str(user.get("username", ""))),
            "password": _clean_password(str(user.get("password", "")), required=True),
            "group": _clean_group(str(user.get("group", ""))),
            "name": _clean_name(str(user.get("name", "")), str(user.get("username", ""))),
        }
        cleaned.append(record)
    folded = [user["username"].casefold() for user in cleaned]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{path.name} has duplicate usernames.")
    if _admin_count(cleaned) < 1:
        raise ValueError(f"{path.name} needs an Admin user.")
    return cleaned


def _write_users(users: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"users": users}
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)
