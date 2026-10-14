# 3-inventory-tracker
nvenTrack is a small full-stack app for one owner who runs three separate businesses (Car Factory, Stationery Store, Supermarket) from a single login system. 

# InvenTrack

InvenTrack is an inventory management system that helps manage three businesses: Car Factory, Stationery Store, and Supermarket, using a single website.

 Features
- Login for owner and managers
- Manage inventory items
- Record purchases and sales
- Automatic stock updates
- Dashboard for each company
- View sales, purchases, and inventory reports
- Export reports as CSV
- Activity log
- Dark mode

 Technologies Used
- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Tailwind CSS
- Chart.js
- JWT Authentication

 How to Run

1. Open the project folder in your terminal.
2. Go to the backend folder:

   `cd backend`

3. Install the required packages:

   `pip install -r requirements.txt`

4. Run the application:

   `python app.py`

5. Open `http://localhost:5000` in your browser.

Demo Login

| Account | Username | Password |
|---|---|---|
| Owner | owner | owner123 |
| Car Factory | caradmin | car123 |
| Stationery Store | stationadmin | station123 |
| Supermarket | marketadmin | market123 |

**Note:** These are demo credentials. Change them before deploying the project publicly.

## Project Structure

inventory-system
├── backend/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── pages/
└── Procfile


## Author

Tanish Sharma
