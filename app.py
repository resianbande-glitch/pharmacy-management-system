from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from sklearn.linear_model import LinearRegression
import pandas as pd

app = Flask(__name__)
app.secret_key = "pharmacysecret"


# ── DATABASE ─────────────────────────────────────────
def connect():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # access columns by name
    return conn


# ── INIT TABLES ──────────────────────────────────────
def init_db():
    conn = connect()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role     TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS medicines(
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT,
            quantity INTEGER,
            price    REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales(
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine TEXT,
            quantity INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart(
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user     TEXT,
            medicine TEXT,
            price    REAL,
            qty      INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            user   TEXT,
            total  REAL,
            method TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS returns(
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine TEXT,
            qty      INTEGER
        )
    """)

    # default admin
    cur.execute("SELECT * FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            ("admin", "1234", "admin")
        )

    # default pharmacist
    cur.execute("SELECT * FROM users WHERE username='pharma'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            ("pharma", "1234", "pharmacist")
        )

    conn.commit()
    conn.close()

init_db()


# ── LOGIN ─────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = connect()
        cur  = conn.cursor()
        cur.execute(
            "SELECT username, role FROM users WHERE username=? AND password=?",
            (u, p)
        )
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect("/admin_dashboard")
            elif user["role"] == "pharmacist":
                return redirect("/pharmacist_dashboard")
            else:
                return redirect("/user_dashboard")

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


# ── REGISTER ──────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip() 

       
        if username.lower() in ["admin", "pharmacist"]:
            return render_template("register.html", error="Kini nga username dili pwede gamiton.")

        conn = connect()
        cur = conn.cursor()

        try:
            
            cur.execute(
                "INSERT INTO users(username, password, role) VALUES(?, ?, ?)",
                (username, password, "user")
            )
            conn.commit()
            conn.close()
            return redirect("/")
        except Exception as e:
            conn.close()
            return render_template("register.html", error="Username already exists.")

    return render_template("register.html")


# ── LOGOUT ────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ── CHECK LOGIN (for guest cart guard) ───────────────
@app.route("/check_login")
def check_login():
    return {"logged_in": "user" in session}


# ── ADMIN DASHBOARD ───────────────────────────────────
@app.route("/admin_dashboard")
def admin_dashboard():
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    conn = connect()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM medicines")
    meds = cur.fetchall()

    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    cur.execute("SELECT username, role FROM users")
    users = cur.fetchall()

    conn.close()

    return render_template("admin_dashboard.html",
                           meds=meds,
                           orders=orders,
                           users=users)


# ── PHARMACIST DASHBOARD ──────────────────────────────
@app.route("/pharmacist_dashboard")
def pharmacist_dashboard():
    if "user" not in session or session["role"] != "pharmacist":
        return redirect("/")

    conn = connect()
    cur  = conn.cursor()

   
    cur.execute("SELECT * FROM medicines")
    meds = cur.fetchall()

    conn.close()

    return render_template("pharmacist_dashboard.html", meds=meds)


# ── USER DASHBOARD ────────────────────────────────────
@app.route("/user_dashboard")
def user_dashboard():
    if "user" not in session or session["role"] != "user":
        return redirect("/")

    conn = connect()
    cur  = conn.cursor()

   
    cur.execute("SELECT * FROM medicines WHERE quantity > 0")
    meds = cur.fetchall()

    conn.close()

    return render_template("user_dashboard.html", meds=meds)


# ── ADD MEDICINE (admin only) ─────────────────────────
@app.route("/add", methods=["GET", "POST"])
def add():
    
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    error   = None
    success = None

    if request.method == "POST":
        name  = request.form.get("name",  "").strip()
        qty   = request.form.get("qty",   "").strip()
        price = request.form.get("price", "").strip()

        # ── basic validation ──────────────────────────
        if not name:
            error = "Medicine name is required."
        elif not qty.isdigit() or int(qty) < 1:
            error = "Quantity must be a whole number greater than 0."
        else:
            try:
                price_val = float(price)
                if price_val < 0:
                    raise ValueError
            except ValueError:
                error = "Price must be a valid positive number."

        if not error:
            try:
                conn = connect()
                cur  = conn.cursor()

                # ── check if medicine already exists ──
                cur.execute(
                    "SELECT id, quantity FROM medicines WHERE LOWER(name)=LOWER(?)",
                    (name,)
                )
                existing = cur.fetchone()

                if existing:
                    # update stock instead of duplicating
                    new_qty = existing["quantity"] + int(qty)
                    cur.execute(
                        "UPDATE medicines SET quantity=?, price=? WHERE id=?",
                        (new_qty, price_val, existing["id"])
                    )
                    success = f"'{name}' already exists — stock updated to {new_qty} units."
                else:
                    cur.execute(
                        "INSERT INTO medicines(name, quantity, price) VALUES(?, ?, ?)",
                        (name, int(qty), price_val)
                    )
                    success = f"'{name}' added successfully to inventory!"

                conn.commit()
                conn.close()

                
                session["flash"] = success
                return redirect("/admin_dashboard")

            except Exception as e:
                error = f"Database error: {str(e)}"
                print(f"[ADD MEDICINE ERROR] {e}") 

    return render_template("add.html", error=error, success=success)


# ── STOCK PAGE ────────────────────────────────────────
@app.route("/stock")
def stock():
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    conn = connect()
    cur  = conn.cursor()
    cur.execute("SELECT name, quantity FROM medicines ORDER BY quantity ASC")
    meds = cur.fetchall()
    conn.close()

    return render_template("stock.html", meds=meds)


# ── REPORTS PAGE ──────────────────────────────────────

@app.route("/reports")
def reports():
    if "user" not in session:
        return redirect("/")

    role = session.get("role") 
    
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()
    conn.close()

    return render_template("reports.html", orders=orders, role=role)

# ── SELL (record sale for ML) ─────────────────────────
@app.route("/sell", methods=["POST"])
def sell():
    if "user" not in session:
        return redirect("/")

    medicine = request.form["medicine"]
    qty      = request.form["qty"]

    conn = connect()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO sales(medicine, quantity) VALUES(?, ?)",
        (medicine, qty)
    )
    conn.commit()
    conn.close()

    return redirect("/admin_dashboard")


# ── ML PREDICTION ─────────────────────────────────────

@app.route('/predict')
def predict():
   
    if "user" not in session:
        return redirect("/")

 
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("SELECT name, quantity, price FROM medicines")
    all_meds = cur.fetchall()
    

    cur.execute("SELECT user FROM orders")
    all_orders = cur.fetchall()

    prediction_results = []

    for med in all_meds:
        name = med['name']
        current_stock = med['quantity']
        
       
        
        sales_count = 0
        
        if current_stock < 5:
            forecast = "High"
            action = "Critical: Fast moving & Low stock"
            sales_count = 10 # simulated count
        elif current_stock < 15:
            forecast = "Stable"
            action = "Moderate: Regular sales detected"
            sales_count = 4 # simulated count
        else:
            forecast = "Low"
            action = "Slow: Minimal movement"
            sales_count = 1 # simulated count

        prediction_results.append({
            'name': name,
            'current_stock': current_stock,
            'forecast': forecast,
            'action': action,
            'sales_frequency': sales_count
        })

    conn.close() 
    return render_template('predict.html', results=prediction_results)

# ── CART ──────────────────────────────────────────────
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    if "user" not in session:
        return {"error": "not_logged_in"}, 401

    data = request.json

    conn = connect()
    cur  = conn.cursor()

    # check if item already in cart for this user
    cur.execute(
        "SELECT id, qty FROM cart WHERE user=? AND medicine=?",
        (session["user"], data["name"])
    )
    existing = cur.fetchone()

    if existing:
        # increment qty
        cur.execute(
            "UPDATE cart SET qty=? WHERE id=?",
            (existing["qty"] + 1, existing["id"])
        )
    else:
        cur.execute(
            "INSERT INTO cart(user, medicine, price, qty) VALUES(?,?,?,?)",
            (session["user"], data["name"], float(data["price"]), 1)
        )

    conn.commit()
    conn.close()

    return {"message": "added"}

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if "user" not in session:
        return jsonify({"success": False}), 401

    data = request.get_json()
    name = data.get('name')

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM cart WHERE user=? AND medicine=?",
        (session["user"], name)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/get_cart")
def get_cart():
    if "user" not in session:
        return jsonify({})

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT medicine, price, qty FROM cart WHERE user=?",
        (session["user"],)
    )
    items = cur.fetchall()
    conn.close()

    # I-format para ma-match ang JS cartItems object
    result = {}
    for item in items:
        result[item["medicine"]] = {
            "price": item["price"],
            "qty": item["qty"]
        }
    return jsonify(result)


@app.route("/cart")
def view_cart():
    if "user" not in session:
        return {"error": "not_logged_in"}

    conn = connect()
    cur  = conn.cursor()
    cur.execute(
        "SELECT medicine, price, qty FROM cart WHERE user=?",
        (session["user"],)
    )
    items = cur.fetchall()
    conn.close()

    total = sum(i["price"] * i["qty"] for i in items)

    return {
        "cart": [{"name": i["medicine"], "price": i["price"], "qty": i["qty"]} for i in items],
        "total": total
    }


# ── CHECKOUT ──────────────────────────────────────────


@app.route("/checkout", methods=["POST"])
def checkout():
    if "user" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.json
    method  = data.get("method", "COD")
    name    = data.get("name", "")
    phone   = data.get("phone", "")
    address = data.get("address", "")

    conn = connect()
    cur  = conn.cursor()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        "SELECT medicine, price, qty FROM cart WHERE user=?",
        (session["user"],)
    )
    items = cur.fetchall()

    if not items:
        conn.close()
        return jsonify({"error": "cart_empty"}), 400

    total    = sum(item["price"] * item["qty"] for item in items)
    discount = float(data.get("discount", 0))
    total    = total - (total * discount)

    cur.execute(
        "INSERT INTO orders(user, total, method) VALUES(?,?,?)",
        (session["user"], round(total, 2), method)
    )

    for item in items:
        cur.execute(
            "UPDATE medicines SET quantity = quantity - ? WHERE name=? AND quantity >= ?",
            (item["qty"], item["medicine"], item["qty"])
        )

    cur.execute("DELETE FROM cart WHERE user=?", (session["user"],))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "order_placed", "total": round(total, 2)})
@app.route('/place_order', methods=['POST'])
def place_order():
    if "user" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.get_json()
    name    = data.get('name')
    phone   = data.get('phone')
    address = data.get('address')

    conn = connect()
    cur  = conn.cursor()

    # Kuha ang cart sa DB
    cur.execute(
        "SELECT medicine, price, qty FROM cart WHERE user=?",
        (session["user"],)
    )
    items = cur.fetchall()

    if not items:
        conn.close()
        return jsonify({"error": "cart_empty"}), 400

    total = sum(i["price"] * i["qty"] for i in items)

    # Save order
    cur.execute(
        "INSERT INTO orders(user, total, method) VALUES(?,?,?)",
        (session["user"], round(total, 2), "cash")
    )

    # ← KANI ANG KULANG: reduce stock
    for item in items:
        cur.execute(
            "UPDATE medicines SET quantity = quantity - ? WHERE name=? AND quantity >= ?",
            (item["qty"], item["medicine"], item["qty"])
        )

    # Clear cart
    cur.execute("DELETE FROM cart WHERE user=?", (session["user"],))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "order_placed"})
# ── RETURN MEDICINE ───────────────────────────────────
@app.route("/return_medicine", methods=["POST"])
def return_medicine():
    if "user" not in session or session["role"] != "pharmacist":
        return redirect("/")

    med = request.form["medicine"]
    qty = request.form["qty"]

    conn = connect()
    cur  = conn.cursor()

    cur.execute(
        "UPDATE medicines SET quantity = quantity + ? WHERE name=?",
        (int(qty), med)
    )
    cur.execute(
        "INSERT INTO returns(medicine, qty) VALUES(?,?)",
        (med, int(qty))
    )

    conn.commit()
    conn.close()

    return redirect("/pharmacist_dashboard")


# ── RUN ───────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
