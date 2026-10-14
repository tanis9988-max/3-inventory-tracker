# InvenTrack – Multi-Company Inventory Management System

Small inventory system for one owner who runs three businesses (Car
Factory, Stationery Store, Supermarket), managed from a single
dashboard. Backend is Flask + SQLite, frontend is plain HTML/CSS/JS
(Tailwind + Chart.js from CDN, no build step).

## Login Details

Login page asks for Company, Username and Password.

| Company | Username | Password | Access |
|---|---|---|---|
| Owner (all companies) | `owner` | `owner123` | Everything, all 3 companies |
| Car Factory | `caradmin` | `car123` | Car Factory only |
| Stationery Store | `stationadmin` | `station123` | Stationery only |
| Supermarket | `marketadmin` | `market123` | Supermarket only |

Pick the matching company from the dropdown before logging in.

---

## Running it

You need Python 3.9+.

```bash
cd backend
pip install -r requirements.txt
python app.py
```

First run creates and seeds `inventory.db` automatically. Then open:

```
http://localhost:5000
```

One server, no CORS setup needed since Flask serves the frontend too.

To reset the demo data, stop the server, delete `backend/inventory.db`,
and run `python app.py` again.

## Folder structure

```
inventory-system/
├── backend/
│   ├── app.py            # API routes + auth + RBAC
│   ├── database.py       # sqlite schema
│   ├── seed_data.py       # demo data (3 companies, 30 products)
│   ├── requirements.txt
│   └── inventory.db      # created on first run
├── frontend/
│   ├── index.html        # login page
│   ├── css/style.css
│   ├── js/
│   │   ├── api.js         # fetch wrapper + auth
│   │   └── layout.js      # sidebar/topbar, dark mode
│   └── pages/
│       ├── owner-dashboard.html
│       ├── company-dashboard.html
│       ├── inventory.html
│       ├── purchases.html
│       ├── sales.html
│       ├── reports.html
│       ├── activity-log.html
│       └── profile.html
└── README.md
```

---

## How to add a stock item

1. Log in as a manager (or owner, then open a company from the owner
   dashboard).
2. Click **Inventory** in the sidebar.
3. Click **+ Add Stock Item** in the top right.
4. Fill in the item name, purchase price, selling price and quantity.
   Image URL is optional — leave it blank and a placeholder image is
   used automatically.
5. Click **Save Item**. It shows up straight away in the inventory
   grid/table, and gets logged in the Activity Log.

Stock quantity also updates automatically in two other places, so you
don't have to edit it by hand every time:
- **Purchases page** → recording a purchase adds that quantity to the
  product's stock.
- **Sales page** → recording a sale subtracts that quantity from
  stock (and blocks the sale if there isn't enough left).

## What's in the demo data

- 3 companies, 10 products each (30 total) — matches the brief, didn't
  want to pad it out with fake data.
- A few sample purchases/sales per company so dashboards and reports
  aren't empty on first login.
- Product images come from picsum.photos with a seeded URL per
  product, so they stay consistent on reload without me hotlinking
  random images that could 404 later.
- A couple of items per company are deliberately left under 10 units
  so the low-stock badges/report have something to show.

## Features

- Company + role based login (owner vs manager), JWT sessions
- Owner dashboard with company switcher + combined stats
- Per-company dashboard: stat cards, sales-vs-purchases chart, recent
  activity feed
- Inventory: add / edit / delete, search, sort, grid or table view,
  pagination, low-stock badges
- Purchases: recording one increases stock automatically
- Sales: recording one decreases stock (blocked if not enough stock)
- Reports: inventory / sales / purchases / low-stock, CSV export
  (PDF export uses the browser's print dialog — didn't see the point
  pulling in a whole PDF library for this)
- Activity log for every add/update/delete/login/logout
- Dark mode toggle, responsive layout, toasts, confirm-before-delete

## Known limitations

- SQLite + Flask dev server — fine for a demo, not for real traffic.
- No image upload, just a URL field.
- Only the 4 seeded accounts exist, no signup/forgot-password.
- PDF export is print-to-PDF, not a generated PDF file.
- JWT secret is hardcoded in `app.py` for convenience — move it to an
  env variable before deploying this anywhere real.
