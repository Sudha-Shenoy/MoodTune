# MoodTune
> **AI Mood & Language Based Music Player**

MoodTune is an intelligent music application designed to recommend and play music based on user mood and language preferences.

---

## Current Status
**Module 01 – Project Setup**
- Clean modular foundation with Flask application factory.
- Blueprints and Jinja2 templates initialized.
- Environment variables configured via `python-dotenv`.
- Automated testing with `pytest`.

---

## Technology Stack
- **Backend:** Python 3, Flask
- **Frontend:** HTML5, CSS3, Vanilla JavaScript, Jinja2 Templates
- **Environment Management:** python-dotenv
- **Testing:** pytest
- **Version Control:** Git

---

## Planned Integrations
- **AI Recommendation Engine:** Intelligent mood and language analysis for music suggestions.
- **YouTube Data API:** Music and video search integration.
- **YouTube Player:** Embedded playback interface.
- **SQLite Database:** Local persistent storage for user preferences and history.
- **Authentication:** User signup, login, and profile management.

---

## Running the Project

Follow these steps to set up and run MoodTune locally:

### 1. Create Virtual Environment
Open a terminal in the project root directory and create a virtual environment:

```bash
# Windows
python -m venv venv

# macOS / Linux
python3 -m venv venv
```

### 2. Activate Virtual Environment

```bash
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.\venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

### 3. Install Requirements

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to create your local `.env`:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```
*(Note: `.env` is already configured with local development defaults and is excluded from Git.)*

### 5. Run Flask Application

```bash
python app.py
```

### 6. Open the Local URL
Open your web browser and navigate to:
[http://127.0.0.1:5000/](http://127.0.0.1:5000/)

---

## Running Tests

Execute the automated test suite:

```bash
python -m pytest tests/
```
