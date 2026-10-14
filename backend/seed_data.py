"""
seed_data.py
------------
Wipes and repopulates the database with sample data for the three
companies. Kept the numbers small (10 products each, a few
purchases/sales) since this is just for demoing the app.

Usage:
    python seed_data.py
"""

import datetime
import random
from werkzeug.security import generate_password_hash

from database import get_db, SCHEMA

random.seed(42)


def img(seed):
    return f"https://picsum.photos/seed/{seed}/400/300"


COMPANIES = [
    {"name": "Car Factory", "slug": "car", "color": "#2563eb", "icon": "car"},
    {"name": "Stationery Store", "slug": "station", "color": "#16a34a", "icon": "pencil"},
    {"name": "Supermarket", "slug": "market", "color": "#ea580c", "icon": "shopping-cart"},
]

USERS = [
    {"username": "owner", "password": "owner123", "role": "owner", "company": None, "full_name": "Tanish Sharma"},
    {"username": "caradmin", "password": "car123", "role": "manager", "company": "car", "full_name": "Mohan"},
    {"username": "stationadmin", "password": "station123", "role": "manager", "company": "station", "full_name": "Rajesh"},
    {"username": "marketadmin", "password": "market123", "role": "manager", "company": "market", "full_name": "Ramesh"},
]

# (name, purchase_price, selling_price, quantity)
PRODUCTS = {
    "car": [
        ("Car Engine", 45000, 58000, 8),
        ("Alloy Wheels", 6500, 8900, 24),
        ("Car Battery", 3200, 4500, 6),
        ("Gearbox", 21000, 27500, 5),
        ("Steering Wheel", 2800, 3900, 18),
        ("Car Seats", 5200, 7200, 14),
        ("Brake Pads", 950, 1450, 60),
        ("Headlights", 1800, 2600, 30),
        ("Windshield", 4200, 5800, 9),
        ("Fuel Tank", 3600, 4900, 12),
    ],
    "station": [
        ("Ball Pen", 3, 8, 500),
        ("Notebook", 18, 35, 240),
        ("Pencil", 2, 5, 600),
        ("Marker", 12, 22, 150),
        ("Stapler", 45, 75, 40),
        ("A4 Paper Pack", 180, 240, 8),
        ("Eraser", 3, 7, 320),
        ("Glue Stick", 15, 28, 90),
        ("Geometry Box", 60, 95, 55),
        ("Highlighter", 20, 35, 7),
    ],
    "market": [
        ("Rice (5kg)", 220, 280, 70),
        ("Wheat Flour (5kg)", 180, 230, 65),
        ("Milk (1L)", 28, 34, 120),
        ("Cooking Oil (1L)", 130, 165, 45),
        ("Sugar (1kg)", 38, 48, 90),
        ("Tea (250g)", 90, 120, 55),
        ("Soap", 25, 38, 200),
        ("Shampoo (200ml)", 95, 140, 6),
        ("Biscuits (pack)", 18, 28, 300),
        ("Eggs (dozen)", 65, 82, 9),
    ],
}


def run():
    conn = get_db()
    conn.executescript(SCHEMA)

    for table in ["activity_logs", "sales", "purchases", "products", "users", "companies"]:
        conn.execute(f"DELETE FROM {table}")

    cur = conn.cursor()

    company_ids = {}
    for c in COMPANIES:
        cur.execute(
            "INSERT INTO companies (name, slug, color, icon) VALUES (?, ?, ?, ?)",
            (c["name"], c["slug"], c["color"], c["icon"]),
        )
        company_ids[c["slug"]] = cur.lastrowid

    for u in USERS:
        cid = company_ids[u["company"]] if u["company"] else None
        cur.execute(
            "INSERT INTO users (username, password_hash, role, company_id, full_name) VALUES (?, ?, ?, ?, ?)",
            (u["username"], generate_password_hash(u["password"]), u["role"], cid, u["full_name"]),
        )

    now = datetime.datetime.now()
    product_ids = {}
    for slug, items in PRODUCTS.items():
        product_ids[slug] = []
        for idx, (name, pcost, sprice, qty) in enumerate(items, start=1):
            code = f"{slug.upper()}-{idx:03d}"
            cur.execute(
                """INSERT INTO products
                   (company_id, product_code, name, purchase_price, selling_price, quantity, image_url, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company_ids[slug], code, name, pcost, sprice, qty,
                    img(f"{slug}-{name.split(' ')[0]}"),
                    now.strftime("%Y-%m-%d %H:%M"),
                ),
            )
            product_ids[slug].append(cur.lastrowid)

    usernames_by_slug = {"car": "caradmin", "station": "stationadmin", "market": "marketadmin"}
    for slug, pids in product_ids.items():
        for i in range(6):
            days_ago = random.randint(1, 60)
            pdate = (now - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")
            pid = random.choice(pids)
            qty = random.randint(5, 40)
            unit_cost = cur.execute("SELECT purchase_price FROM products WHERE id=?", (pid,)).fetchone()["purchase_price"]
            cur.execute(
                """INSERT INTO purchases (company_id, product_id, quantity, cost, purchase_date, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (company_ids[slug], pid, qty, round(unit_cost * qty, 2), pdate, usernames_by_slug[slug]),
            )

        for i in range(8):
            days_ago = random.randint(1, 45)
            sdate = (now - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")
            pid = random.choice(pids)
            sp = cur.execute("SELECT selling_price FROM products WHERE id=?", (pid,)).fetchone()["selling_price"]
            qty = random.randint(1, 10)
            invoice = f"INV-{slug.upper()}-{1000 + i}"
            cur.execute(
                """INSERT INTO sales (company_id, product_id, quantity, selling_price, invoice_number, customer_name, sale_date, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (company_ids[slug], pid, qty, sp, invoice, random.choice(["Walk-in Customer", "Ramesh Traders", "City Mart", "Local Buyer"]), sdate, usernames_by_slug[slug]),
            )

        cur.execute(
            "INSERT INTO activity_logs (company_id, username, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (company_ids[slug], usernames_by_slug[slug], "Login", "Manager logged in", now.strftime("%Y-%m-%d %H:%M:%S")),
        )

    cur.execute(
        "INSERT INTO activity_logs (company_id, username, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
        (None, "owner", "Login", "Owner logged in", now.strftime("%Y-%m-%d %H:%M:%S")),
    )

    conn.commit()
    conn.close()
    print("Database seeded - 3 companies, 4 users, 30 products.")


if __name__ == "__main__":
    run()
