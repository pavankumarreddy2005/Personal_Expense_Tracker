# Personal Expense Tracker

Beginner-friendly tracker with sign up/login, SQLite, income/expenses with date, time, category and description, user-set budget, weekly/monthly alerts, four-week graph, search and CSV export.

## Run in VS Code
1. Open this folder in VS Code.
2. Choose Terminal > New Terminal.
3. Install libraries: `py -m pip install -r requirements.txt`
4. Run: `py expense_tracker.py`
5. First run creates a username and confirmed password. Password typing is hidden.
6. Use menu 1 to add transactions, 5 to set a budget, and 4 for the monthly report/chart.

Expense categories: Food, Travel, Shopping, Rent, Groceries, Bills, Others. Enter a date as YYYY-MM-DD and time as HH:MM; press Enter for current date/time. Add an optional description.

The budget starts at ₹0 and is divided into four equal weekly shares (days 1-7, 8-14, 15-21, 22-end). The program shows a weekly alert when that week's spending crosses its share and a monthly alert when spending crosses the full budget.

For email, configure the three EMAIL values below. Gmail requires an App Password. For WhatsApp, put the recipient phone and country code in WHATSAPP_TO, sign in to WhatsApp Web in your browser, and leave the computer available. PyWhatKit sends by automating WhatsApp Web; it is not an official WhatsApp API.

The program creates `expenses.db`, `monthly_expenses.png`, and `transactions.csv` when needed.

## Optional Streamlit web page

The added `streamlit_app.py` opens this tracker as a local web page without editing `expense_tracker.py`. It uses the same `expenses.db` file and account/transaction tables. Open a terminal in this folder, install the requirements, then run:

```text
py -m pip install -r requirements.txt
py -m streamlit run streamlit_app.py
```

The page opens in your browser. Use your existing username/password to sign in. The web page supports transaction date/time, categories, description, monthly budget, weekly and monthly alerts, the four-week graph, and CSV download. Keep the original `expense_tracker.py` file in this folder; it remains available as the terminal version.
