# MoodTune
> **AI Mood & Language Based Music Player**

MoodTune is an intelligent music application designed to recommend and play music based on user mood and language preferences.

---

## Current Status
**Module 03 — User Authentication**
- User registration, login, logout, and session management.
- Secure password hashing using Werkzeug (`generate_password_hash` / `check_password_hash`).
- MySQL persistence via Flask-SQLAlchemy and PyMySQL with dedicated `users` model.
- Dynamic navbar reflecting authentication state (`Login`/`Register` vs `Hi, <username>`/`Logout`).
- Preserved modern music discovery landing page and visual identity.
- Full automated test suite with isolated in-memory SQLite testing configuration.

---

## Technology Stack
- **Backend:** Python 3, Flask, Flask-SQLAlchemy
- **Database:** MySQL Server 8.x (`MySQL80` service), PyMySQL, cryptography
- **Authentication & Security:** Flask sessions, Werkzeug password hashing, HTTP-only SameSite cookies
- **Frontend:** HTML5, CSS3, Vanilla JavaScript, Jinja2 Templates
- **Testing:** pytest
- **Version Control:** Git

---

## Database Setup & Initialization

MoodTune connects directly to the local **MySQL80** Windows service (verified port: `3306`).

### Step 1: Create Database in MySQL Workbench
Open **MySQL Workbench** (or your MySQL CLI) connected to your local `MySQL80` server, and execute:

```sql
CREATE DATABASE moodtune;
```

### Step 2: Configure Environment Variables
Copy `.env.example` to create your local `.env`:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and set your local MySQL root password:

```env
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev_secret_key_moodtune_local_development

DB_HOST=localhost
DB_PORT=3306
DB_NAME=moodtune
DB_USER=root
DB_PASSWORD=your_actual_mysql_password_here
```

*(Note: `.env` is ignored by Git and will never be committed.)*

### Step 3: Initialize Database Tables
Create the `users` table in the `moodtune` database using either method:

**Option A (Flask CLI):**
```bash
flask --app app init-db
```

**Option B (Standalone Script):**
```bash
python init_db.py
```

---

## Running the Application

### 1. Activate Virtual Environment

```bash
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.\venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Flask

```bash
python app.py
```

### 4. Open Application in Browser
Navigate to:
[http://127.0.0.1:5000/](http://127.0.0.1:5000/)

---

## Authentication Flow

1. **Register a New Account:**
   - Click **Register** on the navbar or navigate to `http://127.0.0.1:5000/register`.
   - Enter your name, valid email, and password (minimum 8 characters).
   - Upon successful registration, your password is saved as a secure hash, and you are redirected to `/login`.

2. **Login:**
   - Click **Login** on the navbar or navigate to `http://127.0.0.1:5000/login`.
   - Enter your email and password.
   - Upon successful authentication, your session is created, and you are redirected to `/`.
   - The navbar dynamically updates to display:
     `Hi, <Your Name>` and a **Logout** button.

3. **Logout:**
   - Click **Logout** on the navbar or navigate to `http://127.0.0.1:5000/logout`.
   - Your session is cleared, and you are redirected to `/` with the navbar reverting to `Login` and `Register`.

---

## Running Automated Tests

Run the complete test suite with `pytest`:

```bash
.\venv\Scripts\python.exe -m pytest tests/ -v
```

*Note: Automated tests execute using `TestingConfig` with an isolated in-memory SQLite database, requiring zero external MySQL configuration or credentials.*
