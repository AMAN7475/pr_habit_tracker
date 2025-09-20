from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import MySQLdb.cursors
from datetime import datetime, date

# ----------------------
# APP SETUP
# ----------------------
app = Flask(__name__)
app.secret_key = "your-secret-key"  # required for session login

# ---------- DATABASE CONFIG ----------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'Aman'
app.config['MYSQL_PASSWORD'] = 'Aman123'
app.config['MYSQL_DB'] = 'habit_tracker_db'

mysql = MySQL(app)

# ============================================================
# DATABASE INITIALIZATION + SEEDING
# ============================================================
def create_tables_and_seed():
    cursor = mysql.connection.cursor()

    # users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INT AUTO_INCREMENT PRIMARY KEY,
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        username VARCHAR(255) UNIQUE,
        dob DATE,
        gender VARCHAR(20),
        mobile VARCHAR(50),
        email VARCHAR(255) UNIQUE,
        password VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # categories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        category_id INT AUTO_INCREMENT PRIMARY KEY,
        category_name VARCHAR(255) NOT NULL,
        is_custom BOOLEAN DEFAULT FALSE,
        user_id INT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)

    # habits table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS habits (
        habit_id INT AUTO_INCREMENT PRIMARY KEY,
        category_id INT,
        user_id INT NULL,
        habit_name VARCHAR(255),
        is_custom BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        created_at DATETIME,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    # user_selected_habits table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_selected_habits (
        entry_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        habit_id INT,
        date_added DATE,
        custom_name VARCHAR(255),
        is_daily_task BOOLEAN DEFAULT FALSE,
        order_position INT,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (habit_id) REFERENCES habits(habit_id) ON DELETE CASCADE
    )
    """)

    mysql.connection.commit()
    cursor.close()
    print("✅ Tables created/verified.")

with app.app_context():
    try:
        create_tables_and_seed()
    except Exception as e:
        print("⚠️ Warning (DB init failed):", e)


# ============================================================
# DEFAULT CATEGORIES + HABITS SEEDING
# ============================================================
def seed_default_habits():
    cursor = mysql.connection.cursor()

    categories_with_habits = {
        "Health & Wellness": [
            "Drink 8 Glasses of Water",
            "Walk 2,000+ Steps",
            "Meditate for 10 Minutes",
            "Sleep Before 11 PM",
            "Do 15 Minutes of Exercise",
            "Avoid Sugar for a Day",
            "No Junk Food Today"
        ],
        "Learning & Growth": [
            "Read for 15–30 Minutes",
            "Watch an Educational Video",
            "Revise a Past Topic",
            "Listen to a Podcast",
            "Practice Mind Mapping",
            "Do 1 Page of Workbook",
            "Write Down a New Word"
        ],
        "Productivity": [
            "Plan Your Day",
            "Complete Top 3 Tasks",
            "Limit Social Media Time",
            "Set Tomorrow’s Agenda",
            "Organize Emails/Folders",
            "Track Your Screen Time",
            "Take 2 Short Breaks"
        ],
        "Finance & Discipline": [
            "Track Daily Expenses",
            "Review Monthly Budget",
            "Save ₹100 Today",
            "Don’t Order Food Online",
            "Use Cashback / Offers",
            "Set a Daily Spending Limit",
            "Use Cash Instead of UPI"
        ],
        "Personal & Lifestyle": [
            "No Screen 1 Hour Before Bed",
            "Take 1 Photo Daily",
            "Practice Gratitude",
            "Compliment Someone",
            "Say “No” to One Thing",
            "Smile at 3 People",
            "Clean 1 Small Area"
        ]
    }

    for category_name, habits in categories_with_habits.items():
        # insert category if not exists
        cursor.execute("SELECT category_id FROM categories WHERE category_name=%s", (category_name,))
        category = cursor.fetchone()

        if category:
            category_id = category[0]
        else:
            cursor.execute("INSERT INTO categories (category_name, is_custom) VALUES (%s, %s)", (category_name, False))
            mysql.connection.commit()
            category_id = cursor.lastrowid

        # insert habits for this category
        for habit_name in habits:
            cursor.execute("""
                SELECT habit_id FROM habits 
                WHERE habit_name=%s AND category_id=%s
            """, (habit_name, category_id))
            habit = cursor.fetchone()

            if not habit:
                cursor.execute("""
                    INSERT INTO habits (category_id, habit_name, is_custom, is_active, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (category_id, habit_name, False, True))

    mysql.connection.commit()
    cursor.close()
    print("✅ Default categories & habits seeded.")


# Run DB setup + seeding
with app.app_context():
    try:
        create_tables_and_seed()
        seed_default_habits()
    except Exception as e:
        print("⚠️ Warning (DB init/seed failed):", e)


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return render_template("login.html")

# ---------------------------
# Account Creation
# ---------------------------
@app.route("/create_account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        data = request.form
        hashed_password = generate_password_hash(data['password'])

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO users(first_name, last_name, username, dob, gender, mobile, email, password)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data['first_name'], data['last_name'], data['username'],
            data['dob'], data['gender'], data['mobile'], data['email'],
            hashed_password
        ))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for("home"))

    return render_template("create_acc.html")

# ---------------------------
# Login
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        email_or_username = request.form['email_or_username']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT * FROM users WHERE email=%s OR username=%s
        """, (email_or_username, email_or_username))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user['password'], password):
            session['loggedin'] = True
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            return redirect(url_for("dashboard"))
        else:
            msg = "Invalid login credentials ❌"

    return render_template("login.html", msg=msg)

# ---------------------------
# Dashboard
# ---------------------------
@app.route("/dashboard")
def dashboard():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT * FROM categories WHERE is_custom=0")
    predefined = cursor.fetchall()

    cursor.execute("SELECT * FROM categories WHERE is_custom=1 AND user_id=%s", (user_id,))
    custom = cursor.fetchall()

    cursor.close()
    return render_template("dashboard.html",
                           username=session["username"],
                           predefined_categories=predefined,
                           custom_categories=custom)


#-------------------------------------------------
# Habit Categories Routes
#-------------------------------------------------

@app.route("/health_wellness")
def health_wellness():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the Health & Wellness category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", ("Health & Wellness",))
    category = cursor.fetchone()

    if not category:
        cursor.close()
        return "Category 'Health & Wellness' not found in DB"

    category_id = category["category_id"]

    # Fetch habits under this category
    cursor.execute("SELECT * FROM habits WHERE category_id = %s", (category_id,))
    habits = cursor.fetchall()

    cursor.close()

    return render_template(
        "health_wellness.html",
        username=session["username"],
        habits=habits
    )




@app.route("/learning_growth")
def learning_growth():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the Learning & Growth category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", ("Learning & Growth",))
    category = cursor.fetchone()

    if not category:
        cursor.close()
        return "Category 'Learning & Growth' not found in DB"

    category_id = category["category_id"]

    # Fetch habits under this category
    cursor.execute("SELECT * FROM habits WHERE category_id = %s", (category_id,))
    habits = cursor.fetchall()

    cursor.close()

    return render_template(
        "learning_growth.html",
        username=session["username"],
        habits=habits
    )



@app.route("/productivity")
def productivity():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the Productivity category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", ("Productivity",))
    category = cursor.fetchone()

    if not category:
        cursor.close()
        return "Category 'Productivity' not found in DB"

    category_id = category["category_id"]

    # Fetch habits under this category
    cursor.execute("SELECT * FROM habits WHERE category_id = %s", (category_id,))
    habits = cursor.fetchall()

    cursor.close()

    return render_template(
        "productivity.html",
        username=session["username"],
        habits=habits
    )



@app.route("/finance_discipline")
def finance_discipline():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the Finance & Discipline category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", ("Finance & Discipline",))
    category = cursor.fetchone()

    if not category:
        cursor.close()
        return "Category 'Finance & Discipline' not found in DB"

    category_id = category["category_id"]

    # Fetch habits under this category
    cursor.execute("SELECT * FROM habits WHERE category_id = %s", (category_id,))
    habits = cursor.fetchall()

    cursor.close()

    return render_template(
        "finance_discipline.html",
        username=session["username"],
        habits=habits
    )        



@app.route("/personal_lifestyle")
def personal_lifestyle():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)


    # Fetch the Personal & lifestyle category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name=%s", ("Personal & Lifestyle",)) 
    category = cursor.fetchone()

    if not category:
        cursor.close()
        return "Category 'Personal & Lifestyle' not found in DB"

    category_id = category["category_id"]
    
     # Fetch habits under this category
    cursor.execute("SELECT * FROM habits WHERE category_id = %s", (category_id,))
    habits = cursor.fetchall()

    cursor.close()

    return render_template(
        "personal_lifestyle.html",
        username=session["username"],
        habits=habits
    )           


# ---------------------------
# Logout
# ---------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ============================================================
# RUN APP
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)























































"""@app.route("/category/<int:category_id>")
def open_category(category_id):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # fetch category info
    cursor.execute("SELECT * FROM categories WHERE category_id=%s", (category_id,))
    category = cursor.fetchone()

    # fetch habits in this category
    cursor.execute("SELECT * FROM habits WHERE category_id=%s", (category_id,))
    habits = cursor.fetchall()

    cursor.close()
    return render_template("category.html", category=category, habits=habits)

@app.route("/add_habit/<int:category_id>", methods=["POST"])
def add_habit(category_id):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["id"]
    habit_name = request.form["habit_name"]

    cursor = mysql.connection.cursor()
    cursor.execute(""
        INSERT INTO habits(category_id, user_id, habit_name, is_custom, created_at)
        VALUES (%s, %s, %s, %s, %s)
    "", (category_id, user_id, habit_name, True, datetime.now()))
    mysql.connection.commit()
    cursor.close()

    flash("New habit added successfully", "success")
    return redirect(url_for("open_category", category_id=category_id))

@app.route("/edit_habit/<int:habit_id>", methods=["POST"])
def edit_habit(habit_id):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    new_name = request.form["habit_name"]

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE habits SET habit_name=%s WHERE habit_id=%s", (new_name, habit_id))
    mysql.connection.commit()
    cursor.close()

    flash("Habit updated successfully", "info")
    # redirect back to category
    return redirect(request.referrer)

@app.route("/create_category", methods=["GET", "POST"])
def create_category():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        user_id = session["id"]
        category_name = request.form["category_name"]

        cursor = mysql.connection.cursor()
        cursor.execute(""
            INSERT INTO categories(id, category_name, is_custom)
            VALUES (%s,%s,%s)
        "", (id, category_name, True))
        mysql.connection.commit()
        cursor.close()

        flash("Custom category created 🎉", "success")
        return redirect(url_for("dashboard"))

    return render_template("create_category.html")

@app.route("/delete_category/<int:category_id>")
def delete_category(category_id):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM categories WHERE category_id=%s AND is_custom=1", (category_id,))
    mysql.connection.commit()
    cursor.close()

    flash("Custom category deleted 🗑️", "danger")
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)"""




















#-----------------------------------------------------------------------------------------------------------------------

"""from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
	return render_template("login_page(final).html")

@app.route("/create_account")
def create_account():
	return render_template("create_acc_page(final).html")	


if __name__ == "__main__":
	app.run(debug = True)"""