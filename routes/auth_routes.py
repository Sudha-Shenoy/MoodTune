"""Authentication routes module for MoodTune."""
import logging
import re
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from models import db, User

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def login_required(view_func):
    """Decorator to require login for protected routes."""
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "info")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return decorated_view


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle user registration."""
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # 1. Name validation
        if not name or len(name) < 2 or len(name) > 100:
            flash("Please enter your name.", "error")
            return render_template("register.html", name=name, email=email), 400

        # 2. Email format validation
        if not email or not EMAIL_REGEX.match(email) or email.endswith("."):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html", name=name, email=email), 400

        # 3. Password validation
        if not password or len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html", name=name, email=email), 400

        # 4. Confirm password match
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", name=name, email=email), 400

        # 5. Database operations (with error handling so raw DB errors are never exposed)
        try:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("An account with this email already exists.", "error")
                return render_template("register.html", name=name, email=email), 400

            new_user = User(name=name, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))

        except OperationalError as exc:
            db.session.rollback()
            logger.error("Database connection error during registration: %s", exc)
            flash("Database connection error. Please verify your MySQL server is running and DB_PASSWORD in .env is correct.", "error")
            return render_template("register.html", name=name, email=email), 500
        except SQLAlchemyError as exc:
            db.session.rollback()
            logger.error("SQLAlchemy database error during registration: %s", exc)
            flash("An error occurred while creating your account. Please try again.", "error")
            return render_template("register.html", name=name, email=email), 500

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email), 400

        try:
            user = User.query.filter_by(email=email).first()

            if not user or not user.check_password(password):
                flash("Invalid email or password.", "error")
                return render_template("login.html", email=email), 400

            # Valid login
            session["user_id"] = user.id
            session["user_name"] = user.name

            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for("main.index"))

        except OperationalError as exc:
            logger.error("Database connection error during login: %s", exc)
            flash("Database connection error. Please verify your MySQL server is running and DB_PASSWORD in .env is correct.", "error")
            return render_template("login.html", email=email), 500
        except SQLAlchemyError as exc:
            logger.error("SQLAlchemy database error during login: %s", exc)
            flash("An unexpected error occurred. Please try again.", "error")
            return render_template("login.html", email=email), 500

    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET"])
def logout():
    """Handle user logout."""
    session.pop("user_id", None)
    session.pop("user_name", None)

    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))
