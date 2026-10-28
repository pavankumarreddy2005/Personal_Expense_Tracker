"""Personal expense tracker: SQLite, dated transactions, budget alerts and charts."""
import csv, getpass, hashlib, sqlite3
from datetime import datetime

DB = "expenses.db"
EXPENSE_CATEGORIES = ["Food", "Travel", "Shopping", "Rent", "Groceries", "Bills", "Others"]

def connect():
    """Create the local database and tables automatically."""
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_hash TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY, username TEXT, kind TEXT, category TEXT,
        amount REAL, description TEXT, transaction_time TEXT)""")
    db.execute("CREATE TABLE IF NOT EXISTS budgets(username TEXT, month TEXT, amount REAL, PRIMARY KEY(username,month))")
    db.commit()
    return db

def hash_password(password):
    """Store a hash instead of the readable password."""
    return hashlib.sha256(password.encode()).hexdigest()

def sign_in(db):
    """Create the first account, then ask the user to log in with hidden password input."""
    if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        print("\nCreate your tracker login")
        while True:
            username = input("Choose a username: ").strip()
            if username and not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone(): break
            print("Username is blank or already used.")
        while True:
            password = getpass.getpass("Choose a password (at least 8 characters): ")
            if len(password) < 8:
                print("Use at least 8 characters."); continue
            if password != getpass.getpass("Enter the password again: "):
                print("Passwords do not match."); continue
            break
        db.execute("INSERT INTO users VALUES (?,?)", (username, hash_password(password)))
        db.commit()
        print("Login created. Please sign in.")
    print("\nSign in")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    row = db.execute("SELECT password_hash FROM users WHERE username=?", (username,)).fetchone()
    if row and row[0] == hash_password(password):
        print("Login successful."); return username
    print("Username or password is incorrect."); return None

def this_month(): return datetime.now().strftime("%Y-%m")

def get_budget(db, username, month):
    row = db.execute("SELECT amount FROM budgets WHERE username=? AND month=?", (username,month)).fetchone()
    return row[0] if row else 0

def month_rows(db, username, month):
    return db.execute("""SELECT kind,category,amount,description,transaction_time FROM transactions
        WHERE username=? AND substr(transaction_time,1,7)=? ORDER BY transaction_time,id""", (username,month)).fetchall()

def totals(rows):
    return (sum(r[2] for r in rows if r[0]=="Income"), sum(r[2] for r in rows if r[0]=="Expense"))

def show_dashboard(db, username):
    """Display income, expenses, balance, category totals, and budget."""
    rows=month_rows(db,username,this_month()); income,expenses=totals(rows); limit=get_budget(db,username,this_month())
    categories={name:0 for name in EXPENSE_CATEGORIES}
    for kind,cat,amount,desc,stamp in rows:
        if kind=="Expense": categories[cat]=categories.get(cat,0)+amount
    print("\n"+"="*40+"\n          PERSONAL EXPENSE TRACKER\n"+"="*40)
    print(f"Balance       : ₹{income-expenses:,.0f}\nIncome        : ₹{income:,.0f}\nExpenses      : ₹{expenses:,.0f}")
    print("\nThis Month\n"+"-"*40)
    for cat in EXPENSE_CATEGORIES: print(f"{cat:<14} ₹{categories[cat]:,.0f}")
    print(f"\nBudget        : ₹{limit:,.0f}")
    print(f"Remaining     : ₹{max(0,limit-expenses):,.0f}" if limit else "Remaining     : ₹0")

def week_of(day):
    """Split a month into four budget weeks: days 1-7, 8-14, 15-21, and 22-end."""
    return min((day-1)//7+1,4)

def send_alert(message):
    """Print the alert; send email and/or WhatsApp when configured."""
    print("\n*** BUDGET ALERT ***\n"+message)
    import notification_settings as settings
    if settings.EMAIL_FROM and settings.EMAIL_TO and settings.EMAIL_APP_PASSWORD:
        try:
            import smtplib
            from email.message import EmailMessage
            email=EmailMessage(); email["Subject"]="Expense Tracker Alert"
            email["From"]=settings.EMAIL_FROM; email["To"]=settings.EMAIL_TO; email.set_content(message)
            with smtplib.SMTP_SSL("smtp.gmail.com",465) as server:
                server.login(settings.EMAIL_FROM,settings.EMAIL_APP_PASSWORD); server.send_message(email)
            print("Email alert sent.")
        except Exception as error: print("Email could not be sent:",error)
    # PyWhatKit sends via WhatsApp Web in your logged-in browser.
    if settings.WHATSAPP_TO:
        try:
            import pywhatkit
            pywhatkit.sendwhatmsg_instantly(settings.WHATSAPP_TO,message,wait_time=20,tab_close=False)
            print("WhatsApp alert sent.")
        except Exception as error: print("WhatsApp could not be sent:",error)

def check_alerts(db, username, stamp, added):
    """Notify when an expense crosses its weekly share or the full monthly budget."""
    month=stamp[:7]; limit=get_budget(db,username,month)
    if limit<=0: return
    rows=db.execute("""SELECT amount,transaction_time FROM transactions WHERE username=?
        AND kind='Expense' AND substr(transaction_time,1,7)=?""",(username,month)).fetchall()
    wk=week_of(int(stamp[8:10]))
    week_sum=sum(a for a,t in rows if week_of(int(t[8:10]))==wk)
    month_sum=sum(a for a,t in rows); week_limit=limit/4
    if week_sum-added<=week_limit<week_sum:
        send_alert(f"Week {wk} expenses are ₹{week_sum:.2f}, above its weekly budget share ₹{week_limit:.2f}.")
    if month_sum-added<=limit<month_sum:
        send_alert(f"Monthly expenses are ₹{month_sum:.2f}, above your budget ₹{limit:.2f}.")

def add_transaction(db, username):
    """Choose type/category, enter amount, date/time, and description."""
    choice=input("Type (1=Income, 2=Expense): ").strip()
    if choice not in ("1","2"): print("Choose 1 or 2."); return
    kind="Income" if choice=="1" else "Expense"
    cats=EXPENSE_CATEGORIES if kind=="Expense" else ["Salary","Business","Other Income"]
    print("Categories:")
    for n,cat in enumerate(cats,1): print(f"[{n}] {cat}")
    selected=input("Choose category number: ").strip()
    if not selected.isdigit() or not 1<=int(selected)<=len(cats): print("Invalid category."); return
    category=cats[int(selected)-1]
    try:
        amount=float(input("Amount: ₹"))
        if amount<=0: raise ValueError
        now=datetime.now()
        d=input(f"Date YYYY-MM-DD (Enter for {now:%Y-%m-%d}): ").strip() or now.strftime("%Y-%m-%d")
        tm=input(f"Time HH:MM (Enter for {now:%H:%M}): ").strip() or now.strftime("%H:%M")
        stamp=datetime.strptime(d+" "+tm,"%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
    except ValueError: print("Enter a positive amount and valid date/time."); return
    description=input("Description (optional): ").strip()
    db.execute("INSERT INTO transactions(username,kind,category,amount,description,transaction_time) VALUES (?,?,?,?,?,?)",
               (username,kind,category,amount,description,stamp)); db.commit()
    print(f"Saved: {stamp} | {kind} | {category} | ₹{amount:.2f} | {description}")
    if kind=="Expense": check_alerts(db,username,stamp,amount)

def view_transactions(db, username):
    rows=db.execute("SELECT transaction_time,kind,category,amount,description FROM transactions WHERE username=? ORDER BY transaction_time DESC,id DESC",(username,)).fetchall()
    if not rows: print("No transactions yet.")
    for t in rows: print(f"{t[0]} | {t[1]} | {t[2]} | ₹{t[3]:.2f} | {t[4]}")

def search_transactions(db, username):
    term=input("Search category or description: ").strip()
    rows=db.execute("SELECT transaction_time,kind,category,amount,description FROM transactions WHERE username=? AND (category LIKE ? OR description LIKE ?) ORDER BY transaction_time DESC",(username,f"%{term}%",f"%{term}%")).fetchall()
    if not rows: print("No matches found.")
    for t in rows: print(f"{t[0]} | {t[1]} | {t[2]} | ₹{t[3]:.2f} | {t[4]}")

def set_budget(db, username):
    try:
        amount=float(input("Enter monthly budget (0 means no budget): ₹"))
        if amount<0: raise ValueError
    except ValueError: print("Enter zero or a positive amount."); return
    db.execute("INSERT OR REPLACE INTO budgets VALUES (?,?,?)",(username,this_month(),amount)); db.commit()
    print(f"Budget saved: ₹{amount:.2f}; each weekly share is ₹{amount/4:.2f}.")

def monthly_report(db, username):
    month=input(f"Month YYYY-MM (Enter for {this_month()}): ").strip() or this_month()
    try: datetime.strptime(month,"%Y-%m")
    except ValueError: print("Use YYYY-MM, such as 2026-10."); return
    rows=month_rows(db,username,month); income,expenses=totals(rows)
    print(f"\nMonthly Report: {month}\nIncome   : ₹{income:,.0f}\nExpenses : ₹{expenses:,.0f}\nSavings  : ₹{income-expenses:,.0f}")
    by_cat={n:0 for n in EXPENSE_CATEGORIES}; weeks=[0,0,0,0]
    for kind,cat,amount,desc,stamp in rows:
        if kind=="Expense": by_cat[cat]=by_cat.get(cat,0)+amount; weeks[week_of(int(stamp[8:10]))-1]+=amount
    print("\nExpense categories:")
    for cat,amount in by_cat.items():
        if amount: print(f"  {cat:<14} ₹{amount:,.0f}")
    try: import matplotlib.pyplot as plt
    except ImportError: print("Install chart library with: py -m pip install -r requirements.txt"); return
    plt.bar(["Week 1","Week 2","Week 3","Week 4"],weeks,color="cornflowerblue")
    plt.title("Expenses by Week - "+month); plt.ylabel("Expenses (₹)"); plt.tight_layout()
    plt.savefig("monthly_expenses.png"); plt.show(); print("Graph saved as monthly_expenses.png")

def export_csv(db, username):
    rows=db.execute("SELECT transaction_time,kind,category,amount,description FROM transactions WHERE username=? ORDER BY transaction_time",(username,)).fetchall()
    with open("transactions.csv","w",newline="",encoding="utf-8") as file:
        writer=csv.writer(file); writer.writerow(["Date and time","Type","Category","Amount","Description"]); writer.writerows(rows)
    print("Exported transactions.csv")

def main():
    db=connect(); username=sign_in(db)
    if not username: db.close(); return
    while True:
        show_dashboard(db,username)
        print("\n[1] Add Transaction\n[2] View Transactions\n[3] Search\n[4] Monthly Report\n[5] Budget\n[6] Export CSV\n[7] Exit")
        choice=input("Choose an option: ").strip()
        if choice=="1": add_transaction(db,username)
        elif choice=="2": view_transactions(db,username)
        elif choice=="3": search_transactions(db,username)
        elif choice=="4": monthly_report(db,username)
        elif choice=="5": set_budget(db,username)
        elif choice=="6": export_csv(db,username)
        elif choice=="7": print("Goodbye!"); break
        else: print("Choose a number from 1 to 7.")
    db.close()

if __name__=="__main__": main()
