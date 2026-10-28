"""Browser-based interface for this expense tracker; expense_tracker.py is unchanged.

Start from this folder with: py -m streamlit run streamlit_app.py
"""
import hashlib
import sqlite3
from datetime import date, datetime

import pandas as pd
import streamlit as st

DB_FILE = "expenses.db"
EXPENSE_CATEGORIES = ["Food", "Travel", "Shopping", "Rent", "Groceries", "Bills", "Others"]
INCOME_CATEGORIES = ["Salary", "Business", "Other Income"]

st.set_page_config(page_title="Personal Expense Tracker", page_icon="💰", layout="wide")


def connect_db():
    """Connect to the same SQLite file and table columns as expense_tracker.py."""
    db = sqlite3.connect(DB_FILE)
    db.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_hash TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY, username TEXT, kind TEXT, category TEXT,
        amount REAL, description TEXT, transaction_time TEXT)""")
    db.execute("CREATE TABLE IF NOT EXISTS budgets(username TEXT, month TEXT, amount REAL, PRIMARY KEY(username,month))")
    db.commit()
    return db


def password_hash(password):
    """Use the same password hash format as the existing terminal program."""
    return hashlib.sha256(password.encode()).hexdigest()


def read_budget(db, username, month):
    row = db.execute("SELECT amount FROM budgets WHERE username=? AND month=?",
                     (username, month)).fetchone()
    return row[0] if row else 0.0


def read_month(db, username, month):
    return db.execute("""SELECT id,kind,category,amount,description,transaction_time
        FROM transactions WHERE username=? AND substr(transaction_time,1,7)=?
        ORDER BY transaction_time DESC,id DESC""", (username, month)).fetchall()


def read_all(db, username):
    """Read all saved transactions for the original View and Search menu actions."""
    return db.execute("""SELECT id,kind,category,amount,description,transaction_time
        FROM transactions WHERE username=? ORDER BY transaction_time DESC,id DESC""",
        (username,)).fetchall()


def week_number(day):
    """Divide a month into days 1-7, 8-14, 15-21 and 22 through month end."""
    return min((day - 1) // 7 + 1, 4)


def push_alert(message):
    """Keep alert visible after page refresh and deliver configured notifications."""
    st.session_state.setdefault("alerts", []).append(message)
    try:
        import notification_settings as settings
    except ImportError:
        return
    # Optional email delivery through Gmail SMTP and an App Password.
    if settings.EMAIL_FROM and settings.EMAIL_TO and settings.EMAIL_APP_PASSWORD:
        try:
            import smtplib
            from email.message import EmailMessage
            email = EmailMessage()
            email["Subject"] = "Personal Expense Tracker Alert"
            email["From"] = settings.EMAIL_FROM
            email["To"] = settings.EMAIL_TO
            email.set_content(message)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(settings.EMAIL_FROM, settings.EMAIL_APP_PASSWORD)
                server.send_message(email)
            st.session_state.setdefault("delivery_messages", []).append("Email alert sent.")
        except Exception as error:
            st.session_state.setdefault("delivery_messages", []).append(f"Email failed: {error}")
    # PyWhatKit sends through WhatsApp Web on the computer running this app.
    if settings.WHATSAPP_TO:
        try:
            import pywhatkit
            pywhatkit.sendwhatmsg_instantly(settings.WHATSAPP_TO, message,
                                            wait_time=10, tab_close=False)
            st.session_state.setdefault("delivery_messages", []).append("WhatsApp Web send started.")
        except Exception as error:
            st.session_state.setdefault("delivery_messages", []).append(f"WhatsApp failed: {error}")


def check_crossing(db, username, stamp, new_amount):
    """Alert when this saved expense first crosses its weekly/monthly budget."""
    month = stamp[:7]
    monthly_budget = read_budget(db, username, month)
    if monthly_budget <= 0:
        return  # Budget alerts are off until the user sets a nonzero budget.
    rows = db.execute("""SELECT amount,transaction_time FROM transactions
        WHERE username=? AND kind='Expense' AND substr(transaction_time,1,7)=?""",
        (username, month)).fetchall()
    wk = week_number(int(stamp[8:10]))
    weekly_spend = sum(amount for amount, when in rows
                       if week_number(int(when[8:10])) == wk)
    monthly_spend = sum(amount for amount, _ in rows)
    weekly_limit = monthly_budget / 4
    if weekly_spend - new_amount <= weekly_limit < weekly_spend:
        push_alert(f"Week {wk} expenses are ₹{weekly_spend:.2f}, above this week's share of ₹{weekly_limit:.2f}.")
    if monthly_spend - new_amount <= monthly_budget < monthly_spend:
        push_alert(f"Monthly expenses are ₹{monthly_spend:.2f}, above your budget of ₹{monthly_budget:.2f}.")


def account_page(db):
    """Show sign up and login forms; reuse the existing database user table."""
    users_exist = db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    tabs = st.tabs(["Sign in", "Create account"] if users_exist else ["Create account"])
    if users_exist:
        with tabs[0]:
            with st.form("signin"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in")
            if submitted:
                row = db.execute("SELECT password_hash FROM users WHERE username=?", (username,)).fetchone()
                if row and row[0] == password_hash(password):
                    st.session_state["username"] = username
                    st.rerun()
                st.error("Username or password is incorrect.")
    with tabs[-1]:
        with st.form("signup"):
            username = st.text_input("Choose a username")
            password = st.text_input("Choose a password (at least 8 characters)", type="password")
            confirm = st.text_input("Enter the password again", type="password")
            submitted = st.form_submit_button("Create account")
        if submitted:
            if not username.strip():
                st.error("Enter a username.")
            elif db.execute("SELECT 1 FROM users WHERE username=?", (username.strip(),)).fetchone():
                st.error("That username already exists.")
            elif len(password) < 8:
                st.error("Use at least 8 characters for the password.")
            elif password != confirm:
                st.error("The passwords do not match.")
            else:
                db.execute("INSERT INTO users VALUES (?,?)", (username.strip(), password_hash(password)))
                db.commit()
                st.success("Account created. Sign in now.")
                st.rerun()


def tracker_page(db, username):
    """Show the familiar text dashboard and use the old numbered menu as web navigation."""
    st.title("PERSONAL EXPENSE TRACKER")
    st.caption(f"Signed in as {username}")
    month_choice = st.date_input("Month to display", value=date.today().replace(day=1))
    month = month_choice.strftime("%Y-%m")
    rows = read_month(db, username, month)
    income = sum(row[3] for row in rows if row[1] == "Income")
    expenses = sum(row[3] for row in rows if row[1] == "Expense")
    monthly_budget = read_budget(db, username, month)
    categories = {name: 0 for name in EXPENSE_CATEGORIES}
    for row in rows:
        if row[1] == "Expense":
            categories[row[2]] = categories.get(row[2], 0) + row[3]

    # Show the same dashboard and numbered choices as the original terminal output.
    dashboard_lines = [
        "=" * 40,
        "          PERSONAL EXPENSE TRACKER",
        "=" * 40,
        f"Balance       : ₹{income-expenses:,.0f}",
        f"Income        : ₹{income:,.0f}",
        f"Expenses      : ₹{expenses:,.0f}",
        "",
        f"This Month ({month})",
        "-" * 40,
    ]
    for category in EXPENSE_CATEGORIES:
        dashboard_lines.append(f"{category:<14} ₹{categories.get(category,0):,.0f}")
    dashboard_lines.extend([
        "",
        f"Budget        : ₹{monthly_budget:,.0f}",
        f"Remaining     : ₹{max(0,monthly_budget-expenses):,.0f}" if monthly_budget else "Remaining     : ₹0",
        "",
        "[1] Add Transaction",
        "[2] View Transactions",
        "[3] Search",
        "[4] Monthly Report",
        "[5] Budget",
        "[6] Export CSV",
        "[7] Exit",
    ])
    st.code("\n".join(dashboard_lines), language=None)

    menu = ["[1] Add Transaction", "[2] View Transactions", "[3] Search",
            "[4] Monthly Report", "[5] Budget", "[6] Export CSV", "[7] Exit"]
    option = st.sidebar.radio("Choose an option", menu)
    for message in st.session_state.pop("alerts", []):
        st.warning(message)
    for message in st.session_state.pop("delivery_messages", []):
        st.info(message)

    if option == menu[0]:
        st.subheader("Add Transaction")
        kind = st.selectbox("Type", ["Expense", "Income"])
        category_list = EXPENSE_CATEGORIES if kind == "Expense" else INCOME_CATEGORIES
        with st.form("transaction_form", clear_on_submit=True):
            category = st.selectbox("Category", category_list)
            amount = st.number_input("Amount (₹)", min_value=0.01, step=100.0)
            day = st.date_input("Transaction date", value=date.today())
            clock = st.time_input("Transaction time", value=datetime.now().time().replace(second=0, microsecond=0))
            description = st.text_input("Description")
            submitted = st.form_submit_button("Save transaction")
        if submitted:
            stamp = datetime.combine(day, clock).strftime("%Y-%m-%d %H:%M")
            db.execute("""INSERT INTO transactions(username,kind,category,amount,description,transaction_time)
                VALUES (?,?,?,?,?,?)""", (username, kind, category, amount, description, stamp))
            db.commit()
            if kind == "Expense":
                check_crossing(db, username, stamp, amount)
            st.success("Transaction saved.")
            st.rerun()

    elif option == menu[1]:
        st.subheader("View Transactions")
        all_rows = read_all(db, username)
        if all_rows:
            frame = pd.DataFrame(all_rows, columns=["ID", "Type", "Category", "Amount", "Description", "Date and time"])
            st.dataframe(frame.drop(columns="ID"), use_container_width=True, hide_index=True)
        else:
            st.info("No transactions recorded for this month.")

    elif option == menu[2]:
        st.subheader("Search Transactions")
        query = st.text_input("Search by category or description")
        all_rows = read_all(db, username)
        matches = [row for row in all_rows if query.lower() in row[2].lower() or query.lower() in row[4].lower()]
        if matches:
            frame = pd.DataFrame(matches, columns=["ID", "Type", "Category", "Amount", "Description", "Date and time"])
            st.dataframe(frame.drop(columns="ID"), use_container_width=True, hide_index=True)
        elif query:
            st.info("No matching transactions found.")

    elif option == menu[3]:
        st.subheader(f"Monthly Report: {month}")
        st.write(f"**Income:** ₹{income:,.0f}  |  **Expenses:** ₹{expenses:,.0f}  |  **Savings:** ₹{income-expenses:,.0f}")
        st.write("Expense categories:")
        for category, amount in categories.items():
            if amount:
                st.write(f"- {category}: ₹{amount:,.0f}")
        week_totals = [0.0, 0.0, 0.0, 0.0]
        for row in rows:
            if row[1] == "Expense":
                week_totals[week_number(int(row[5][8:10]))-1] += row[3]
        chart = pd.DataFrame({"Week": ["Week 1", "Week 2", "Week 3", "Week 4"],
                              "Expenses (₹)": week_totals}).set_index("Week")
        st.bar_chart(chart)

    elif option == menu[4]:
        st.subheader("Budget")
        with st.form("budget_form"):
            budget_value = st.number_input("Monthly budget (₹)", min_value=0.0,
                                           value=float(monthly_budget), step=100.0)
            saved_budget = st.form_submit_button("Save budget")
        if saved_budget:
            db.execute("INSERT OR REPLACE INTO budgets VALUES (?,?,?)",
                       (username, month, budget_value))
            db.commit()
            st.success(f"Budget saved. Each weekly share is ₹{budget_value/4:,.2f}.")
            st.rerun()

    elif option == menu[5]:
        st.subheader("Export CSV")
        export_frame = pd.DataFrame(rows, columns=["ID", "Type", "Category", "Amount", "Description", "Date and time"])
        st.download_button("Download CSV", export_frame.drop(columns="ID").to_csv(index=False).encode("utf-8"),
                           file_name=f"transactions_{month}.csv", mime="text/csv")

    elif option == menu[6]:
        st.session_state.pop("username", None)
        st.rerun()


def main():
    st.title("Personal Expense Tracker")
    db = connect_db()
    try:
        username = st.session_state.get("username")
        if username:
            tracker_page(db, username)
        else:
            account_page(db)
    finally:
        db.close()


main()
