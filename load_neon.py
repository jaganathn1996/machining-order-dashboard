"""Load the local workbook and part pictures into Neon.

Reads secrets from .env. Does not print them.
"""

from __future__ import annotations

import getpass
import hashlib
import os
import secrets
import sys
from io import BytesIO
from pathlib import Path

import boto3
import psycopg
from botocore.config import Config
from PIL import Image

from workbook import DEFAULT_WORKBOOK, load_orders

ROOT = Path(__file__).resolve().parent
BUCKET = "part-photos"


def load_env(path: Path) -> None:
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def object_key(photo: str) -> str:
    return f"parts/{Path(str(photo)).name}"


def png_bytes(relative: str) -> bytes:
    image = Image.open(ROOT / relative).convert("RGBA")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is empty in .env.")
    return value


def main() -> None:
    load_env(ROOT / ".env")
    frame = load_orders(DEFAULT_WORKBOOK)
    storage = boto3.client(
        "s3",
        endpoint_url=require("AWS_ENDPOINT_URL_S3"),
        aws_access_key_id=require("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=require("AWS_SECRET_ACCESS_KEY"),
        region_name=require("AWS_REGION"),
        config=Config(s3={"addressing_style": "path"}),
    )

    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    generated = False
    if not password and sys.stdin.isatty():
        password = getpass.getpass("New admin password: ")
        again = getpass.getpass("Repeat admin password: ")
        if password != again:
            raise SystemExit("Passwords did not match.")
    elif not password:
        password = secrets.token_urlsafe(12)
        generated = True
    if len(password) < 8:
        raise SystemExit("Admin password must be at least 8 characters.")

    uploaded: set[str] = set()
    missing: list[str] = []
    with psycopg.connect(require("DATABASE_URL")) as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE orders")
            for record in frame.to_dict("records"):
                photo = object_key(record["Part Photo"])
                local = ROOT / str(record["Part Photo"])
                if not local.is_file():
                    missing.append(str(record["Part Photo"]))
                elif photo not in uploaded:
                    storage.put_object(
                        Bucket=BUCKET,
                        Key=photo,
                        Body=png_bytes(str(record["Part Photo"])),
                        ContentType="image/png",
                    )
                    uploaded.add(photo)
                cursor.execute(
                    """
                    INSERT INTO orders (
                        apm_no, po_date, po_number, part_number, part_photo,
                        qty, dispatch_date, specification, risk, rm_size,
                        action_qty, rm_status, process, tools_accessories,
                        special_process, inserts, enquiry, program_status,
                        planning, machining_status, review, deviation, customer,
                        completed_status, rma_status, is_aerospace, cost
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    """,
                    (
                        record["APM NO"],
                        record["PO Date"].date(),
                        record["PO Number"],
                        record["Part Number"],
                        photo,
                        int(record["Qty"]),
                        record["Dispatch Date"].date(),
                        record["Specification"],
                        record["Risk"],
                        record["RM Size"],
                        int(record["Action Qty"]),
                        record["RM Status"],
                        record["Process"],
                        record["Tools & Accessories"],
                        record["Special Process & Instruments"],
                        record["Inserts"],
                        record["Enquiry"] or "",
                        record["Program Status"],
                        record["Planning"],
                        record["Machining Status"],
                        record["Review"] or "",
                        record["Deviation"] or "",
                        record["Customer"],
                        record["Completed Status"],
                        record["RMA Status"],
                        record["Is Aerospace Order"],
                        float(record["Cost"]),
                    ),
                )
            cursor.execute("DELETE FROM users WHERE username = %s", ("admin",))
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, display_name, department)
                VALUES (%s, %s, %s, %s)
                """,
                ("admin", password_hash(password), "Admin", "Admin"),
            )
            cursor.execute("SELECT COUNT(*) FROM orders")
            order_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
        connection.commit()
    print(f"Loaded {order_count} orders and {len(uploaded)} pictures.")
    print(f"Users in the database: {user_count}.")
    if generated:
        print(f"Admin username: admin")
        print(f"Admin password: {password}")
    if missing:
        print("Missing picture files:", ", ".join(missing))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        text = str(exc)
        for name in ("DATABASE_URL", "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID"):
            secret = os.environ.get(name, "")
            if secret:
                text = text.replace(secret, "[hidden]")
        print(text, file=sys.stderr)
        raise SystemExit(1) from None
