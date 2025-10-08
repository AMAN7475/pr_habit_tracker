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

    # daily_task_status table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_task_status (
        task_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        habit_id INT NOT NULL,
        everyday_date DATE NOT NULL,
        status ENUM('Completed', 'Missed', 'Skipped', 'Pending') DEFAULT 'Pending',
        marked_time DATETIME DEFAULT NULL,
        UNIQUE KEY unique_user_habit_date (user_id, habit_id, everyday_date),
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
    data = {}
    today = date.today()

    if request.method == "POST":
        # Convert form to dictionary safely
        data = request.form.to_dict()

        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()

        # Ensure first letter uppercase, rest lowercase
        first_name = first_name.capitalize()
        last_name = last_name.capitalize()
        data["first_name"] = first_name
        data["last_name"] = last_name
        
        #--------------------------
        # First Name Validation
        #--------------------------
        name_pattern = r"^[A-Z][a-z]{2,19}$"  # 1 uppercase + 2–19 lowercase only

        if not first_name:
            errors["first_name"] = "Required field*"
        elif not re.match("^[A-Za-z]+$", first_name):
            errors["first_name"] = "Only alphabets are allowed*"
        elif not re.match(name_pattern, first_name):
            if len(first_name) < 3:
                errors["first_name"] = "Minimum 3 characters required*"
            else:
                errors["first_name"] = "First letter must be uppercase, rest lowercase*"
        elif re.fullmatch(r"^[A-Z](.)\1+$", first_name):  # repeated letters check
            errors["first_name"] = "Repeated letters are not allowed*"
            
        #--------------------------
        # Last Name Validation
        #--------------------------

        if not last_name:
            errors["last_name"] = "Required field*"
        elif not re.match("^[A-Za-z]+$", last_name):
            errors["last_name"] = "Only alphabets are allowed*"
        elif not re.match(name_pattern, last_name):
            if len(last_name) < 3:
                errors["last_name"] = "Minimum 3 characters required*"
            else:
                errors["last_name"] = "First letter must be uppercase, rest lowercase*"
        elif re.fullmatch(r"^[A-Z](.)\1+$", last_name):  # repeated letters check
            errors["last_name"] = "Repeated letters are not allowed*"

        # -------------------------
        # Username validation
        # -------------------------
        username = data.get("username", "").strip()
        if len(username) < 5 or len(username) > 20:
            errors["username"] = "Username length must be in between 5-20 characters*"
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
                    errors["dob"] = f"DOB cannot be in the future* (max {mm}/{dd}/{yyyy})"
                elif entered_date > today:
                    # Convert max allowed date to mm/dd/yyyy format for error message
                    mm = str(today.month).zfill(2)
                    dd = str(today.day).zfill(2)
                    yyyy = today.year
                    errors["dob"] = f"Date cannot be in the future* (max {mm}/{dd}/{yyyy})"

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
        email = request.form.get("email", "").strip()
        if email:
            allowed_domains = (
                "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
                "icloud.com", "live.com", "aol.com", "protonmail.com",
                "zoho.com", "rediffmail.com"
            )

            # General pattern
            pattern = r'^[a-z0-9._]{5,}@(' + '|'.join(re.escape(d) for d in allowed_domains) + r')$'
            if not re.match(pattern, email):
                errors["email"] = (
                    "Invalid email format. Use lowercase letters, numbers, '.', or '_'. "
                    "At least 5 characters before @, and domain must be common (e.g., gmail.com)."
                )
            else:
                username = email.split('@')[0]
                # Check if all characters are the same (e.g., aaaaa, 11111)
                if re.fullmatch(r'(.)\1+', username):
                    errors["email"] = "Username part cannot have all repeated characters."
        else:
            errors["email"] = "Required field*"


        # -------------------------
        # Password validation
        # -------------------------
        password = data.get("password", "").strip()

        if not password:
            errors["password"] = "Required field*"
        else:
            # Length validation first
            if len(password) < 8 or len(password) > 30:
                errors["password"] = "Password must contain at least one uppercase letter, one number and one special character. And Password length must be in between 8 to 30 characters*"

            # Complexity validation (uppercase + number + special char)
            elif not re.search(r"[A-Z]", password) or not re.search(r"\d", password) or not re.search(r"[!@#$%^&*]",password):
                errors["password"] = "Password must contain at least one uppercase letter, one number and one special character. And Password length must be in between 8 to 30 characters*"

            # Optional full pattern validation (if you want to enforce all at once)
            elif not re.fullmatch(r"^[A-Za-z\d!@#$%^&*]{8,30}$", password):
                errors["password"] = "Invalid password format*"


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
            first_name,
            last_name,
            username,
            dob,
            gender,
            mobile,
            email,
            hashed_password
        ))
        mysql.connection.commit()
        cursor.close()

        flash("Account Created Successfully!", "success")
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
#-------------------------------------------------
# Health and Wellness
#-------------------------------------------------

@app.route("/health_wellness")
def health_wellness():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get category_id
    cursor.execute(
        "SELECT category_id FROM categories WHERE category_name = %s",
        ("Health & Wellness",)
    )
    category = cursor.fetchone()
    if not category:
        cursor.close()
        return "Category 'Health & Wellness' not found in DB"

    category_id = category["category_id"]

    # Fetch all habits
    cursor.execute("""
        SELECT h.habit_id,
               h.habit_name,
               ush.custom_name,
               CASE 
                   WHEN ush.habit_id IS NOT NULL THEN 1 
                   ELSE 0 
               END AS in_user_habits
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
        habit['added'] = habit['in_user_habits']  # 1 if added, 0 if not

    return render_template(
        "health_wellness.html",
        username=session["username"],
        habits=habits,
        category=category
    )


#-------------------------------------------------
# Remove Button for Health & Wellness
#-------------------------------------------------

@app.route("/remove_health_habit/<int:habit_id>", methods=["POST"])
def remove_health_habit(habit_id):
    if "loggedin" not in session:
        flash("Not logged in", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch habit info
    cursor.execute("""
        SELECT * FROM habits h
        LEFT JOIN user_selected_habits ush
        ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.habit_id = %s
    """, (user_id, habit_id))
    habit = cursor.fetchone()

    if not habit:
        cursor.close()
        flash("Habit not found", "error")
        return redirect(url_for("health_wellness"))

    # Case 1: Custom habit
    if habit["is_custom"]:
        # Delete from user_selected_habits and habits
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        cursor.execute("DELETE FROM habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Custom habit removed successfully"

    # Case 2: Predefined habit edited
    elif habit.get("custom_name"):
        # Remove from user habits & reset edited name
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit Reverted to predefined one."

    # Case 3: Predefined habit untouched
    else:
        # Remove from user habits only
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit removed from my habits"

    mysql.connection.commit()
    cursor.close()

    flash(message, "success")
    return redirect(url_for("health_wellness"))



#-------------------------------------------------
# Learning and Growth
#-------------------------------------------------


@app.route("/learning_growth")
def learning_growth():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get category_id
    cursor.execute(
        "SELECT category_id FROM categories WHERE category_name = %s",
        ("Learning & Growth",)
    )
    category = cursor.fetchone()
    if not category:
        cursor.close()
        return "Category 'Learning & Growth' not found in DB"

    category_id = category["category_id"]

    # Fetch all habits
    cursor.execute("""
        SELECT h.habit_id,
               h.habit_name,
               ush.custom_name,
               CASE 
                   WHEN ush.habit_id IS NOT NULL THEN 1 
                   ELSE 0 
               END AS in_user_habits
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
        habit['added'] = habit['in_user_habits']  # 1 if added, 0 if not

    return render_template(
        "learning_growth.html",
        username=session["username"],
        habits=habits,
        category=category
    )

#-------------------------------------------------
# Remove Button for Learning & Growth
#-------------------------------------------------

@app.route("/remove_learning_habit/<int:habit_id>", methods=["POST"])
def remove_learning_habit(habit_id):
    if "loggedin" not in session:
        flash("Not logged in", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch habit info
    cursor.execute("""
        SELECT * FROM habits h
        LEFT JOIN user_selected_habits ush
        ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.habit_id = %s
    """, (user_id, habit_id))
    habit = cursor.fetchone()

    if not habit:
        cursor.close()
        flash("Habit not found", "error")
        return redirect(url_for("learning_growth"))

    # Case 1: Custom habit
    if habit["is_custom"]:
        # Delete from user_selected_habits and habits
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        cursor.execute("DELETE FROM habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Custom habit removed successfully"

    # Case 2: Predefined habit edited
    elif habit.get("custom_name"):
        # Remove from user habits & reset edited name
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit Reverted to predefined one."

    # Case 3: Predefined habit untouched
    else:
        # Remove from user habits only
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit removed from my habits"

    mysql.connection.commit()
    cursor.close()

    flash(message, "success")
    return redirect(url_for("learning_growth"))



#-------------------------------------------------
# Productivity
#-------------------------------------------------


@app.route("/productivity")
def productivity():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get category_id
    cursor.execute(
        "SELECT category_id FROM categories WHERE category_name = %s",
        ("Productivity",)
    )
    category = cursor.fetchone()
    if not category:
        cursor.close()
        return "Category 'Productivity' not found in DB"

    category_id = category["category_id"]

    # Fetch all habits
    cursor.execute("""
        SELECT h.habit_id,
               h.habit_name,
               ush.custom_name,
               CASE 
                   WHEN ush.habit_id IS NOT NULL THEN 1 
                   ELSE 0 
               END AS in_user_habits
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
        habit['added'] = habit['in_user_habits']  # 1 if added, 0 if not

    return render_template(
        "productivity.html",
        username=session["username"],
        habits=habits,
        category=category
    )


#-------------------------------------------------
# Remove Button for Productivity
#-------------------------------------------------

@app.route("/remove_productivity_habit/<int:habit_id>", methods=["POST"])
def remove_productivity_habit(habit_id):
    if "loggedin" not in session:
        flash("Not logged in", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch habit info
    cursor.execute("""
        SELECT * FROM habits h
        LEFT JOIN user_selected_habits ush
        ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.habit_id = %s
    """, (user_id, habit_id))
    habit = cursor.fetchone()

    if not habit:
        cursor.close()
        flash("Habit not found", "error")
        return redirect(url_for("productivity"))

    # Case 1: Custom habit
    if habit["is_custom"]:
        # Delete from user_selected_habits and habits
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        cursor.execute("DELETE FROM habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Custom habit removed successfully"

    # Case 2: Predefined habit edited
    elif habit.get("custom_name"):
        # Remove from user habits & reset edited name
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit Reverted to predefined one."

    # Case 3: Predefined habit untouched
    else:
        # Remove from user habits only
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit removed from my habits"

    mysql.connection.commit()
    cursor.close()

    flash(message, "success")
    return redirect(url_for("productivity"))

#-------------------------------------------------
# Finance & Discipline
#-------------------------------------------------


@app.route("/finance_discipline")
def finance_discipline():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get category_id
    cursor.execute(
        "SELECT category_id FROM categories WHERE category_name = %s",
        ("Finance & Discipline",)
    )
    category = cursor.fetchone()
    if not category:
        cursor.close()
        return "Category 'Finance & Discipline' not found in DB"

    category_id = category["category_id"]

    # Fetch all habits
    cursor.execute("""
        SELECT h.habit_id,
               h.habit_name,
               ush.custom_name,
               CASE 
                   WHEN ush.habit_id IS NOT NULL THEN 1 
                   ELSE 0 
               END AS in_user_habits
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
        habit['added'] = habit['in_user_habits']  # 1 if added, 0 if not

    return render_template(
        "finance_discipline.html",
        username=session["username"],
        habits=habits,
        category=category
    )


#-------------------------------------------------
# Remove Button for Finance & Discipline
#-------------------------------------------------

@app.route("/remove_finance_habit/<int:habit_id>", methods=["POST"])
def remove_finance_habit(habit_id):
    if "loggedin" not in session:
        flash("Not logged in", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch habit info
    cursor.execute("""
        SELECT * FROM habits h
        LEFT JOIN user_selected_habits ush
        ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.habit_id = %s
    """, (user_id, habit_id))
    habit = cursor.fetchone()

    if not habit:
        cursor.close()
        flash("Habit not found", "error")
        return redirect(url_for("finance_discipline"))

    # Case 1: Custom habit
    if habit["is_custom"]:
        # Delete from user_selected_habits and habits
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        cursor.execute("DELETE FROM habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Custom habit removed successfully"

    # Case 2: Predefined habit edited
    elif habit.get("custom_name"):
        # Remove from user habits & reset edited name
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit Reverted to predefined one."

    # Case 3: Predefined habit untouched
    else:
        # Remove from user habits only
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit removed from my habits"

    mysql.connection.commit()
    cursor.close()

    flash(message, "success")
    return redirect(url_for("finance_discipline"))

#-------------------------------------------------
# Personal & Lifestyle
#-------------------------------------------------


@app.route("/personal_lifestyle")
def personal_lifestyle():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get category_id
    cursor.execute(
        "SELECT category_id FROM categories WHERE category_name = %s",
        ("Personal & Lifestyle",)
    )
    category = cursor.fetchone()
    if not category:
        cursor.close()
        return "Category 'Personal & Lifestyle' not found in DB"

    category_id = category["category_id"]

    # Fetch all habits
    cursor.execute("""
        SELECT h.habit_id,
               h.habit_name,
               ush.custom_name,
               CASE 
                   WHEN ush.habit_id IS NOT NULL THEN 1 
                   ELSE 0 
               END AS in_user_habits
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
        habit['added'] = habit['in_user_habits']  # 1 if added, 0 if not

    return render_template(
        "personal_lifestyle.html",
        username=session["username"],
        habits=habits,
        category=category
    )


#-------------------------------------------------
# Remove Button for Personal & Lifestyle
#-------------------------------------------------

@app.route("/remove_lifestyle_habit/<int:habit_id>", methods=["POST"])
def remove_lifestyle_habit(habit_id):
    if "loggedin" not in session:
        flash("Not logged in", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch habit info
    cursor.execute("""
        SELECT * FROM habits h
        LEFT JOIN user_selected_habits ush
        ON h.habit_id = ush.habit_id AND ush.user_id = %s
        WHERE h.habit_id = %s
    """, (user_id, habit_id))
    habit = cursor.fetchone()

    if not habit:
        cursor.close()
        flash("Habit not found", "error")
        return redirect(url_for("personal_lifestyle"))

    # Case 1: Custom habit
    if habit["is_custom"]:
        # Delete from user_selected_habits and habits
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        cursor.execute("DELETE FROM habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Custom habit removed successfully"

    # Case 2: Predefined habit edited
    elif habit.get("custom_name"):
        # Remove from user habits & reset edited name
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit Reverted to predefined one."

    # Case 3: Predefined habit untouched
    else:
        # Remove from user habits only
        cursor.execute("DELETE FROM user_selected_habits WHERE habit_id=%s AND user_id=%s", (habit_id, user_id))
        message = "Habit removed from my habits"

    mysql.connection.commit()
    cursor.close()

    flash(message, "success")
    return redirect(url_for("personal_lifestyle"))


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
    flash("Custom habit added successfully", "success")
    return redirect(request.referrer)


# ---------------------------
# My Habits Page 
# ---------------------------
@app.route("/my_habits")
def my_habits():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    today = date.today()

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # STEP 1: Fetch all user-selected habits (predefined + custom)
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

    # STEP 2: Ensure today's records exist in daily_task_status
    for habit in user_habits:
        habit_id = habit["habit_id"]

        cursor.execute("""
            SELECT * FROM daily_task_status
            WHERE user_id = %s AND habit_id = %s AND everyday_date = %s
        """, (user_id, habit_id, today))
        existing = cursor.fetchone()

        if not existing:
            cursor.execute("""
                INSERT INTO daily_task_status (user_id, habit_id, everyday_date, status)
                VALUES (%s, %s, %s, 'Pending')
            """, (user_id, habit_id, today))
            mysql.connection.commit()

    # STEP 3: Fetch habits with today's daily status
    cursor.execute("""
        SELECT h.habit_id,
               h.habit_name,
               ush.custom_name,
               c.category_name,
               dts.status 
        FROM user_selected_habits ush
        JOIN habits h ON ush.habit_id = h.habit_id
        JOIN categories c ON h.category_id = c.category_id
        JOIN daily_task_status dts 
          ON dts.habit_id = h.habit_id 
         AND dts.user_id = ush.user_id
         AND dts.everyday_date = %s
        WHERE ush.user_id = %s
        ORDER BY ush.date_added DESC
    """, (today, user_id))
    habits_with_status = cursor.fetchall()

    cursor.close()

    return render_template(
        "my_habits.html",
        username=session["username"],
        habits=habits_with_status,
        today=today.strftime("%d %B, %Y")
    )

# ---------------------------
# Update Habit Status (AJAX)
# ---------------------------
@app.route("/update_habit_status", methods=["POST"])
def update_habit_status():
    if "loggedin" not in session:
        return jsonify(success=False, message="Not logged in"), 401

    data = request.get_json()
    habit_id = data.get("habit_id")
    status = data.get("status")
    user_id = session["user_id"]

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE daily_task_status
        SET status = %s, marked_time = NOW()
        WHERE user_id = %s AND habit_id = %s AND everyday_date = CURDATE()
    """, ("Completed", user_id, habit_id))
    mysql.connection.commit()
    cursor.close()

    return jsonify(success=True, message=f"Status updated to {status}")


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

    flash("Habit edited and added successfully", "success")
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
# Remove habit from custom category
#----------------------------
@app.route("/remove_custom_habit/<int:category_id>/<int:habit_id>", methods=["POST"])
def remove_custom_habit(category_id, habit_id):
    if "loggedin" not in session:
        flash("Not logged in", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor()

    # Verify habit belongs to user & category
    cursor.execute("""
        SELECT * FROM habits 
        WHERE habit_id=%s AND category_id=%s AND user_id=%s AND is_custom=1
    """, (habit_id, category_id, user_id))
    habit = cursor.fetchone()

    if not habit:
        cursor.close()
        flash("Habit not found or unauthorized", "error")
        return redirect(url_for("open_custom_category", category_id=category_id))

    # Delete from user_selected_habits
    cursor.execute("""
        DELETE FROM user_selected_habits 
        WHERE habit_id=%s AND user_id=%s
    """, (habit_id, user_id))

    # Delete from habits
    cursor.execute("""
        DELETE FROM habits 
        WHERE habit_id=%s AND user_id=%s
    """, (habit_id, user_id))

    mysql.connection.commit()
    cursor.close()

    flash("Habit removed successfully", "success")
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

    errors = {}
    current_date = date.today().isoformat()

    return render_template("profile.html", user=user, errors=errors, current_date=current_date)


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "loggedin" not in session:
        return redirect(url_for("login"))

    errors = {}
    user_id = session["user_id"]

    first_name = request.form["first_name"].strip().capitalize()
    last_name = request.form["last_name"].strip().capitalize()
    mobile = request.form["mobile"].strip() 
    dob = request.form["dob"]
    email = request.form["email"].strip().lower()

    # helper values
    current_date = date.today().isoformat()
    name_pattern = r"^[A-Z][a-z]{2,19}$"

    # --- Name validation ---

    repeated_pattern = r"^(.)\1+$"  # matches all same character (like AAAAA or bbbbb)

    if not re.match(name_pattern, first_name):
        if len(first_name) < 3:
            errors["first_name"] = "Minimum 3 characters required*"
        else:
            errors["first_name"] = "Only alphabets are allowed*"
    elif re.match(repeated_pattern, first_name, re.IGNORECASE):
        errors["first_name"] = "Name cannot have all repeated characters*"

    if not re.match(name_pattern, last_name):
        if len(last_name) < 3:
            errors["last_name"] = "Minimum 3 characters required*"
        else:
            errors["last_name"] = "Only alphabets are allowed*"
    elif re.match(repeated_pattern, last_name, re.IGNORECASE):
        errors["last_name"] = "Name cannot have all repeated characters*"

    # --- Mobile validation ---
    mobile_pattern = r"^[6-9][0-9]{9}$"
    if mobile and not re.match(mobile_pattern, mobile):
        errors["mobile"] = "Invalid mobile no. Must be 10 digits and start with 6-9"


    # --- DOB validation ---
    if dob:
        try:
            # Convert input from yyyy-mm-dd (standard HTML date input format) to date object
            dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
            today = date.today()
            if dob_date > today:
                errors["dob"] = f"DOB cannot be in the future (max {today.strftime('%d-%m-%Y')})"
        except ValueError:
            errors["dob"] = "Invalid date format"
    else:
        errors["dob"] = "Date of birth is required"

    
                
    # If validation fails — return profile page with errors
    if errors:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT username, first_name, last_name, mobile, dob, email FROM users WHERE user_id=%s", (user_id,))
        user = cursor.fetchone()
        cursor.close()

        current_date = date.today().isoformat()    
        return render_template("profile.html", user=user, errors=errors, current_date=current_date)


    # If everything is fine — update DB
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


    # --- Email validation ---
    allowed_domains = [
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
        "icloud.com", "live.com", "aol.com", "protonmail.com",
        "zoho.com", "rediffmail.com"
    ]

    # Check pattern (5+ lowercase letters/numbers/._ before @)
    email_pattern = r"^[a-z0-9._]{5,}@[a-z0-9.-]+\.[a-z]{2,}$"

    if not re.match(email_pattern, email):
        errors["email"] = errors["email"] = (
                    "Invalid email format. Use lowercase letters, numbers, '.', or '_'. "
                    "At least 5 characters before @, and domain must be common (e.g., gmail.com)."
                )
    else:
        parts = email.split("@")
        if len(parts) != 2 or parts[1] not in allowed_domains:
            errors["email"] = f"Email must end with one of: {', '.join(allowed_domains)}"
        elif re.match(r"^(.)\1+$", parts[0]):  # repeated characters check
            errors["email"] = "Username part cannot have all repeated characters"


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