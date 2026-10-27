from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import datetime

app = Flask(__name__)
app.secret_key = "super_secret_pink_key_here"

# --- GLOBAL DATABASE & STATE ---
users_db = {
    "admin": {"password": "password123", "is_admin": True}
}

data_records = [
    {"owner": "admin", "description": "Allowance", "category": "Income", "amount": 1000.0, "type": "Income"},
    {"owner": "admin", "description": "Lunch", "category": "Food", "amount": 150.0, "type": "Expense"}
]

admin_logs = []
current_announcement = {"message": "", "active": False}

# --- HELPER FUNCTIONS ---
def record_log(username, action):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'time': current_time,
        'user': username,
        'action': action
    }
    admin_logs.insert(0, log_entry)

def calculate_user_totals(username):
    total_income = 0.0
    total_expense = 0.0
    user_records = [item for item in data_records if item["owner"] == username]

    for item in user_records:
        if item["type"] == "Income":
            total_income += item["amount"]
        elif item["type"] == "Expense":
            total_expense += item["amount"]

    net_balance = total_income - total_expense
    return total_income, total_expense, net_balance, len(user_records)

# Context processor para laging available ang announcement at users_db sa templates
@app.context_processor
def inject_globals():
    return dict(
        announcement=current_announcement,
        users_db=users_db
    )

# --- API ENDPOINTS (REAL-TIME POLLING) ---
@app.route("/api/check-announcement")
def check_announcement():
    return jsonify(current_announcement)

@app.route("/api/get-logs")
def get_logs():
    user = session.get("user")
    if not user or not users_db.get(user, {}).get("is_admin", False):
        return jsonify([])
    return jsonify(admin_logs)

# --- AUTHENTICATION ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("home"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "Please fill in all fields!"
        elif username in users_db and users_db[username]["password"] == password:
            session["user"] = username
            record_log(username, "Logged in successfully")

            if users_db[username]["is_admin"]:
                return redirect(url_for("admin_panel"))
            return redirect(url_for("home"))
        else:
            error = "Invalid username or password!"

    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect(url_for("home"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "All fields are required!"
        elif username in users_db:
            error = "Username already exists! Choose another one."
        else:
            users_db[username] = {"password": password, "is_admin": False}
            record_log(username, "Registered a new account")
            return redirect(url_for("login"))

    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    user = session.get("user")
    if user:
        record_log(user, "Logged out of the system")
    session.pop("user", None)
    return redirect(url_for("login"))

# --- CORE DASHBOARD ROUTES ---
@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    total_inc, total_exp, balance, count = calculate_user_totals(username)

    return render_template(
        "index.html",
        total_income=total_inc,
        total_expense=total_exp,
        balance=balance,
        count=count,
        username=username
    )

@app.route("/add", methods=["GET", "POST"])
def add_entry():
    if "user" not in session:
        return redirect(url_for("login"))

    error_message = None

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        entry_type = request.form.get("entry_type", "").strip()

        if not description or not category or not amount_raw or not entry_type:
            error_message = "All fields are required!"
        else:
            try:
                amount = float(amount_raw)
                if amount <= 0:
                    error_message = "Amount must be greater than zero!"
                else:
                    new_record = {
                        "owner": session["user"],
                        "description": description,
                        "category": category,
                        "amount": amount,
                        "type": entry_type
                    }
                    data_records.append(new_record)
                    record_log(session["user"], f"Added {entry_type}: {description} (₱{amount})")
                    return redirect(url_for("view_data"))
            except ValueError:
                error_message = "Invalid amount! Please enter a valid number."

    return render_template("add_entry.html", error=error_message)

@app.route("/records")
def view_data():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    user_records = [item for item in data_records if item["owner"] == username]
    return render_template("view_data.html", records=user_records)

# --- ADMIN PANEL ROUTES ---
@app.route("/admin")
def admin_panel():
    user = session.get("user")
    if not user or not users_db.get(user, {}).get("is_admin", False):
        return redirect(url_for("login"))

    record_log("admin", "Accessed the Admin Control Panel")

    return render_template(
        "admin.html",
        transactions=data_records,
        logs=admin_logs
    )

@app.route("/admin/make-admin/<username>", methods=["POST"])
def make_admin(username):
    current_user = session.get("user")
    if not current_user or not users_db.get(current_user, {}).get("is_admin", False):
        return redirect(url_for("login"))

    if username in users_db:
        users_db[username]["is_admin"] = True
        record_log(current_user, f"Promoted user '{username}' to Administrator")

    return redirect(url_for("admin_panel"))

@app.route("/admin/remove-admin/<username>", methods=["POST"])
def remove_admin(username):
    current_user = session.get("user")
    if not current_user or not users_db.get(current_user, {}).get("is_admin", False):
        return redirect(url_for("login"))

    if username in users_db and username != "admin" and username != current_user:
        users_db[username]["is_admin"] = False
        record_log(current_user, f"Removed admin privileges from '{username}'")

    return redirect(url_for("admin_panel"))

@app.route("/admin/broadcast", methods=["POST"])
def broadcast_message():
    user = session.get("user")
    if not user or not users_db.get(user, {}).get("is_admin", False):
        return redirect(url_for("login"))

    msg = request.form.get("announcement_text", "").strip()
    if msg:
        current_announcement["message"] = msg
        current_announcement["active"] = True
        record_log(user, f"Sent broadcast announcement: {msg}")

    return redirect(url_for("admin_panel"))

@app.route("/admin/clear-broadcast", methods=["POST"])
def clear_broadcast():
    user = session.get("user")
    if not user or not users_db.get(user, {}).get("is_admin", False):
        return redirect(url_for("login"))

    current_announcement["active"] = False
    current_announcement["message"] = ""
    record_log(user, "Cleared the broadcast announcement")

    return redirect(url_for("admin_panel"))

if __name__ == "__main__":
    app.run(debug=True)