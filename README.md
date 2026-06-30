# AI Resume Builder and Analyzer

Final Year BCA project built with Python Flask, SQLAlchemy, HTML, CSS, JavaScript, and Bootstrap 5. It runs locally with SQLite by default and can also use MySQL by setting `DATABASE_URL`.

The project lets users register, login, build resumes, choose templates, preview resumes live, download PDF resumes, print resumes, and analyze resume quality using local rule-based AI logic. It does not use OpenAI API or any paid external API.

## Features

- User registration, login, logout, and session management
- Resume builder with full name, email, phone, address, objective, skills, education, experience, projects, certifications, languages, and achievements
- Professional, modern, and simple resume templates
- Live resume preview while editing
- Rule-based AI resume analyzer
- Resume score out of 100
- ATS compatibility score
- Skill, keyword, missing section, strength, weakness, and suggestion analysis
- PDF download using ReportLab
- Print-friendly resume view
- Admin login, dashboard statistics, user management, resume management, and delete operations
- SQLite local database by default, with MySQL support through SQLAlchemy ORM

## Folder Structure

```text
ai resume builder and analyser/
|-- app.py
|-- analyzer.py
|-- config.py
|-- extensions.py
|-- models.py
|-- pdf_utils.py
|-- requirements.txt
|-- database.sql
|-- .env.example
|-- templates/
|   |-- base.html
|   |-- index.html
|   |-- auth/
|   |-- resume/
|   `-- admin/
|-- static/
|   |-- css/style.css
|   `-- js/app.js
`-- docs/
    |-- INSTALLATION_GUIDE.md
    |-- VS_CODE_SETUP_GUIDE.md
    |-- PROJECT_REPORT_SYNOPSIS.md
    `-- ER_DIAGRAM_EXPLANATION.md
```

## Quick Start

1. Install Python 3.11 or newer.
2. Create a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Run `flask --app app run`.
5. Open `http://127.0.0.1:5000`.

The app auto-creates a local `resume_builder.sqlite3` database and default admin when `DATABASE_URL` is not set.

To use MySQL instead, create the database using `database.sql`, copy `.env.example` to `.env`, uncomment `DATABASE_URL`, set your real MySQL password, then run `flask --app app init-db`.

Default admin login after setup:

```text
Email: admin@resumeai.local
Password: admin123
```

## Analyzer Scoring

```text
Skills = 20
Education = 15
Experience = 20
Projects = 15
Certifications = 10
Career Objective = 10
Languages = 10
Total = 100
```

The analyzer checks content completeness, section strength, keyword presence, action verbs, ATS readiness, and missing details. Suggestions are generated based on low scores and empty sections.
