from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import MySQLdb.cursors
from datetime import datetime, date
import re

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
        is_custom TINYINT(1) DEFAULT 0,
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
    #print("Tables created/verified.")

with app.app_context():
    try:
        create_tables_and_seed()
    except Exception as e:
        print("Warning (DB init failed):", e)


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
    #print("Default categories & habits seeded.")


# Run DB setup + seeding
with app.app_context():
    try:
        create_tables_and_seed()
        seed_default_habits()
    except Exception as e:
        print("Warning (DB init/seed failed):", e)


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
    errors = {}
    data = request.form
    today = date.today()

    if request.method == "POST":
        # Convert form to dictionary safely
        data = request.form.to_dict()

        # -------------------------
        # First Name validation
        # -------------------------
        first_name = data.get("first_name", "").strip()
        if not first_name:
            errors["first_name"] = "Required field*"
        elif not re.match("^[A-Za-z]+$", first_name):
            errors["first_name"] = "Only alphabets are allowed*"    
        elif len(first_name) < 3:
            errors["first_name"] = "Minimum 3 characters required*"
        elif len(first_name) > 20:
            errors["first_name"] = "Maximum 20 characters allowed*"

        # -------------------------
        # Last Name validation
        # -------------------------
        last_name = data.get("last_name", "").strip()
        if not last_name:
            errors["last_name"] = "Required field*"
        elif not re.match("^[A-Za-z]+$", last_name):
            errors["last_name"] = "Only alphabets are allowed*"    
        elif len(last_name) < 3:
            errors["last_name"] = "Minimum 3 characters required*"
        elif len(last_name) > 20:
            errors["last_name"] = "Maximum 20 characters allowed*"

        # -------------------------
        # Username validation
        # -------------------------
        username = data.get("username", "").strip()
        if len(username) < 5 or len(username) > 20:
            errors["username"] = "Username should range in between 5-20 characters*"
        elif not re.match("^[A-Za-z0-9]+$", username):
            errors["username"] = "Only alphabets and numeral values are allowed*"
        elif not (re.search("[A-Za-z]", username) and re.search("[0-9]", username)):
            errors["username"] = "Username should be alphanumeric"
        else:
            # Check uniqueness in DB
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            existing_user = cursor.fetchone()
            cursor.close()
            if existing_user:
                errors["username"] = "Username already taken"


        # -------------------------
        # DOB validation
        # -------------------------
        dob = data.get("dob", "").strip()

        if not dob:
            errors["dob"] = "Required field*"
        else:
            try:
                entered_date = datetime.strptime(dob, "%Y-%m-%d").date()
            except ValueError:
                errors["dob"] = "Invalid date format"
            else:
                if entered_date.year > today.year:
                    errors["dob"] = f"Year cannot be beyond {today.year}"
                elif entered_date > today:
                    errors["dob"] = "Date cannot be in the future"

        # -------------------------
        # Gender validation
        # -------------------------
        gender = data.get("gender", "").strip()
        if not gender:
            errors["gender"] = "Required field*"

        # -------------------------
        # Mobile validation
        # -------------------------
        mobile = data.get("mobile", "").strip()

        if not mobile:
            errors["mobile"] = "Required field*"

        elif not re.fullmatch(r"^[6-9][0-9]{9}$", mobile):
            errors["mobile"] = "Invalid Mobile No. Must be 10 digits & start with 6-9"
            

        # -------------------------
        # Email validation
        # -------------------------
        email = data.get("email", "").strip()
        if not email:
            errors["email"] = "Required field*"

        # -------------------------
        # Password validation
        # -------------------------
        password = data.get("password", "").strip()
        if not password:
            errors["password"] = "Required field*"

        # -------------------------
        # If errors → return form with errors
        # -------------------------
        if errors:
            return render_template(
                "create_acc.html",
                data=data,
                errors=errors,
                today_date=today.strftime("%Y-%m-%d")
            )

        # -------------------------
        # If no errors → insert into DB
        # -------------------------
        hashed_password = generate_password_hash(password)

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO users(first_name, last_name, username, dob, gender, mobile, email, password)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            first_name.capitalize(),
            last_name.capitalize(),
            username,
            dob,
            gender,
            mobile,
            email,
            hashed_password
        ))
        mysql.connection.commit()
        cursor.close()

        flash("Account created successfully", "success")
        return redirect(url_for("home"))

    # -------------------------
    # GET request → empty form
    today_date = date.today().isoformat()
    return render_template(
        "create_acc.html", 
        data=data if data else {},
        errors=errors if errors else {},
        today_date=today.strftime("%Y-%m-%d")
    )


#----------------------------
# Check Username
#----------------------------

@app.route("/check_username", methods=["POST"])
def check_username():
    username = request.form.get("username", "").strip()
    response = {"status": "ok", "message": ""}

    if len(username) < 5 or len(username) > 20:
        response["status"] = "error"
        response["message"] = "Username should range in between 5-20 characters"
    elif not re.match("^[A-Za-z0-9]+$", username):
        response["status"] = "error"
        response["message"] = "Only alphabets and numeral values are allowed"
    elif len(re.findall(r'\d', username)) < 2:
        response["status"] = "error"
        response["message"] = "Username should be alphanumeric"
    else:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()
        cursor.close()
        if existing_user:
            response["status"] = "error"
            response["message"] = "Username already taken"

    return jsonify(response)


# ---------------------------
# Login
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error_username = ""
    error_password = ""

    if request.method == "POST":
        email_or_username = request.form.get("email_or_username", "").strip()
        password = request.form.get("password", "").strip()

        # Inline validation for empty fields
        if not email_or_username:
            error_username = "Required field*"
        if not password:
            error_password = "Required field*"

        if error_username or error_password:
            return render_template("login.html",error_username=error_username,error_password=error_password)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT * FROM users WHERE email=%s OR username=%s
        """, (email_or_username, email_or_username))
        user = cursor.fetchone()
        cursor.close()

        if not user:
            error_username = "User not found*"
            return render_template("login.html",error_username=error_username,error_password=error_password)

        if not check_password_hash(user['password'], password):
            error_password = "Wrong Password*"
            return render_template("login.html",error_username=error_username,error_password=error_password)

        # Successful login
        session['loggedin'] = True
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        return redirect(url_for("dashboard"))

    return render_template("login.html",error_username=error_username,error_password=error_password)



# ---------------------------
# Dashboard
# ---------------------------
@app.route("/dashboard")
def dashboard():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Predefined categories (shared for all users)
    cursor.execute("SELECT * FROM categories WHERE is_custom=0")
    predefined_categories = cursor.fetchall()

    # Custom categories created by the user
    cursor.execute("SELECT * FROM categories WHERE is_custom=1 AND user_id=%s", (user_id,))
    custom_categories = cursor.fetchall()

    cursor.close()
    return render_template(
        "dashboard.html",
        username=session["username"],
        predefined_categories=predefined_categories,
        custom_categories=custom_categories
    )


#-------------------------------------------------
# Habit Categories Routes
#-------------------------------------------------

@app.route("/health_wellness")
def health_wellness():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", ("Health & Wellness",))
    category = cursor.fetchone()
    if not category:
        cursor.close()
        return "Category 'Health & Wellness' not found in DB"

    category_id = category["category_id"]

    # Fetch habits along with user custom_name if exists
    cursor.execute("""
        SELECT h.habit_id, 
               h.habit_name, 
               ush.custom_name
        FROM habits h
        LEFT JOIN user_selected_habits ush 
            ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.category_id = %s
    """, (user_id, category_id))
    habits = cursor.fetchall()
    cursor.close()

    # Pass the name to display: custom_name if exists, else default habit_name
    for habit in habits:
        habit['display_name'] = habit['custom_name'] if habit['custom_name'] else habit['habit_name']

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

    # Get category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", ("Learning & Growth",))
    category = cursor.fetchone()

    if not category:
        cursor.close()
        return "Category 'Learning & Growth' not found in DB"

    category_id = category["category_id"]

    # Fetch habits along with user custom_name if exists
    cursor.execute("""
        SELECT h.habit_id, 
               h.habit_name, 
               ush.custom_name
        FROM habits h
        LEFT JOIN user_selected_habits ush 
            ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.category_id = %s
    """, (user_id, category_id))
    habits = cursor.fetchall()
    cursor.close()

    # Pass the name to display: custom_name if exists, else default habit_name
    for habit in habits:
        habit['display_name'] = habit['custom_name'] if habit['custom_name'] else habit['habit_name']

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

    # Get category_id
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", ("Productivity",))
    category = cursor.fetchone()

    if not category:
        cursor.close()
        return "Category 'Productivity' not found in DB"

    category_id = category["category_id"]

    # Fetch habits along with user custom_name if exists
    cursor.execute("""
        SELECT h.habit_id, 
               h.habit_name, 
               ush.custom_name
        FROM habits h
        LEFT JOIN user_selected_habits ush 
            ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.category_id = %s
    """, (user_id, category_id))
    habits = cursor.fetchall()
    cursor.close()

    # Pass the name to display: custom_name if exists, else default habit_name
    for habit in habits:
        habit['display_name'] = habit['custom_name'] if habit['custom_name'] else habit['habit_name']

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

    # Fetch habits along with user custom_name if exists
    cursor.execute("""
        SELECT h.habit_id, 
               h.habit_name, 
               ush.custom_name
        FROM habits h
        LEFT JOIN user_selected_habits ush 
            ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.category_id = %s
    """, (user_id, category_id))
    habits = cursor.fetchall()
    cursor.close()

    # Pass the name to display: custom_name if exists, else default habit_name
    for habit in habits:
        habit['display_name'] = habit['custom_name'] if habit['custom_name'] else habit['habit_name']

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
    
    # Fetch habits along with user custom_name if exists
    cursor.execute("""
        SELECT h.habit_id, 
               h.habit_name, 
               ush.custom_name
        FROM habits h
        LEFT JOIN user_selected_habits ush 
            ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.category_id = %s
    """, (user_id, category_id))
    habits = cursor.fetchall()
    cursor.close()

    # Pass the name to display: custom_name if exists, else default habit_name
    for habit in habits:
        habit['display_name'] = habit['custom_name'] if habit['custom_name'] else habit['habit_name']

    return render_template(
        "personal_lifestyle.html",
        username=session["username"],
        habits=habits
    )



# ---------------------------
# Add Predefined Habit
# ---------------------------
@app.route("/add_habit/<int:habit_id>", methods=["POST"])
def add_habit(habit_id):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor()

    # Insert into user_selected_habits (if not already added)
    cursor.execute("""
        SELECT * FROM user_selected_habits WHERE user_id=%s AND habit_id=%s
    """, (user_id, habit_id))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute("""
            INSERT INTO user_selected_habits (user_id, habit_id, date_added)
            VALUES (%s, %s, CURDATE())
        """, (user_id, habit_id))
        mysql.connection.commit()

    cursor.close()
    flash("Habit added successfully", "success")
    return redirect(request.referrer)


# ---------------------------
# Add Custom Habit
# ---------------------------
@app.route("/add_custom_habit/<string:category_name>", methods=["POST"])
def add_custom_habit(category_name):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    habit_name = request.form["habit_name"]

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get category_id for this category
    cursor.execute("SELECT category_id FROM categories WHERE category_name=%s", (category_name,))
    category = cursor.fetchone()
    if not category:
        cursor.close()
        flash("Category not found", "danger")
        return redirect(request.referrer)

    category_id = category["category_id"]

    # Insert into habits (custom habit)
    cursor.execute("""
        INSERT INTO habits (category_id, user_id, habit_name, is_custom, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (category_id, user_id, habit_name, True, True))
    mysql.connection.commit()
    habit_id = cursor.lastrowid

    # Insert into user_selected_habits
    cursor.execute("""
        INSERT INTO user_selected_habits (user_id, habit_id, date_added, custom_name)
        VALUES (%s, %s, CURDATE(), %s)
    """, (user_id, habit_id, habit_name))
    mysql.connection.commit()

    cursor.close()
    flash("Custom habit added", "success")
    return redirect(request.referrer)


# ---------------------------
# My Habits Page
# ---------------------------
@app.route("/my_habits")
def my_habits():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch all user-selected habits (predefined + custom)
    cursor.execute("""
        SELECT ush.entry_id,
               h.habit_id, 
               h.habit_name, 
               ush.custom_name, 
               c.category_name, 
               ush.date_added
        FROM user_selected_habits ush
        JOIN habits h ON ush.habit_id = h.habit_id
        JOIN categories c ON h.category_id = c.category_id
        WHERE ush.user_id = %s
        ORDER BY ush.date_added DESC
    """, (user_id,))
    user_habits = cursor.fetchall()

    cursor.close()

    return render_template(
        "my_habits.html", 
        username=session["username"], 
        habits=user_habits,
        today=date.today().strftime("%d %B, %Y") 
    )



#----------------------------
# Edit Habits
#----------------------------
@app.route("/edit_habit", methods=["POST"])
def edit_habit():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    habit_id = request.form["habit_id"]
    custom_name = request.form["custom_name"]

    cursor = mysql.connection.cursor()

    # Check if the habit is already in user_selected_habits
    cursor.execute("""
        SELECT entry_id FROM user_selected_habits 
        WHERE user_id=%s AND habit_id=%s
    """, (user_id, habit_id))
    entry = cursor.fetchone()

    if entry:
        # Update custom_name if already added
        cursor.execute("""
            UPDATE user_selected_habits
            SET custom_name=%s
            WHERE user_id=%s AND habit_id=%s
        """, (custom_name, user_id, habit_id))
    else:
        # Insert into user_selected_habits with custom name
        cursor.execute("""
            INSERT INTO user_selected_habits (user_id, habit_id, date_added, custom_name)
            VALUES (%s, %s, CURDATE(), %s)
        """, (user_id, habit_id, custom_name))

    mysql.connection.commit()
    cursor.close()

    flash("Habit edited successfully", "success")
    return redirect(request.referrer)


#----------------------------
# Remove Habits
#----------------------------
@app.route('/remove_habit/<int:habit_id>', methods=['POST'])
def remove_habit(habit_id):
    cursor = mysql.connection.cursor()

    # Step 1: Remove from user_selected_habits (always do this)
    cursor.execute("""
        DELETE FROM user_selected_habits 
        WHERE habit_id = %s AND user_id = %s
    """, (habit_id, session['user_id']))

    # Step 2: Check if it's a custom habit created by this user
    cursor.execute("""
        SELECT is_custom, user_id 
        FROM habits 
        WHERE habit_id = %s
    """, (habit_id,))
    habit = cursor.fetchone()

    if habit and habit[0] == 1 and habit[1] == session['user_id']:  
        # habit[0] → is_custom (1 if custom)  
        # habit[1] → user_id (who created it)  
        cursor.execute("DELETE FROM habits WHERE habit_id = %s", (habit_id,))

    mysql.connection.commit()
    cursor.close()

    flash("Habit removed successfully", "success")
    return redirect(url_for('my_habits'))

#----------------------------
# Create category
#----------------------------
@app.route("/create_category", methods=["POST"])
def create_category():
    if "loggedin" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    data = request.get_json()
    if not data or not data.get("category_name"):
        return jsonify({"success": False, "message": "Category name is required"}), 400

    category_name = data["category_name"].strip()
    user_id = session["user_id"]

    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO categories (category_name, is_custom, user_id)
        VALUES (%s, %s, %s)
    """, (category_name, True, user_id))
    mysql.connection.commit()
    category_id = cursor.lastrowid
    cursor.close()

    return jsonify({
        "success": True,
        "url": url_for("open_custom_category", category_id=category_id)
    })


#----------------------------
# Route to open custom category page
#----------------------------
@app.route("/custom_category/<int:category_id>")
def open_custom_category(category_id):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Verify category belongs to user
    cursor.execute("""
        SELECT * FROM categories 
        WHERE category_id=%s AND user_id=%s AND is_custom=1
    """, (category_id, user_id))
    category = cursor.fetchone()
    if not category:
        cursor.close()
        return "Category not found or not authorized"

    # Fetch habits of this category
    cursor.execute("""
        SELECT h.habit_id, h.habit_name, ush.custom_name
        FROM habits h
        LEFT JOIN user_selected_habits ush
            ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.category_id = %s
    """, (user_id, category_id))
    habits = cursor.fetchall()
    cursor.close()

    for habit in habits:
        habit["display_name"] = habit["custom_name"] if habit["custom_name"] else habit["habit_name"]

    return render_template("custom_category.html",
                           category=category,
                           habits=habits,
                           username=session["username"])


#----------------------------
#Add habit in custom category
#----------------------------
@app.route("/add_custom_category_habit/<int:category_id>", methods=["POST"])
def add_custom_category_habit(category_id):
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    habit_name = request.form["habit_name"]

    cursor = mysql.connection.cursor()

    # Insert into habits
    cursor.execute("""
        INSERT INTO habits (category_id, user_id, habit_name, is_custom, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (category_id, user_id, habit_name, True, True))
    mysql.connection.commit()
    habit_id = cursor.lastrowid

    # Insert into user_selected_habits
    cursor.execute("""
        INSERT INTO user_selected_habits (user_id, habit_id, date_added, custom_name)
        VALUES (%s, %s, CURDATE(), %s)
    """, (user_id, habit_id, habit_name))
    mysql.connection.commit()

    cursor.close()
    flash("Habit added successfully", "success")
    return redirect(url_for("open_custom_category", category_id=category_id))

#----------------------------
# profile
#----------------------------

@app.route("/profile")
def profile():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT username, first_name, last_name, mobile, dob, email FROM users WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()

    return render_template("profile.html", user=user)


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    first_name = request.form["first_name"]
    last_name = request.form["last_name"]
    mobile = request.form["mobile"]
    dob = request.form["dob"]
    email = request.form["email"]

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users 
        SET first_name=%s, last_name=%s, mobile=%s, dob=%s, email=%s 
        WHERE user_id=%s
    """, (first_name, last_name, mobile, dob, email, user_id))
    mysql.connection.commit()
    cursor.close()

    flash("Profile updated successfully", "success")
    return redirect(url_for("profile"))

#----------------------------
# About Us
#----------------------------
@app.route("/about_us")
def about_us():
    username = session.get('username', 'Guest')
    return render_template("about_us.html", username=username)


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