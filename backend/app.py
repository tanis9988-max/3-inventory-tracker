"""
app.py
------
Main Flask entry point. Handles auth (JWT), and the REST endpoints
for products / purchases / sales / reports / activity log. Also
serves the static frontend so you only need to run one server.

Run with:
    python app.py
Then open http://localhost:5000 in your browser.
"""

import csv
import datetime
import functools
import io
import os

import jwt
from flask import Flask, request, jsonify, g, send_from_directory, Response
from werkzeug.security import check_password_hash

from database import get_db, SCHEMA

app = Flask(__name__, static_folder=None)

SECRET_KEY = os.environ.get("SECRET_KEY", "campus-inventory-secret-key-change-me")
TOKEN_EXPIRY_HOURS = 8

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

LOW_STOCK_THRESHOLD = 10


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_token(user_row):
    payload = {
        "user_id": user_row["id"],
        "username": user_row["username"],
        "role": user_row["role"],
        "company_id": user_row["company_id"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def log_activity(company_id, username, action, details=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO activity_logs (company_id, username, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
        (company_id, username, action, details, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired, please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        g.user = payload
        return f(*args, **kwargs)
    return wrapper


def check_company_access(company_id):
    if g.user["role"] == "owner":
        return True
    return g.user["company_id"] == company_id


def company_or_403():
    company_id = request.args.get("company_id") or (request.json.get("company_id") if request.is_json else None)
    if company_id is None:
        return None, (jsonify({"error": "company_id is required"}), 400)
    company_id = int(company_id)
    if not check_company_access(company_id):
        return None, (jsonify({"error": "You do not have access to this company"}), 403)
    return company_id, None


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    company_slug = (data.get("company") or "").strip().lower()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password or not company_slug:
        return jsonify({"error": "Company, username and password are all required"}), 400

    conn = get_db()

    if company_slug == "owner":
        user = conn.execute("SELECT * FROM users WHERE username=? AND role='owner'", (username,)).fetchone()
    else:
        company = conn.execute("SELECT * FROM companies WHERE slug=?", (company_slug,)).fetchone()
        if not company:
            conn.close()
            return jsonify({"error": "Company not found"}), 404
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND company_id=? AND role='manager'",
            (username, company["id"]),
        ).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        conn.close()
        return jsonify({"error": "Invalid credentials"}), 401

    token = make_token(user)
    log_activity(user["company_id"], user["username"], "Login")

    result = {
        "token": token,
        "role": user["role"],
        "username": user["username"],
        "full_name": user["full_name"],
        "company_id": user["company_id"],
    }
    conn.close()
    return jsonify(result)


@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    log_activity(g.user["company_id"], g.user["username"], "Logout")
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# companies
# ---------------------------------------------------------------------------

@app.route("/api/companies", methods=["GET"])
@login_required
def list_companies():
    conn = get_db()
    rows = conn.execute("SELECT * FROM companies").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@app.route("/api/dashboard/owner", methods=["GET"])
@login_required
def owner_dashboard():
    if g.user["role"] != "owner":
        return jsonify({"error": "Owner only"}), 403
    conn = get_db()
    companies = conn.execute("SELECT * FROM companies").fetchall()

    total_products = conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
    total_value = conn.execute("SELECT COALESCE(SUM(selling_price * quantity), 0) v FROM products").fetchone()["v"]
    low_stock = conn.execute("SELECT COUNT(*) c FROM products WHERE quantity < ?", (LOW_STOCK_THRESHOLD,)).fetchone()["c"]

    per_company = []
    for c in companies:
        p_count = conn.execute("SELECT COUNT(*) c FROM products WHERE company_id=?", (c["id"],)).fetchone()["c"]
        value = conn.execute("SELECT COALESCE(SUM(selling_price * quantity), 0) v FROM products WHERE company_id=?", (c["id"],)).fetchone()["v"]
        per_company.append({**dict(c), "product_count": p_count, "inventory_value": value})

    conn.close()
    return jsonify({
        "total_companies": len(companies),
        "total_products": total_products,
        "total_inventory_value": total_value,
        "total_low_stock": low_stock,
        "companies": per_company,
    })


@app.route("/api/dashboard/company", methods=["GET"])
@login_required
def company_dashboard():
    company_id, err = company_or_403()
    if err:
        return err
    conn = get_db()

    total_products = conn.execute("SELECT COUNT(*) c FROM products WHERE company_id=?", (company_id,)).fetchone()["c"]
    low_stock = conn.execute("SELECT COUNT(*) c FROM products WHERE company_id=? AND quantity < ?", (company_id, LOW_STOCK_THRESHOLD)).fetchone()["c"]
    inventory_value = conn.execute("SELECT COALESCE(SUM(selling_price * quantity), 0) v FROM products WHERE company_id=?", (company_id,)).fetchone()["v"]

    sales_total = conn.execute("SELECT COALESCE(SUM(selling_price * quantity), 0) v, COUNT(*) c FROM sales WHERE company_id=?", (company_id,)).fetchone()
    purchases_total = conn.execute("SELECT COALESCE(SUM(cost), 0) v, COUNT(*) c FROM purchases WHERE company_id=?", (company_id,)).fetchone()

    recent = conn.execute(
        "SELECT * FROM activity_logs WHERE company_id=? ORDER BY id DESC LIMIT 8", (company_id,)
    ).fetchall()

    monthly_sales = conn.execute(
        """SELECT strftime('%Y-%m', sale_date) month, SUM(selling_price*quantity) total
           FROM sales WHERE company_id=? GROUP BY month ORDER BY month DESC LIMIT 6""",
        (company_id,),
    ).fetchall()
    monthly_purchases = conn.execute(
        """SELECT strftime('%Y-%m', purchase_date) month, SUM(cost) total
           FROM purchases WHERE company_id=? GROUP BY month ORDER BY month DESC LIMIT 6""",
        (company_id,),
    ).fetchall()

    conn.close()
    return jsonify({
        "total_products": total_products,
        "low_stock": low_stock,
        "inventory_value": inventory_value,
        "sales_summary": {"total": sales_total["v"], "count": sales_total["c"]},
        "purchase_summary": {"total": purchases_total["v"], "count": purchases_total["c"]},
        "recent_activity": [dict(r) for r in recent],
        "monthly_sales": [dict(r) for r in reversed(monthly_sales)],
        "monthly_purchases": [dict(r) for r in reversed(monthly_purchases)],
    })


# ---------------------------------------------------------------------------
# products / inventory
# ---------------------------------------------------------------------------

def product_to_dict(row):
    d = dict(row)
    d["low_stock"] = d["quantity"] < LOW_STOCK_THRESHOLD
    return d


@app.route("/api/products", methods=["GET"])
@login_required
def get_products():
    company_id, err = company_or_403()
    if err:
        return err

    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "name")
    sort_dir = "DESC" if request.args.get("sort_dir") == "desc" else "ASC"

    allowed_sort_cols = {"name", "quantity", "selling_price", "purchase_price", "last_updated"}
    if sort_by not in allowed_sort_cols:
        sort_by = "name"

    query = "SELECT * FROM products WHERE company_id = ?"
    params = [company_id]

    if search:
        query += " AND (name LIKE ? OR product_code LIKE ?)"
        like = f"%{search}%"
        params += [like, like]

    query += f" ORDER BY {sort_by} {sort_dir}"

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([product_to_dict(r) for r in rows])


@app.route("/api/products/<int:product_id>", methods=["GET"])
@login_required
def get_product(product_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    if not check_company_access(row["company_id"]):
        return jsonify({"error": "Access denied"}), 403
    return jsonify(product_to_dict(row))


@app.route("/api/products", methods=["POST"])
@login_required
def add_product():
    company_id, err = company_or_403()
    if err:
        return err
    d = request.json
    required = ["name", "purchase_price", "selling_price", "quantity"]
    for field in required:
        if field not in d or d[field] in (None, ""):
            return jsonify({"error": f"'{field}' is required"}), 400

    conn = get_db()
    company = conn.execute("SELECT slug FROM companies WHERE id=?", (company_id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) c FROM products WHERE company_id=?", (company_id,)).fetchone()["c"]
    code = d.get("product_code") or f"{company['slug'].upper()}-{count + 1:03d}"

    cur = conn.execute(
        """INSERT INTO products
           (company_id, product_code, name, purchase_price, selling_price, quantity, image_url, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            company_id, code, d["name"],
            float(d["purchase_price"]), float(d["selling_price"]), int(d["quantity"]),
            d.get("image_url") or f"https://picsum.photos/seed/{code}/400/300",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    log_activity(company_id, g.user["username"], "Added Product", d["name"])
    return jsonify({"id": new_id, "product_code": code}), 201


@app.route("/api/products/<int:product_id>", methods=["PUT"])
@login_required
def update_product(product_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    if not check_company_access(row["company_id"]):
        conn.close()
        return jsonify({"error": "Access denied"}), 403

    d = request.json
    fields = ["name", "purchase_price", "selling_price", "quantity", "image_url"]
    updates = {f: d[f] for f in fields if f in d}
    if not updates:
        conn.close()
        return jsonify({"error": "Nothing to update"}), 400

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), product_id]
    conn.execute(f"UPDATE products SET {set_clause}, last_updated=? WHERE id=?", values)
    conn.commit()
    conn.close()
    log_activity(row["company_id"], g.user["username"], "Updated Product", row["name"])
    return jsonify({"ok": True})


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
@login_required
def delete_product(product_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    if not check_company_access(row["company_id"]):
        conn.close()
        return jsonify({"error": "Access denied"}), 403
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    log_activity(row["company_id"], g.user["username"], "Deleted Product", row["name"])
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# purchases  (adds stock)
# ---------------------------------------------------------------------------

@app.route("/api/purchases", methods=["GET"])
@login_required
def get_purchases():
    company_id, err = company_or_403()
    if err:
        return err
    conn = get_db()
    rows = conn.execute(
        """SELECT pu.*, p.name as product_name
           FROM purchases pu
           LEFT JOIN products p ON pu.product_id = p.id
           WHERE pu.company_id=? ORDER BY pu.purchase_date DESC, pu.id DESC""",
        (company_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/purchases", methods=["POST"])
@login_required
def add_purchase():
    company_id, err = company_or_403()
    if err:
        return err
    d = request.json
    for field in ["product_id", "quantity", "cost"]:
        if field not in d or d[field] in (None, ""):
            return jsonify({"error": f"'{field}' is required"}), 400

    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id=? AND company_id=?", (d["product_id"], company_id)).fetchone()
    if not product:
        conn.close()
        return jsonify({"error": "Product not found in this company"}), 404

    purchase_date = d.get("purchase_date") or datetime.date.today().isoformat()
    cur = conn.execute(
        """INSERT INTO purchases (company_id, product_id, quantity, cost, purchase_date, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (company_id, d["product_id"], int(d["quantity"]), float(d["cost"]), purchase_date, g.user["username"]),
    )
    conn.execute(
        "UPDATE products SET quantity = quantity + ?, last_updated=? WHERE id=?",
        (int(d["quantity"]), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), d["product_id"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    log_activity(company_id, g.user["username"], "Purchase Created", f"{product['name']} x{d['quantity']}")
    return jsonify({"id": new_id}), 201


# ---------------------------------------------------------------------------
# sales  (removes stock)
# ---------------------------------------------------------------------------

@app.route("/api/sales", methods=["GET"])
@login_required
def get_sales():
    company_id, err = company_or_403()
    if err:
        return err
    conn = get_db()
    rows = conn.execute(
        """SELECT sa.*, p.name as product_name
           FROM sales sa LEFT JOIN products p ON sa.product_id = p.id
           WHERE sa.company_id=? ORDER BY sa.sale_date DESC, sa.id DESC""",
        (company_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/sales", methods=["POST"])
@login_required
def add_sale():
    company_id, err = company_or_403()
    if err:
        return err
    d = request.json
    for field in ["product_id", "quantity", "selling_price", "invoice_number"]:
        if field not in d or d[field] in (None, ""):
            return jsonify({"error": f"'{field}' is required"}), 400

    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id=? AND company_id=?", (d["product_id"], company_id)).fetchone()
    if not product:
        conn.close()
        return jsonify({"error": "Product not found in this company"}), 404

    qty = int(d["quantity"])
    if qty > product["quantity"]:
        conn.close()
        return jsonify({"error": f"Not enough stock. Only {product['quantity']} left."}), 400

    sale_date = d.get("sale_date") or datetime.date.today().isoformat()
    cur = conn.execute(
        """INSERT INTO sales (company_id, product_id, quantity, selling_price, invoice_number, customer_name, sale_date, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (company_id, d["product_id"], qty, float(d["selling_price"]), d["invoice_number"], d.get("customer_name", "Walk-in Customer"), sale_date, g.user["username"]),
    )
    conn.execute(
        "UPDATE products SET quantity = quantity - ?, last_updated=? WHERE id=?",
        (qty, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), d["product_id"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    log_activity(company_id, g.user["username"], "Sale Created", f"{product['name']} x{qty} ({d['invoice_number']})")
    return jsonify({"id": new_id}), 201


# ---------------------------------------------------------------------------
# activity log
# ---------------------------------------------------------------------------

@app.route("/api/activity-log", methods=["GET"])
@login_required
def get_activity_log():
    company_id, err = company_or_403()
    if err:
        return err
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM activity_logs WHERE company_id=? ORDER BY id DESC LIMIT 200", (company_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

@app.route("/api/reports/<report_type>", methods=["GET"])
@login_required
def reports(report_type):
    company_id, err = company_or_403()
    if err:
        return err
    conn = get_db()

    if report_type == "inventory":
        rows = conn.execute(
            """SELECT product_code, name, purchase_price, selling_price, quantity,
                      (selling_price * quantity) as stock_value
               FROM products WHERE company_id=? ORDER BY name""",
            (company_id,),
        ).fetchall()
    elif report_type == "sales":
        rows = conn.execute(
            """SELECT sa.sale_date, sa.invoice_number, p.name as product, sa.quantity,
                      sa.selling_price, (sa.selling_price*sa.quantity) as total, sa.customer_name
               FROM sales sa LEFT JOIN products p ON sa.product_id=p.id
               WHERE sa.company_id=? ORDER BY sa.sale_date DESC""",
            (company_id,),
        ).fetchall()
    elif report_type == "purchases":
        rows = conn.execute(
            """SELECT pu.purchase_date, p.name as product, pu.quantity, pu.cost
               FROM purchases pu LEFT JOIN products p ON pu.product_id=p.id
               WHERE pu.company_id=? ORDER BY pu.purchase_date DESC""",
            (company_id,),
        ).fetchall()
    elif report_type == "low-stock":
        rows = conn.execute(
            """SELECT product_code, name, quantity FROM products
               WHERE company_id=? AND quantity < ? ORDER BY quantity ASC""",
            (company_id, LOW_STOCK_THRESHOLD),
        ).fetchall()
    else:
        conn.close()
        return jsonify({"error": "Unknown report type"}), 404

    conn.close()
    data = [dict(r) for r in rows]

    if request.args.get("format") == "csv":
        if not data:
            return Response("No data available\n", mimetype="text/csv")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={report_type}-report.csv"},
        )

    return jsonify(data)


# ---------------------------------------------------------------------------
# static frontend
# ---------------------------------------------------------------------------

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    full_path = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(full_path):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return resp


if __name__ == "__main__":
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "inventory.db")):
        print("No database found - seeding it now.")
        import seed_data
        seed_data.run()
    port = int(os.environ.get("PORT", 5000))
    # debug mode is only for local development - if a hosting platform
    # has set PORT for us, assume we're in production and turn it off
    is_local = "PORT" not in os.environ
    app.run(host="0.0.0.0", port=port, debug=is_local)
