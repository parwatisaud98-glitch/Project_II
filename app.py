from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from dbms import cursor, conn
from datetime import date, timedelta
import os
import uuid

app = Flask(__name__)
app.secret_key = "local_services_secret_key"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- HOME ----------------

@app.route("/")
def home():

    # Latest Services
    cursor.execute("""
        SELECT *
        FROM services
        ORDER BY id ASC
        LIMIT 6
    """)
    services = cursor.fetchall()

    # Top Rated Providers
    cursor.execute("""
        SELECT
            users.*,
            ROUND(IFNULL(AVG(reviews.rating),5),1) AS average_rating,
            COUNT(reviews.id) AS total_reviews
        FROM users
        LEFT JOIN reviews
            ON users.id = reviews.provider_id
        WHERE users.role='Service Provider'
        GROUP BY users.id
        ORDER BY average_rating ASC
        LIMIT 6
    """)
    providers = cursor.fetchall()

    # Total Services
    cursor.execute("""
        SELECT COUNT(*) AS total_services
        FROM services
    """)
    service_count = cursor.fetchone()["total_services"]

    # Total Providers
    cursor.execute("""
        SELECT COUNT(*) AS total_providers
        FROM users
        WHERE role='Service Provider'
    """)
    provider_count = cursor.fetchone()["total_providers"]

    # Total Bookings
    cursor.execute("""
        SELECT COUNT(*) AS total_bookings
        FROM bookings
    """)
    booking_count = cursor.fetchone()["total_bookings"]

    return render_template(
        "index.html",
        services=services,
        providers=providers,
        service_count=service_count,
        provider_count=provider_count,
        booking_count=booking_count
    )

# ---------------- ALL SERVICES ----------------

@app.route("/services")
def services():
    cursor.execute("""
        SELECT *
        FROM services
        WHERE status='Available'
        ORDER BY service_name
    """)
    services = cursor.fetchall()
    return render_template(
        "services.html",
        services=services
    )

# ---------------- PROVIDERS SERVICES ----------------

@app.route("/my_services")
def my_services():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") != "Service Provider":
        return redirect("/login")
    cursor.execute("""
        SELECT *
        FROM services
        WHERE provider_id=%s
        ORDER BY id ASC
    """, (session["user_id"],))
    services = cursor.fetchall()
    return render_template(
        "my_services.html",
        services=services,
        show_action=True
    )

# ---------------- PROVIDERS EDIT SERVICES ----------------

@app.route("/provider_edit_service/<int:id>", methods=["GET","POST"])
def provider_edit_service(id):
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute("""
        SELECT *
        FROM services
        WHERE id=%s AND provider_id=%s
    """, (id, session["user_id"]))
    service = cursor.fetchone()
    if not service:
        return "Unauthorized", 403
    if request.method == "POST":
        cursor.execute("""
            UPDATE services
            SET
                service_name=%s,
                category=%s,
                price=%s,
                description=%s
            WHERE id=%s AND provider_id=%s
        """, (
            request.form["service_name"],
            request.form["category"],
            request.form["price"],
            request.form["description"],
            id,
            session["user_id"]
        ))
        conn.commit()
        flash("Service Updated Successfully")
        return redirect("/my_services")
    return render_template("edit_service.html", service=service)

# ---------------- PROVIDERS DELETE SERVICES ----------------

@app.route("/provider_delete_service/<int:id>")
def provider_delete_service(id):
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute("""
        DELETE FROM services
        WHERE id=%s AND provider_id=%s
    """, (id, session["user_id"]))
    conn.commit()
    flash("Service Deleted Successfully")
    return redirect("/my_services")


# ---------------- ABOUT ----------------

@app.route("/about")
def about():
    return render_template("index.html")

# ---------------- ALL PROVIDERS ----------------

@app.route("/providers")
def providers():
    cursor.execute("""
        SELECT *
        FROM users
        WHERE role='Provider'
           OR role='Service Provider'
    """)
    providers = cursor.fetchall()
    return render_template(
        "providers.html",
        providers=providers
    )

# ---------------- REGISTER ----------------

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register_post():
    print("POST WORKING")
    fullname = request.form.get("fullname")
    email = request.form.get("email")
    phone = request.form.get("phone")
    address = request.form.get("address")
    role = request.form.get("role")
    service_name = request.form.get("service_name")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    # Password length
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return redirect("/register")

    # Confirm password
    if password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect("/register")

    # Default image
    filename = ""

    # Upload image only for Service Provider
    if role == "Service Provider":
        file = request.files.get("photo")
        if file and file.filename != "":
            filename = secure_filename(file.filename)
            filename = str(uuid.uuid4()) + "_" + filename
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

    # Check email
    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (email,)
    )
    user = cursor.fetchone()
    if user:
        flash("Email already exists.", "danger")
        return redirect("/register")

    # Insert user
    cursor.execute("""
        INSERT INTO users
        (fullname,email,phone,address,role,service_name,password,image)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        fullname,
        email,
        phone,
        address,
        role,
        service_name,
        password,      # Plain password
        filename
    ))
    conn.commit()
    flash("Registration Successful", "success")
    return redirect("/login")

# ---------------- LOGIN ----------------

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("email")
    password = request.form.get("password")

    # Password length check
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return redirect("/login")

    # Check email
    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (email,)
    )
    user = cursor.fetchone()
    if not user:
        flash("Invalid Email or Password.", "danger")
        return redirect("/login")

    # Plain password check
    if user["password"] != password:
        flash("Invalid Email or Password.", "danger")
        return redirect("/login")

    # Login Success
    session["user_id"] = user["id"]
    session["fullname"] = user["fullname"]
    session["role"] = user["role"]
    flash("Login Successful!", "success")
    if user["role"] == "Customer":
        return redirect("/customer_dashboard")
    elif user["role"] == "Service Provider":
        return redirect("/provider_dashboard")
    elif user["role"] == "Admin":
        return redirect("/admin_dashboard")
    return redirect("/login")

# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    flash("Logout Successful")
    return redirect("/login")

# ---------------- CUSTOMER DASHBOARD ----------------

@app.route("/customer_dashboard")
def customer_dashboard():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    # Logged-in customer
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    # Customer bookings
    sql = """
    SELECT bookings.*,
           users.fullname AS provider_name
    FROM bookings
    JOIN users
        ON bookings.provider_id = users.id
    WHERE bookings.customer_id = %s
    ORDER BY bookings.id ASC
    """
    cursor.execute(sql, (user_id,))
    bookings = cursor.fetchall()
    completed_count = sum(1 for b in bookings if b["status"] == "Completed")
    pending_count = sum(1 for b in bookings if b["status"] == "Pending")
    return render_template(
        "customer_dashboard.html",
        user=user,
        bookings=bookings,
        completed_count=completed_count,
        pending_count=pending_count
    )

# ================= CUSTOMER PROFILE =================

@app.route("/customer_profile")
def customer_profile():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    # Customer Details
    cursor.execute("""
        SELECT *
        FROM users
        WHERE id=%s AND role='Customer'
    """, (user_id,))
    customer = cursor.fetchone()
    if not customer:
        return redirect("/login")

    # Bookings
    cursor.execute("""
        SELECT bookings.*,
               users.fullname AS provider_name
        FROM bookings
        JOIN users
            ON bookings.provider_id = users.id
        WHERE bookings.customer_id=%s
        ORDER BY bookings.id ASC
    """, (user_id,))
    bookings = cursor.fetchall()
    total_bookings = len(bookings)
    completed_count = sum(
        1 for b in bookings
        if b["status"] == "Completed"
    )
    pending_count = sum(
        1 for b in bookings
        if b["status"] == "Pending"
    )
    cancelled_count = sum(
        1 for b in bookings
        if b["status"] == "Cancelled"
    )

    return render_template(
        "customer_profile.html",
        customer=customer,
        bookings=bookings,
        total_bookings=total_bookings,
        completed_count=completed_count,
        pending_count=pending_count,
        cancelled_count=cancelled_count
    )

# ---------------- UPDATE_CUSTOMER_PROFILE ----------------

@app.route("/update_customer_profile", methods=["POST"])
def update_customer_profile():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    fullname = request.form["fullname"]
    email = request.form["email"]
    phone = request.form["phone"]
    address = request.form["address"]
    description = request.form["description"]

    # DEBUG
    print(request.files)
    print(request.files.get("image"))
    
    # Get current image
    cursor.execute("SELECT image FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    image = user["image"]

    # Check if new image uploaded
    if "image" in request.files:

        file = request.files["image"]

        if file and file.filename != "":

            filename = secure_filename(file.filename)

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

            image = filename

    cursor.execute("""
        UPDATE users
        SET
            fullname=%s,
            email=%s,
            phone=%s,
            address=%s,
            description=%s,
            image=%s
        WHERE id=%s
    """, (
        fullname,
        email,
        phone,
        address,
        description,
        image,
        user_id
    ))
    conn.commit()
    flash("Profile Updated Successfully.", "success")
    return redirect("/customer_profile")

# ---------------- CATEGORIES ----------------

@app.route("/categories")
def categories():
    cursor.execute("""
        SELECT services.*,
               users.fullname
        FROM services
        JOIN users
        ON services.provider_id=users.id
        ORDER BY services.category
    """)
    services = cursor.fetchall()

    def count(cat):
        cursor.execute(
            "SELECT COUNT(*) AS total FROM services WHERE category=%s",
            (cat,)
        )
        return cursor.fetchone()["total"]
    return render_template(
        "categories.html",
        services=services,
        electrician_count=count("Electrician"),
        plumber_count=count("Plumber"),
        carpenter_count=count("Carpenter"),
        painter_count=count("Painter"),
        cleaner_count=count("Cleaner"),
        mechanic_count=count("Mechanic"),
        tutor_count=count("Tutor"),
        beauty_count=count("Beauty Service")
    )

# ---------------- FAVOURITES ----------------

@app.route("/favourites")
def favourites():
    if "user_id" not in session:
        return redirect("/login")
    customer_id = session["user_id"]
    cursor.execute("""
    SELECT
        favourites.id,
        users.fullname,
        users.address,
        users.image,
        services.service_name,
        services.category,
        services.price,
        services.image AS service_image,
        services.provider_id
    FROM favourites
    JOIN services
        ON favourites.service_id = services.id
    JOIN users
        ON services.provider_id = users.id
    WHERE favourites.customer_id=%s
    ORDER BY favourites.id ASC
    """,(customer_id,))
    favourites = cursor.fetchall()
    return render_template(
        "favourites.html",
        favourites=favourites
    )

# ---------------- MY_BOOKINGS DASHBOARD ----------------

@app.route("/my_bookings")
def my_bookings():
    if "user_id" not in session:
        return redirect("/login")

    customer_id = session["user_id"]

    sql = """
    SELECT bookings.*, users.fullname AS provider_name
    FROM bookings
    JOIN users ON bookings.provider_id = users.id
    WHERE bookings.customer_id = %s
    ORDER BY bookings.id ASC
    """

    cursor.execute(sql, (customer_id,))
    bookings = cursor.fetchall()

    return render_template(
        "my_bookings.html",
        bookings=bookings
    )

# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "Admin":
        return redirect("/login")

    # Admin information
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )
    admin = cursor.fetchone()

    # Total Customers
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM users
        WHERE role='Customer'
    """)
    total_customers = cursor.fetchone()["total"]

    # Total Providers
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM users
        WHERE role='Service Provider'
    """)
    total_providers = cursor.fetchone()["total"]

    # Total Bookings
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM bookings
    """)
    total_bookings = cursor.fetchone()["total"]

    # Total Revenue
    cursor.execute("""
        SELECT IFNULL(SUM(amount),0) AS revenue
        FROM bookings
    """)
    total_revenue = cursor.fetchone()["revenue"]

    # Recent Bookings
    cursor.execute("""
        SELECT *
        FROM bookings
        ORDER BY id DESC
        LIMIT 5
    """)
    bookings = cursor.fetchall()

    # Pending Providers
    cursor.execute("""
        SELECT *
        FROM users
        WHERE role='Service Provider'
        AND status='Pending'
    """)
    providers = cursor.fetchall()

    # ============================
    # Monthly Bookings (Jan-Dec)
    # ============================
    cursor.execute("""
        SELECT
            MONTH(booking_date) AS month,
            COUNT(*) AS total
        FROM bookings
        WHERE booking_date IS NOT NULL
        GROUP BY MONTH(booking_date)
        ORDER BY MONTH(booking_date)
    """)
    rows = cursor.fetchall()

    monthly_bookings = [0] * 12

    for row in rows:
        if row["month"]:
            monthly_bookings[row["month"] - 1] = row["total"]

    # ============================
    # Service Categories
    # ============================
    cursor.execute("""
        SELECT category,
               COUNT(*) AS total
        FROM services
        GROUP BY category
    """)
    category_result = cursor.fetchall()

    category_labels = []
    category_data = []

    for row in category_result:
        category_labels.append(row["category"])
        category_data.append(row["total"])

    return render_template(
        "admin_dashboard.html",
        admin=admin,
        total_customers=total_customers,
        total_providers=total_providers,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        bookings=bookings,
        providers=providers,
        monthly_bookings=monthly_bookings,
        category_labels=category_labels,
        category_data=category_data
    )

# ---------------- MANAGE CUSTOMERS ----------------

@app.route("/manage_customers")
def manage_customers():
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute("""
    SELECT *
    FROM users
    WHERE role='Customer'
    ORDER BY id ASC
    """)
    customers = cursor.fetchall()
    return render_template(
        "manage_customers.html",
        customers=customers
    )

# ---------------- DELETE CUSTOMER ----------------

@app.route("/delete_customer/<int:id>")
def delete_customer(id):
    cursor.execute(
        "DELETE FROM users WHERE id=%s",
        (id,)
    )
    conn.commit()
    flash("Customer Deleted Successfully")
    return redirect("/manage_customers")

# ---------------- MANAGE PROVIDERS ----------------

@app.route("/manage_providers")
def manage_providers():
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute("""
        SELECT *
        FROM users
        WHERE role='Service Provider'
        ORDER BY id ASC
    """)
    providers = cursor.fetchall()
    return render_template(
        "manage_providers.html",
        providers=providers
    )

# ---------------- APPROVE PROVIDER ----------------

@app.route("/approve_provider/<int:id>")
def approve_provider(id):
    cursor.execute("""
        UPDATE users
        SET status='Approved'
        WHERE id=%s
    """,(id,))
    conn.commit()
    flash("Provider Approved Successfully")
    return redirect("/manage_providers")

# ---------------- REJECT PROVIDER ----------------

@app.route("/reject_provider/<int:id>")
def reject_provider(id):
    cursor.execute("""
        UPDATE users
        SET status='Rejected'
        WHERE id=%s
    """,(id,))
    conn.commit()
    flash("Provider Rejected")
    return redirect("/manage_providers")

# ---------------- DELETE PROVIDER ----------------

@app.route("/delete_provider/<int:id>")
def delete_provider(id):
    cursor.execute("""
        DELETE FROM users
        WHERE id=%s
    """,(id,))
    conn.commit()
    flash("Provider Deleted Successfully")
    return redirect("/manage_providers")

# ---------------- MANAGE SERVICES ----------------

@app.route("/manage_services")
def manage_services():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") != "Admin":
        return redirect("/login")
    cursor.execute("""
        SELECT *
        FROM services
        ORDER BY id ASC
    """)
    services = cursor.fetchall()
    return render_template(
        "my_services.html",
        services=services,
        show_action=True
    )

# ---------------- ADD SERVICE ----------------

@app.route("/add_service")
def add_service():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") not in ["Admin","Service Provider"]:
        return redirect("/login")
    providers = []
    if session.get("role") == "Admin":
        cursor.execute("""
            SELECT id, fullname
            FROM users
            WHERE role='Service Provider'
            ORDER BY fullname
        """)
        providers = cursor.fetchall()
    return render_template(
        "add_service.html",
        providers=providers
    )

@app.route("/add_service", methods=["POST"])
def add_service_post():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") not in ["Admin", "Service Provider"]:
        return redirect("/login")
    if session.get("role") == "Admin":
        provider_id = request.form.get("provider_id")
    else:
        provider_id = session["user_id"]
    service_name = request.form.get("service_name")
    category = request.form.get("category")
    price = request.form.get("price")
    description = request.form.get("description")
    image = request.files.get("image")
    filename = ""
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(
            os.path.join(app.config["UPLOAD_FOLDER"], filename)
        )
    cursor.execute("""
        INSERT INTO services
        (
            provider_id,
            service_name,
            category,
            price,
            description,
            image
        )
        VALUES(%s,%s,%s,%s,%s,%s)
    """, (
        provider_id,
        service_name,
        category,
        price,
        description,
        filename
    ))
    conn.commit()
    flash("Service Added Successfully")
    # Redirect based on role
    if session.get("role") == "Admin":
        return redirect("/manage_services")
    else:
        return redirect("/my_services")

# ---------------- ADMIN ADD SERVICE ----------------

@app.route("/admin_add_service")
def admin_add_service():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") != "Admin":
        return redirect("/login")
    cursor.execute("""
        SELECT id, fullname
        FROM users
        WHERE role='Service Provider'
        ORDER BY fullname
    """)
    providers = cursor.fetchall()
    return render_template(
        "add_service.html",
        providers=providers
    )

@app.route("/admin_add_service", methods=["POST"])
def admin_add_service_post():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") != "Admin":
        return redirect("/login")
    provider_id = request.form.get("provider_id")
    service_name = request.form.get("service_name")
    category = request.form.get("category")
    price = request.form.get("price")
    description = request.form.get("description")
    image = request.files.get("image")
    filename = ""
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    cursor.execute("""
        INSERT INTO services
        (
            provider_id,
            service_name,
            category,
            price,
            description,
            image
        )
        VALUES(%s,%s,%s,%s,%s,%s)
    """,
    (
        provider_id,
        service_name,
        category,
        price,
        description,
        filename
    ))
    conn.commit()
    flash("Service Added Successfully")
    return redirect("/manage_services")

# ---------------- EDIT SERVICE ----------------

@app.route("/edit_service/<int:id>",methods=["GET","POST"])
def edit_service(id):
    if "user_id" not in session:
        return redirect("/login")
    if session["role"] != "Admin":
        return "Unauthorized"
    if request.method=="POST":
        cursor.execute("""
        UPDATE services
        SET
        service_name=%s,
        price=%s,
        description=%s
        WHERE id=%s
        """,
        (
        request.form["service_name"],
        request.form["price"],
        request.form["description"],
        id
        ))
        conn.commit()
        flash("Service Updated")
        return redirect("/manage_services")
    cursor.execute(
    "SELECT * FROM services WHERE id=%s",
    (id,)
    )
    service=cursor.fetchone()
    return render_template(
    "edit_service.html",
    service=service
    )

# ---------------- DELETE SERVICE ----------------

@app.route("/delete_service/<int:id>")
def delete_service(id):
    if "user_id" not in session:
        return redirect("/login")
    if session["role"] != "Admin":
        return "Unauthorized"
    cursor.execute(
    "DELETE FROM services WHERE id=%s",
    (id,)
    )
    conn.commit()
    flash("Service Deleted Successfully")
    return redirect("/manage_services")

# ---------------- MANAGE BOOKINGS ----------------

@app.route("/manage_bookings")
def manage_bookings():
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute("""
    SELECT
    bookings.*,
    c.fullname AS customer_name,
    p.fullname AS provider_name
    FROM bookings
    JOIN users c
    ON bookings.customer_id=c.id
    JOIN users p
    ON bookings.provider_id=p.id
    ORDER BY bookings.id ASC
    """)
    bookings = cursor.fetchall()
    return render_template(
        "manage_bookings.html",
        bookings=bookings
    )

# ---------------- UPDATE BOOKING STATUS ----------------

@app.route("/booking_status/<int:id>/<status>")
def booking_status(id,status):
    cursor.execute("""
    UPDATE bookings
    SET status=%s
    WHERE id=%s
    """,(status,id))
    conn.commit()
    flash("Booking Status Updated Successfully")
    return redirect("/manage_bookings")

# ---------------- DELETE BOOKING ----------------

@app.route("/delete_booking/<int:id>")
def delete_booking(id):
    cursor.execute(
        "DELETE FROM bookings WHERE id=%s",
        (id,)
    )
    conn.commit()
    flash("Booking Deleted Successfully")
    return redirect("/manage_bookings")

# ---------------- ADMIN REVIEWS ----------------

@app.route("/reviews")
def reviews():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "Admin":
        return redirect("/")

    cursor.execute("""
        SELECT
            reviews.id,
            customer.fullname AS customer_name,
            provider.fullname AS provider_name,
            reviews.service_name,
            reviews.rating,
            reviews.review,
            reviews.review_date
        FROM reviews
        LEFT JOIN users AS customer
            ON reviews.customer_id = customer.id
        LEFT JOIN users AS provider
            ON reviews.provider_id = provider.id
        ORDER BY reviews.id ASC
    """)

    reviews = cursor.fetchall()

    return render_template(
        "reviews.html",
        reviews=reviews,
        admin=True,
        review_form=False
    )

# ---------------- PROVIDER REVIEW ----------------

@app.route("/provider_reviews")
def provider_reviews():

    if "user_id" not in session:
        return redirect("/login")

    provider_id = session["user_id"]

    cursor.execute("""
        SELECT
            reviews.id,
            users.fullname AS customer_name,
            reviews.rating,
            reviews.review,
            reviews.review_date
        FROM reviews
        JOIN users
            ON reviews.customer_id = users.id
        WHERE reviews.provider_id=%s
        ORDER BY reviews.id DESC
    """,(provider_id,))

    reviews = cursor.fetchall()

    return render_template(
        "provider_reviews.html",
        reviews=reviews
    )

# ---------------- ADD REVIEW ----------------

@app.route("/add_review/<int:booking_id>", methods=["GET", "POST"])
def add_review():

    if "user_id" not in session:
        return redirect("/login")

    cursor.execute("""
        SELECT *
        FROM bookings
        WHERE id=%s
    """, (booking_id,))

    booking = cursor.fetchone()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect("/customer_dashboard")

    if request.method == "POST":

        rating = request.form.get("rating")
        review = request.form.get("reviews")

        cursor.execute("""
            INSERT INTO reviews
            (
                booking_id,
                provider_id,
                customer_id,
                service_name,
                rating,
                review
            )
            VALUES(%s,%s,%s,%s,%s,%s)
        """,(
            booking_id,
            booking["provider_id"],
            session["user_id"],
            booking["service_name"],
            rating,
            review
        ))

        conn.commit()

        flash("Review Added Successfully", "success")

        return redirect("/customer_dashboard")

    # GET Request
    return render_template(
        "reviews.html",
        booking=booking,
        review_form=True,
        admin=False
    )

# ---------------- DELETE REVIEW ----------------

@app.route("/delete_review/<int:id>")
def delete_review(id):
    cursor.execute(
        "DELETE FROM reviews WHERE id=%s",
        (id,)
    )
    conn.commit()
    flash("Review Deleted Successfully")
    return redirect("/reviews")

# ---------------- PROVIDER BOOKINGS ----------------

@app.route("/provider_bookings")
def provider_bookings():
    if "user_id" not in session:
        return redirect("/login")
    provider_id = session["user_id"]
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (provider_id,)
    )
    provider = cursor.fetchone()
    cursor.execute("""
        SELECT bookings.*, users.fullname AS customer_name
        FROM bookings
        JOIN users
        ON bookings.customer_id = users.id
        WHERE bookings.provider_id=%s
    """, (provider_id,))
    bookings = cursor.fetchall()
    return render_template(
        "provider_bookings.html",
        provider=provider,
        bookings=bookings
    )

# ---------------- SEARCH SERVICES ----------------

@app.route("/search")
def search():
    keyword = request.args.get("keyword", "").strip()
    category = request.args.get("category", "").strip()
    sql = """
    SELECT
        u.id,
        u.fullname,
        u.address,
        u.phone,
        u.email,
        u.image,
        u.experience,
        s.service_name,
        s.category,
        s.price,
        s.description,
        s.image AS service_image
    FROM services s
    JOIN users u
        ON s.provider_id = u.id
    WHERE
        u.role='Service Provider'
        AND s.status='Available'
    """
    values = []
    if keyword:
        sql += """
        AND (
            u.fullname LIKE %s
            OR s.service_name LIKE %s
            OR s.category LIKE %s
            OR u.address LIKE %s
        )
        """
        key = "%" + keyword + "%"
        values.extend([key, key, key, key])
    if category:
        sql += " AND s.category=%s"
        values.append(category)
    sql += " ORDER BY s.id ASC"
    cursor.execute(sql, tuple(values))
    providers = cursor.fetchall()
    print(providers)   # debugging
    return render_template(
        "search.html",
        providers=providers,
        keyword=keyword
    )

# ---------------- PROVIDER PROFILE ----------------

@app.route("/provider_profile/<int:id>", methods=["GET", "POST"])
def provider_profile(id):
    # Provider Information
    cursor.execute("SELECT * FROM users WHERE id=%s", (id,))
    provider = cursor.fetchone()
    if provider is None:
        return "Provider Not Found"
    # Update Profile
    if request.method == "POST":
        if "user_id" not in session:
            return redirect("/login")
        if session["user_id"] != id:
            return "Unauthorized", 403
        fullname = request.form["fullname"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]
        service_name = request.form["service_name"]
        experience = request.form["experience"]
        description = request.form["description"]
        price = request.form["price"]
        available_time = request.form["available_time"]
        image = provider["image"]
        file = request.files.get("image")
        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image = filename
        cursor.execute("""
        UPDATE users
        SET
            fullname=%s,
            email=%s,
            phone=%s,
            address=%s,
            service_name=%s,
            experience=%s,
            description=%s,
            price=%s,
            available_time=%s,
            image=%s
        WHERE id=%s
        """,(
            fullname,
            email,
            phone,
            address,
            service_name,
            experience,
            description,
            price,
            available_time,
            image,
            id
        ))
        conn.commit()
        flash("Profile Updated Successfully")
        return redirect(f"/provider_profile/{id}")
    # Services Offered
    cursor.execute("""
        SELECT *
        FROM services
        WHERE provider_id=%s
        ORDER BY id ASC
    """, (id,))
    services = cursor.fetchall()
    # Reviews
    cursor.execute("""
        SELECT
            reviews.*,
            users.fullname
        FROM reviews
        JOIN users
        ON reviews.customer_id = users.id
        WHERE reviews.provider_id=%s
        ORDER BY reviews.id ASC
    """, (id,))
    reviews = cursor.fetchall()
    # Rating
    cursor.execute("""
        SELECT
            ROUND(AVG(rating),1) AS avg_rating,
            COUNT(*) AS total_reviews
        FROM reviews
        WHERE provider_id=%s
    """, (id,))
    rating = cursor.fetchone()
    return render_template(
        "provider_profile.html",
        provider=provider,
        services=services,
        reviews=reviews,
        rating=rating
    )

# ---------------- BOOKING PAGE ----------------

@app.route("/booking/<int:id>", methods=["GET"])
def booking(id):
    if "user_id" not in session:
        return redirect("/login")
    provider_id = id

    # Get provider
    cursor.execute("SELECT * FROM users WHERE id=%s", (provider_id,))
    provider = cursor.fetchone()

    # Get logged-in customer
    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    # Check provider booking limit
    cursor.execute("""
        SELECT booking_count, subscription_active
        FROM users
        WHERE id=%s
    """, (provider_id,))
    provider_subscription = cursor.fetchone()
    if provider_subscription["booking_count"] >= 5 and provider_subscription["subscription_active"] == 0:
        flash("This provider has reached the free booking limit. Please subscribe to continue receiving bookings.")
        return redirect("/subscription")
    return render_template(
        "booking.html",
        provider=provider,
        user=user
    )

# ---------------- SAVE BOOKING ----------------

@app.route("/booking/<int:id>", methods=["POST"])
def booking_post(id):
    if "user_id" not in session:
        return redirect("/login")
    customer_id = session["user_id"]
    customer_name = request.form.get("customer_name")
    phone = request.form.get("phone")
    service_name = request.form.get("service_name")
    booking_date = request.form.get("booking_date")
    booking_time = request.form.get("booking_time")
    payment = request.form.get("payment")
    address = request.form.get("address")
    description = request.form.get("description")
    sql = """
    INSERT INTO bookings
    (customer_id, customer_name, provider_id, service_name,
     phone, booking_date, booking_time,
     address, description, payment, status)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    values = (
        customer_id,
        customer_name,
        id,                 # provider_id
        service_name,
        phone,
        booking_date,
        booking_time,
        address,
        description,
        payment,
        "Pending"
    )
    cursor.execute(sql, values)
    conn.commit()
    flash("Booking Successful")
    return redirect("/customer_dashboard")

# ---------------- PROVIDER DASHBOARD ----------------

@app.route("/provider_dashboard")
def provider_dashboard():
    if "user_id" not in session:
        return redirect("/login")
    provider_id = session["user_id"]
    # Get Provider Details
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (provider_id,)
    )
    provider = cursor.fetchone()
     # Get Provider Subscription
    cursor.execute("""
        SELECT *
        FROM subscriptions
        WHERE provider_id=%s
        ORDER BY id DESC
        LIMIT 1
    """, (provider_id,))
    subscription = cursor.fetchone()

     # REMAINING DAYS
    remaining_days = None
    if subscription:
        remaining_days = (subscription["end_date"] - date.today()).days

        if remaining_days < 0:
            remaining_days = 0

    # Get Provider Bookings
    cursor.execute("""
        SELECT bookings.*, users.fullname AS customer_name
        FROM bookings
        JOIN users
        ON bookings.customer_id = users.id
        WHERE bookings.provider_id=%s
        ORDER BY bookings.id ASC
    """, (provider_id,))
    bookings = cursor.fetchall()
    # Dashboard Counts
    total_bookings = len(bookings)
    pending_bookings = len([b for b in bookings if b["status"] == "Pending"])
    accepted_bookings = len([b for b in bookings if b["status"] == "Accepted"])
    completed_bookings = len([b for b in bookings if b["status"] == "Completed"])
    # Earnings
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM bookings
        WHERE provider_id=%s
        AND status='Completed'
        """, (provider_id,))
    result = cursor.fetchone()
    total_earnings = result["total"] * 500
    # Reviews (currently empty)
    cursor.execute("""
    SELECT reviews.*,
    users.fullname AS customer_name
    FROM reviews
    JOIN users
    ON reviews.customer_id=users.id
    WHERE provider_id=%s
    ORDER BY id ASC
    """,(provider_id,))
    reviews=cursor.fetchall()
    return render_template(
        "provider_dashboard.html",
        provider=provider,
        subscription=subscription,
        bookings=bookings,
        total_bookings=total_bookings,
        pending_bookings=pending_bookings,
        accepted_bookings=accepted_bookings,
        completed_bookings=completed_bookings,
        reviews=reviews,
        total_earnings=total_earnings,
        remaining_days=remaining_days
    )

# ---------------- ACCEPT BOOKING ----------------

@app.route("/accept/<int:id>")
def accept(id):
    cursor.execute(
        "UPDATE bookings SET status='Accepted' WHERE id=%s",
        (id, )
    )
    conn.commit()
    flash("Booking Accepted Successfully")
    return redirect("/provider_dashboard")

# ---------------- Reject BOOKING ----------------

@app.route("/reject/<int:id>")
def reject(id):
    cursor.execute(
        "UPDATE bookings SET status='Rejected' WHERE id=%s",
        (id, )
    )
    conn.commit()
    flash("Booking Rejected")
    return redirect("/provider_dashboard")

# ---------------- COMPLETE BOOKING ----------------

@app.route("/complete_booking/<int:id>")
def complete_booking(id):

    # Mark booking as completed
    cursor.execute("""
        UPDATE bookings
        SET status='Completed'
        WHERE id=%s
    """, (id,))

    # Get provider ID
    cursor.execute("""
        SELECT provider_id
        FROM bookings
        WHERE id=%s
    """, (id,))
    booking = cursor.fetchone()
    provider_id = booking["provider_id"]

    # Increase provider booking count
    cursor.execute("""
        UPDATE users
        SET booking_count = booking_count + 1
        WHERE id=%s
    """, (provider_id,))
    conn.commit()
    flash("Booking completed successfully.")
    return redirect("/provider_bookings")

# ---------------- NOTIFICATIONS ----------------

@app.route("/notifications", methods=["GET","POST"])
def notifications():
    if "user_id" not in session:
        return redirect("/login")
    if request.method=="POST":
        receiver=request.form["receiver"]
        title=request.form["title"]
        message=request.form["message"]
        cursor.execute("""
        INSERT INTO notifications
        (receiver,title,message)
        VALUES(%s,%s,%s)
        """,(receiver,title,message))
        conn.commit()
        flash("Notification Sent Successfully")
        return redirect("/notifications")
    cursor.execute("""
    SELECT *
    FROM notifications
    ORDER BY id ASC
    """)
    notifications=cursor.fetchall()
    return render_template(
        "notifications.html",
        notifications=notifications
    )

# ---------------- DELETE NOTIFICATION ----------------

@app.route("/delete_notification/<int:id>")
def delete_notification(id):
    cursor.execute(
        "DELETE FROM notifications WHERE id=%s",
        (id,)
    )
    conn.commit()
    flash("Notification Deleted Successfully")
    return redirect("/notifications")

# ---------------- SETTINGS ----------------

@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )
    admin=cursor.fetchone()
    return render_template(
        "settings.html",
        admin=admin
    )

# ---------------- PROVIDER SETTINGS ----------------

@app.route("/provider_settings")
def provider_settings():
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )
    provider = cursor.fetchone()
    return render_template(
        "settings.html",
        provider=provider
    )
# ---------------- PROVIDER Password update ----------------

@app.route("/change_provider_password", methods=["POST"])
def change_provider_password():

    if "user_id" not in session:
        return redirect("/login")

    old = request.form["old_password"]
    new = request.form["new_password"]
    confirm = request.form["confirm_password"]

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    provider = cursor.fetchone()

    if provider["password"] != old:
        flash("Current Password Incorrect")
        return redirect("/provider_settings")

    if new != confirm:
        flash("Password Does Not Match")
        return redirect("/provider_settings")

    cursor.execute("""
        UPDATE users
        SET password=%s
        WHERE id=%s
    """, (
        new,
        session["user_id"]
    ))

    conn.commit()

    flash("Password Changed Successfully")

    return redirect("/provider_settings")

# ---------------- UPDATE ADMIN PROFILE ----------------

@app.route("/update_admin_profile", methods=["POST"])
def update_admin_profile():
    fullname = request.form["fullname"]
    email = request.form["email"]
    phone = request.form["phone"]
    image = request.files["image"]
    filename = None
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )
        )
        cursor.execute("""
        UPDATE users
        SET fullname=%s,
            email=%s,
            phone=%s,
            image=%s
        WHERE role='Admin'
        """,
        (
            fullname,
            email,
            phone,
            filename
        ))
    else:
        cursor.execute("""
        UPDATE users
        SET fullname=%s,
            email=%s,
            phone=%s
        WHERE role='Admin'
        """,
        (
            fullname,
            email,
            phone
        ))
    conn.commit()
    flash("Profile Updated Successfully")
    return redirect("/settings")

# ----------------CHANGE PASSWORD ----------------

@app.route("/change_admin_password",methods=["POST"])
def change_admin_password():
    old=request.form["old_password"]
    new=request.form["new_password"]
    confirm=request.form["confirm_password"]
    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )
    admin=cursor.fetchone()
    if admin["password"]!=old:
        flash("Current Password is Incorrect")
        return redirect("/settings")
    if new!=confirm:
        flash("New Password Does Not Match")
        return redirect("/settings")
    cursor.execute("""
    UPDATE users
    SET password=%s
    WHERE id=%s
    """,(new,session["user_id"]))
    conn.commit()
    flash("Password Changed Successfully")
    return redirect("/settings")

# ---------------- CONTACT ----------------

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        fullname = request.form["fullname"]
        email = request.form["email"]
        subject = request.form["subject"]
        message = request.form["message"]
        cursor.execute("""
            INSERT INTO contact_messages
            (fullname, email, subject, message)
            VALUES (%s, %s, %s, %s)
        """, (fullname, email, subject, message))
        conn.commit()
        flash("Message sent successfully!")
        return redirect("/contact")
    return render_template("contact.html")

# ---------------- CONTACT MESSAGES----------------

@app.route("/contact_messages")
def contact_messages():
    if "user_id" not in session:
        return redirect("/login")
    cursor.execute("SELECT role FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()
    if user["role"] != "Admin":
        return "Access Denied", 403
    cursor.execute("SELECT * FROM contact_messages ORDER BY id ASC")
    messages = cursor.fetchall()
    return render_template(
        "contact_messages.html",
        messages=messages
    )

# ---------------- DELETE CONTACT ----------------

@app.route("/delete_message/<int:id>")
def delete_message(id):
    cursor.execute(
        "DELETE FROM contact_messages WHERE id=%s",
        (id,)
    )
    conn.commit()
    return redirect("/contact_messages")

# ---------------- SUBSCRIPTIONS ----------------

@app.route("/subscription")
def subscription():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("subscription.html")

@app.route("/subscription", methods=["POST"])
def subscription_post():
    if "user_id" not in session:
        return redirect("/login")
    provider_id = session["user_id"]
    plan = request.form.get("plan")
    transaction_id = request.form.get("transaction_id")
    screenshot = request.files.get("screenshot")

    # Check if screenshot is uploaded
    if not screenshot or screenshot.filename == "":
        flash("Payment Screenshot Required", "danger")
        return redirect("/subscription")
    filename = secure_filename(screenshot.filename)
    screenshot.save(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )
    )
    if plan == "1 Month":
        amount = 500
        end_date = date.today() + timedelta(days=30)
    elif plan == "3 Months":
        amount = 1200
        end_date = date.today() + timedelta(days=90)
    else:
        flash("Please select a valid subscription plan.", "danger")
        return redirect("/subscription")
    cursor.execute("""
        INSERT INTO subscriptions
        (
            provider_id,
            plan,
            amount,
            transaction_id,
            payment_screenshot,
            status,
            start_date,
            end_date
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        provider_id,
        plan,
        amount,
        transaction_id,
        filename,
        "Pending",
        date.today(),
        end_date
    ))
    conn.commit()
    flash("Subscription Submitted Successfully", "success")
    return redirect("/provider_dashboard")

# ---------------- MANAGE SUBSCRIPTIONS ----------------

@app.route("/manage_subscriptions")
def manage_subscriptions():
    if "user_id" not in session or session.get("role") != "Admin":
        return redirect("/login")
    cursor.execute("""
        SELECT
            subscriptions.*,
            users.fullname
        FROM subscriptions
        JOIN users
        ON subscriptions.provider_id = users.id
        ORDER BY subscriptions.id ASC
    """)
    subscriptions = cursor.fetchall()
    return render_template(
        "manage_subscriptions.html",
        subscriptions=subscriptions
    )

# ---------------- APPROVE SUBSCRIPTIONS ----------------

@app.route("/approve_subscription/<int:id>")
def approve_subscription(id):
    cursor.execute(
        "SELECT * FROM subscriptions WHERE id=%s",
        (id,)
    )
    sub = cursor.fetchone()
    cursor.execute("""
        UPDATE subscriptions
        SET status='Approved'
        WHERE id=%s
    """, (id,))
    cursor.execute("""
        UPDATE users
        SET
            subscription_active=1,
            booking_count=0
        WHERE id=%s
    """, (sub["provider_id"],))
    conn.commit()
    flash("Subscription Approved Successfully.", "success" )
    return redirect("/manage_subscriptions")

# ---------------- REJECT SUBSCRIPTIONS ----------------

@app.route("/reject_subscription/<int:id>")
def reject_subscription(id):
    cursor.execute("""
        UPDATE subscriptions
        SET status='Rejected'
        WHERE id=%s
    """, (id,))
    conn.commit()
    flash("Subscription Rejected", "warning")
    return redirect(url_for("manage_subscriptions"))

if __name__ == "__main__":
    app.run(debug=True)