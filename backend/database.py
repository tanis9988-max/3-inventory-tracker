"""
database.py
-----------
Small helper module that wraps the sqlite3 connection and holds the
table definitions. Nothing fancy here - no ORM, just plain SQL because
for a project this size an ORM felt like overkill and I wanted to
actually understand the queries I was writing.

Run this file directly to (re)create an empty database:
    python database.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # enforce foreign keys, sqlite has this off by default which trips
    # people up all the time
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    color       TEXT NOT NULL,
    icon        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL,              -- 'owner' or 'manager'
    company_id      INTEGER,                    -- NULL for owner (access to all)
    full_name       TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL,
    product_code    TEXT NOT NULL,
    name            TEXT NOT NULL,
    purchase_price  REAL NOT NULL DEFAULT 0,
    selling_price   REAL NOT NULL DEFAULT 0,
    quantity        INTEGER NOT NULL DEFAULT 0,
    image_url       TEXT,
    last_updated    TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    quantity        INTEGER NOT NULL,
    cost            REAL NOT NULL,
    purchase_date   TEXT NOT NULL,
    created_by      TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    quantity        INTEGER NOT NULL,
    selling_price   REAL NOT NULL,
    invoice_number  TEXT NOT NULL,
    customer_name   TEXT,
    sale_date       TEXT NOT NULL,
    created_by      TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER,
    username    TEXT NOT NULL,
    action      TEXT NOT NULL,
    details     TEXT,
    timestamp   TEXT NOT NULL
);
"""

if __name__ == "__main__":
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print("Schema created at", DB_PATH)
