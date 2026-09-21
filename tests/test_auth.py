"""Unit and integration tests for MoodTune Module 03: User Authentication."""
import pytest
from flask import session
from app import create_app
from config.config import TestingConfig
from models import db, User
from routes.auth_routes import login_required


@pytest.fixture
def app():
    """Create and configure a Flask test application with isolated in-memory database."""
    application = create_app(TestingConfig)

    # Register a temporary dummy route to test the login_required decorator
    @application.route("/test-protected")
    @login_required
    def test_protected():
        return "Protected Content"

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the application."""
    return app.test_client()


# 1. GET /login returns 200
def test_get_login_status_code(client):
    """Verify that GET /login returns HTTP 200."""
    response = client.get("/login")
    assert response.status_code == 200


# 2. GET /register returns 200
def test_get_register_status_code(client):
    """Verify that GET /register returns HTTP 200."""
    response = client.get("/register")
    assert response.status_code == 200


# 3. Login form contains required fields
def test_login_form_elements(client):
    """Verify login form contains email, password, and login button."""
    response = client.get("/login")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert 'name="email"' in html
    assert 'name="password"' in html
    assert 'type="email"' in html
    assert 'type="password"' in html
    assert "Login" in html


# 4. Registration form contains required fields
def test_register_form_elements(client):
    """Verify registration form contains name, email, password, confirm_password, and button."""
    response = client.get("/register")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert 'name="name"' in html
    assert 'name="email"' in html
    assert 'name="password"' in html
    assert 'name="confirm_password"' in html
    assert "Create Account" in html


# 5. Valid registration creates a User
def test_valid_registration_creates_user(client, app):
    """Verify valid registration creates a user in the database and redirects to login."""
    response = client.post(
        "/register",
        data={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123"
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Registration successful! Please log in." in response.data.decode("utf-8")

    with app.app_context():
        user = User.query.filter_by(email="jane@example.com").first()
        assert user is not None
        assert user.name == "Jane Doe"


# 6. Password is hashed and never stored as plaintext
def test_password_is_hashed_not_plaintext(client, app):
    """Verify stored password is a hash and not plaintext."""
    client.post(
        "/register",
        data={
            "name": "Alex Smith",
            "email": "alex@example.com",
            "password": "MySecretPassword99",
            "confirm_password": "MySecretPassword99"
        }
    )

    with app.app_context():
        user = User.query.filter_by(email="alex@example.com").first()
        assert user is not None
        assert user.password_hash != "MySecretPassword99"
        assert len(user.password_hash) > 20
        assert user.check_password("MySecretPassword99") is True
        assert user.check_password("WrongPassword") is False


# 7. Duplicate email is rejected
def test_duplicate_email_rejected(client, app):
    """Verify duplicate email registration is rejected with friendly message."""
    client.post(
        "/register",
        data={
            "name": "User One",
            "email": "duplicate@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        }
    )

    response = client.post(
        "/register",
        data={
            "name": "User Two",
            "email": "duplicate@example.com",
            "password": "Password456",
            "confirm_password": "Password456"
        }
    )
    assert response.status_code == 400
    assert "An account with this email already exists." in response.data.decode("utf-8")


# 8. Invalid email is rejected
def test_invalid_email_format_rejected(client):
    """Verify improperly formatted emails are rejected."""
    for invalid_email in ["not-an-email", "missing@domain", "@nodomain.com", "user@.com"]:
        response = client.post(
            "/register",
            data={
                "name": "Test User",
                "email": invalid_email,
                "password": "Password123",
                "confirm_password": "Password123"
            }
        )
        assert response.status_code == 400
        assert "Please enter a valid email address." in response.data.decode("utf-8")


# 9. Missing name is rejected
def test_missing_name_rejected(client):
    """Verify registration with missing or whitespace-only name is rejected."""
    for bad_name in ["", " ", "a"]:
        response = client.post(
            "/register",
            data={
                "name": bad_name,
                "email": "valid@example.com",
                "password": "Password123",
                "confirm_password": "Password123"
            }
        )
        assert response.status_code == 400
        assert "Please enter your name." in response.data.decode("utf-8")


# 10. Password shorter than 8 characters is rejected
def test_short_password_rejected(client):
    """Verify password shorter than 8 characters is rejected."""
    response = client.post(
        "/register",
        data={
            "name": "Short Pass User",
            "email": "short@example.com",
            "password": "short",
            "confirm_password": "short"
        }
    )
    assert response.status_code == 400
    assert "Password must be at least 8 characters." in response.data.decode("utf-8")


# 11. Password mismatch is rejected
def test_password_mismatch_rejected(client):
    """Verify mismatched password and confirm_password are rejected."""
    response = client.post(
        "/register",
        data={
            "name": "Mismatch User",
            "email": "mismatch@example.com",
            "password": "Password123",
            "confirm_password": "DifferentPassword123"
        }
    )
    assert response.status_code == 400
    assert "Passwords do not match." in response.data.decode("utf-8")


# 12. Invalid login is rejected
def test_invalid_login_rejected(client, app):
    """Verify invalid credentials return a generic error message."""
    # Attempt login for non-existent user
    response = client.post(
        "/login",
        data={"email": "nonexistent@example.com", "password": "RandomPassword123"}
    )
    assert response.status_code == 400
    assert "Invalid email or password." in response.data.decode("utf-8")

    # Create user and attempt login with wrong password
    with app.app_context():
        u = User(name="Valid User", email="valid@example.com")
        u.set_password("CorrectPassword123")
        db.session.add(u)
        db.session.commit()

    response2 = client.post(
        "/login",
        data={"email": "valid@example.com", "password": "WrongPassword999"}
    )
    assert response2.status_code == 400
    assert "Invalid email or password." in response2.data.decode("utf-8")


# 13. Valid login succeeds
def test_valid_login_succeeds(client, app):
    """Verify valid login redirects to home page with welcome message."""
    with app.app_context():
        u = User(name="Sam Wilson", email="sam@example.com")
        u.set_password("FalconShield2026")
        db.session.add(u)
        db.session.commit()

    response = client.post(
        "/login",
        data={"email": "sam@example.com", "password": "FalconShield2026"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Welcome back, Sam Wilson!" in response.data.decode("utf-8")


# 14. Successful login sets user_id in session
def test_login_sets_user_id_in_session(client, app):
    """Verify user_id is stored in session upon successful login."""
    with app.app_context():
        u = User(name="Diana Prince", email="diana@example.com")
        u.set_password("Themyscira2026")
        db.session.add(u)
        db.session.commit()
        user_id = u.id

    with client:
        client.post(
            "/login",
            data={"email": "diana@example.com", "password": "Themyscira2026"}
        )
        assert session.get("user_id") == user_id


# 15. Successful login sets user_name in session
def test_login_sets_user_name_in_session(client, app):
    """Verify user_name is stored in session upon successful login."""
    with app.app_context():
        u = User(name="Clark Kent", email="clark@example.com")
        u.set_password("Metropolis2026")
        db.session.add(u)
        db.session.commit()

    with client:
        client.post(
            "/login",
            data={"email": "clark@example.com", "password": "Metropolis2026"}
        )
        assert session.get("user_name") == "Clark Kent"


# 16. Logout clears authentication session data
def test_logout_clears_session(client, app):
    """Verify logout removes user_id and user_name from session."""
    with app.app_context():
        u = User(name="Bruce Wayne", email="bruce@example.com")
        u.set_password("GothamCity2026")
        db.session.add(u)
        db.session.commit()

    with client:
        # Log in first
        client.post(
            "/login",
            data={"email": "bruce@example.com", "password": "GothamCity2026"}
        )
        assert session.get("user_id") is not None

        # Log out
        response = client.get("/logout", follow_redirects=True)
        assert response.status_code == 200
        assert session.get("user_id") is None
        assert session.get("user_name") is None
        assert "You have been logged out." in response.data.decode("utf-8")


# 17. Home page works when logged out
def test_home_page_when_logged_out(client):
    """Verify GET / returns 200 and shows Login/Register links when unauthenticated."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Login" in html
    assert "Register" in html
    assert "Logout" not in html


# 18. Home page works when logged in
def test_home_page_when_logged_in(client, app):
    """Verify GET / returns 200 and shows personalized greeting and logout when authenticated."""
    with app.app_context():
        u = User(name="Tony Stark", email="tony@example.com")
        u.set_password("JarvisIron2026")
        db.session.add(u)
        db.session.commit()

    with client:
        client.post(
            "/login",
            data={"email": "tony@example.com", "password": "JarvisIron2026"}
        )
        response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Hi," in html
        assert "Tony Stark" in html
        assert "Logout" in html


# 19. Navbar changes correctly based on authentication state
def test_navbar_auth_state_transition(client, app):
    """Verify navbar dynamically switches between logged-out and logged-in states."""
    with app.app_context():
        u = User(name="Peter Parker", email="peter@example.com")
        u.set_password("WebSlinger2026")
        db.session.add(u)
        db.session.commit()

    with client:
        # 1. Initially logged out: shows Login & Register
        res_logged_out = client.get("/")
        html_out = res_logged_out.data.decode("utf-8")
        assert "Login" in html_out
        assert "Register" in html_out
        assert "Logout" not in html_out

        # 2. After login: shows greeting & Logout
        client.post(
            "/login",
            data={"email": "peter@example.com", "password": "WebSlinger2026"}
        )
        res_logged_in = client.get("/")
        html_in = res_logged_in.data.decode("utf-8")
        assert "Peter Parker" in html_in
        assert "Logout" in html_in

        # 3. After logout: reverts to Login & Register
        client.get("/logout")
        res_reverted = client.get("/")
        html_rev = res_reverted.data.decode("utf-8")
        assert "Login" in html_rev
        assert "Register" in html_rev
        assert "Logout" not in html_rev


# 20. login_required redirects unauthenticated users appropriately
def test_login_required_redirects_unauthenticated(client, app):
    """Verify login_required decorator redirects unauthenticated users to /login."""
    # When unauthenticated: redirects to /login
    response = client.get("/test-protected")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    # Follow redirect
    follow_res = client.get("/test-protected", follow_redirects=True)
    assert follow_res.status_code == 200
    assert "Please log in to access this page." in follow_res.data.decode("utf-8")

    # When authenticated: access granted
    with app.app_context():
        u = User(name="Natasha Romanoff", email="natasha@example.com")
        u.set_password("BlackWidow2026")
        db.session.add(u)
        db.session.commit()

    with client:
        client.post(
            "/login",
            data={"email": "natasha@example.com", "password": "BlackWidow2026"}
        )
        auth_res = client.get("/test-protected")
        assert auth_res.status_code == 200
        assert "Protected Content" in auth_res.data.decode("utf-8")
