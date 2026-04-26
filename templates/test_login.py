"""
test_login.py — simulates exactly what Flask does during login
Run: python test_login.py
"""
import sqlite3

DB = "database.db"

def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

print("=" * 50)
print("LOGIN SIMULATION TEST")
print("=" * 50)

# ── 1. Show all users ─────────────────────────
conn = connect()
cur  = conn.cursor()
cur.execute("SELECT id, username, password, role FROM users")
users = cur.fetchall()
conn.close()

print("\n── ALL USERS IN DATABASE ──────────────")
if not users:
    print("  ❌ NO USERS FOUND — database is empty!")
else:
    for u in users:
        print(f"  id={u['id']} | username='{u['username']}' | password='{u['password']}' | role='{u['role']}'")

# ── 2. Simulate login for each user ──────────
print("\n── LOGIN SIMULATION ───────────────────")
for u in users:
    conn = connect()
    cur  = conn.cursor()
    cur.execute(
        "SELECT username, role FROM users WHERE username=? AND password=?",
        (u['username'], u['password'])
    )
    result = cur.fetchone()
    conn.close()

    if result:
        role = result['role']
        if role == 'admin':
            dest = '/admin_dashboard'
        elif role == 'pharmacist':
            dest = '/pharmacist_dashboard'
        elif role == 'user':
            dest = '/user_dashboard'
        else:
            dest = f'❌ UNKNOWN ROLE: "{role}" — will redirect to / (login page!)'
        print(f"  ✅ '{u['username']}' → {dest}")
    else:
        print(f"  ❌ '{u['username']}' — login FAILED (password mismatch?)")

# ── 3. Check for NULL/wrong roles ─────────────
print("\n── ROLE CHECK ─────────────────────────")
conn = connect()
cur  = conn.cursor()
cur.execute("SELECT username, role FROM users WHERE role NOT IN ('admin','pharmacist','user') OR role IS NULL")
bad = cur.fetchall()
conn.close()

if bad:
    print("  ❌ These users have WRONG or NULL roles:")
    for u in bad:
        print(f"     username='{u['username']}' | role={repr(u['role'])}")
    print("\n  FIX: Run this SQL:")
    print("  UPDATE users SET role='user' WHERE role NOT IN ('admin','pharmacist','user') OR role IS NULL;")
else:
    print("  ✅ All roles are correct")

# ── 4. Check user_dashboard route condition ───
print("\n── ROUTE CONDITION CHECK ──────────────")
print("  app.py checks: session['role'] != 'user'")
conn = connect()
cur  = conn.cursor()
cur.execute("SELECT username, role FROM users WHERE role='user'")
real_users = cur.fetchall()
conn.close()

if real_users:
    print(f"  ✅ Found {len(real_users)} user(s) with role='user':")
    for u in real_users:
        print(f"     '{u['username']}'")
else:
    print("  ❌ NO users with role='user' — everyone gets redirected back to login!")
    print("  FIX: Register a new account, or run:")
    print("  UPDATE users SET role='user' WHERE username NOT IN ('admin','pharma');")

print("\n" + "=" * 50)