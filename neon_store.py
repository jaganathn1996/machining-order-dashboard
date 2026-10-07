"""Neon orders, users, and part-photo storage."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
import psycopg
from botocore.config import Config
from botocore.exceptions import ClientError

from workbook import for_editor, to_export_frame

ROOT = Path(__file__).resolve().parent
BUCKET = "part-photos"
SECRET_KEYS = (
    "DATABASE_URL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ENDPOINT_URL_S3",
    "AWS_REGION",
)
FIELDS = [
    ("apm_no", "APM NO"),
    ("po_date", "PO Date"),
    ("po_number", "PO Number"),
    ("part_number", "Part Number"),
    ("part_photo", "Part Photo"),
    ("qty", "Qty"),
    ("dispatch_date", "Dispatch Date"),
    ("specification", "Specification"),
    ("risk", "Risk"),
    ("rm_size", "RM Size"),
    ("action_qty", "Action Qty"),
    ("rm_status", "RM Status"),
    ("process", "Process"),
    ("tools_accessories", "Tools & Accessories"),
    ("special_process", "Special Process & Instruments"),
    ("inserts", "Inserts"),
    ("enquiry", "Enquiry"),
    ("program_status", "Program Status"),
    ("planning", "Planning"),
    ("machining_status", "Machining Status"),
    ("review", "Review"),
    ("deviation", "Deviation"),
    ("customer", "Customer"),
    ("completed_status", "Completed Status"),
    ("rma_status", "RMA Status"),
    ("is_aerospace", "Is Aerospace Order"),
    ("cost", "Cost"),
]


def load_config() -> None:
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))
    try:
        import streamlit as st

        for key in SECRET_KEYS:
            if key in st.secrets and not os.environ.get(key):
                os.environ[key] = str(st.secrets[key])
    except Exception:
        pass


def setting(name: str) -> str:
    load_config()
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set.")
    return value


def connect() -> psycopg.Connection:
    return psycopg.connect(setting("DATABASE_URL"))


def storage_client():
    return boto3.client(
        "s3",
        endpoint_url=setting("AWS_ENDPOINT_URL_S3"),
        aws_access_key_id=setting("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=setting("AWS_SECRET_ACCESS_KEY"),
        region_name=setting("AWS_REGION"),
        config=Config(s3={"addressing_style": "path"}),
    )


def storage_key(photo: object) -> str:
    name = Path(str(photo or "")).name
    if name in {"", "nan", "None"}:
        return ""
    return f"parts/{name}"


def bucket_bytes(key: str) -> bytes:
    if not key:
        return b""
    try:
        response = storage_client().get_object(Bucket=BUCKET, Key=key)
    except ClientError:
        return b""
    return response["Body"].read()


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt, digest = stored.split("$")
        rounds_int = int(rounds)
    except (ValueError, AttributeError):
        return False
    if scheme != "pbkdf2_sha256":
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds_int).hex()
    return secrets.compare_digest(check, digest)


def _sql_value(display: str, value: object) -> object:
    if display == "Part Photo":
        return storage_key(value)
    if display in {"PO Date", "Dispatch Date"} and isinstance(value, datetime):
        return value.date()
    if display in {"Qty", "Action Qty"}:
        return int(round(float(value)))
    if display == "Cost":
        return float(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return value


def load_order_frame() -> pd.DataFrame:
    columns = ", ".join(sql for sql, _display in FIELDS)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {columns} FROM orders ORDER BY apm_no")
            rows = cursor.fetchall()
    frame = pd.DataFrame(rows, columns=[display for _sql, display in FIELDS])
    return for_editor(frame)


def save_order_frame(frame: pd.DataFrame) -> None:
    export = to_export_frame(frame)
    rows = [
        tuple(_sql_value(display, record[display]) for _sql, display in FIELDS)
        for record in export.to_dict("records")
    ]
    placeholders = ", ".join(["%s"] * len(FIELDS))
    column_list = ", ".join(sql for sql, _display in FIELDS)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE orders")
            if rows:
                cursor.executemany(
                    f"INSERT INTO orders ({column_list}) VALUES ({placeholders})",
                    rows,
                )
        connection.commit()


def fetch_users() -> list[dict]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT username, display_name, department, password_hash
                FROM users
                ORDER BY username
                """
            )
            rows = cursor.fetchall()
    return [
        {
            "username": username,
            "name": name,
            "group": department,
            "password_hash": stored_hash,
        }
        for username, name, department, stored_hash in rows
    ]
