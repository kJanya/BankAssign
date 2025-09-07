
# College Eligibility FastAPI (SQLite)

## Overview
A lightweight FastAPI application that evaluates student eligibility for college programs using 12th-grade subject combinations, cut-offs, and qualification exams (JEE/NEET). It validates inputs with regex, stores requests and decisions in SQLite, and logs all I/O with timestamps.

- **Stack**: FastAPI, SQLite (`sqlite3`), NumPy, Pandas, `re`
- **OOP & Structure**: Modular components for DB, logging, validation, and eligibility engine.
- **Concurrency**: FastAPI handles concurrent requests; SQLite connection is per-request (`check_same_thread=False`).
- **Time Budget**: Computation is O(1) with tiny lookups; median latency << 1s in local tests.

🚀 Deploying to Render (FastAPI + Uvicorn)

This project is a FastAPI app served by Uvicorn. Below are the exact steps (and commands) used to deploy it on Render.

1) Repo layout
.
├─ app/
│  ├─ __init__.py
│  ├─ main.py            # FastAPI app (routes: /docs, /health, /check_eligibility)
│  ├─ db.py              # SQLite helpers (uses DB_PATH env var)
│  ├─ eligibility.py     # Business rules
│  ├─ schemas.py         # Pydantic models
│  └─ logger.py
├─ requirements.txt
└─ (optional) runtime.txt   # pin Python version on Render (e.g., 3.12.6)


Note: api/index.py is only needed for Vercel; Render does not need it.

2) Dependencies

Use a minimal, platform-friendly requirements.txt (avoid pip freeze):

fastapi==0.115.0
uvicorn==0.30.6
pydantic==2.9.2
numpy==2.1.3
pandas==2.3.0


If you’d rather match local Python 3.12, pin Pydantic v1 & NumPy 2.0.1, and add runtime.txt with 3.12.6.

3) (Optional) Pin Python version on Render

If you hit wheels/build issues on Python 3.13, pin to 3.12:

runtime.txt
└─ 3.12.6


Commit and push.

4) Create the service on Render

Go to Render → New → Web Service.

Connect your GitHub repo.

Environment: Python (auto-detected).

Build Command:

pip install -r requirements.txt


Start Command:

uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers ${WEB_CONCURRENCY:-2} --log-level info


Click Create Web Service.

Environment variables

If you’re using SQLite (default in this project):

DB_PATH → set to a writable path.

Quick demo (ephemeral): /tmp/data.sqlite3

To add: Settings → Environment → Add Environment Variable.

## Run locally
```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open interactive docs at: `http://localhost:8000/docs`

## API
`POST /check_eligibility`

### Request (JSON)
```json
{
  "name": "Jane Doe",
  "age": 18,
  "gender": "Female",
  "desired_course": "Computer Science Engineering",
  "marks": {
    "Physics": 80, "Chemistry": 78, "Mathematics": 82,
    "English": 85, "Computer Science": 90, "Economics": 70
  },
  "qualification_exams": {"JEE": true, "NEET": false}
}
```

### Response (JSON)
```json
{
  "student_id": "6b9d1e0e-...",
  "desired_course": "Computer Science Engineering",
  "eligible": true,
  "reasons": [],
  "recommendations": []
}
```

If ineligible, `reasons` contains precise deficiencies and `recommendations` lists the top viable alternatives based on provided subjects/exam status and cutoffs.

## Input Validation
- Name: letters + spaces only (`^[A-Za-z ]+$`)
- Age: 17–25 inclusive
- Gender: Male/Female/Other (case-insensitive)
- Marks: 0–100 per subject (expects key-value dict)
- Desired course: must be one of the predefined catalog entries

## Eligibility Logic
- Engineering branches: require **JEE** and **PCM** with branch-specific cut-offs.
- Medicine: require **NEET** and **PCB** with cut-offs.
- Commerce/Humanities: require specific subject triplets; no cutoff.
- Average computed with **NumPy** over required-subject marks only.
- Recommendations:
  1. Courses whose required subjects are present **and** exam (if required) is qualified **and** cut-off met.
  2. If none, closest matches that ignore cut-off.
  3. If still none, compatible Humanities/Commerce programs.
  4. Fallback tip to improve eligibility.

A compact **Pandas** DataFrame holds the catalog and supports vectorized filtering.

## Persistence
- `students`: raw input JSON + student fingerprint for idempotent upsert (name+age+gender). If a student re-applies, the previous record is **deleted** and replaced.
- `decisions`: normalized output JSON with eligibility flag, reasons, and recommendations.
- `logs`: independent request/response logs with UTC ISO timestamps.

## Error Handling
- Validation errors → HTTP 422 with detailed list.
- All other exceptions → HTTP 500 with a generic message (internally logged); no stack traces leaked.

## Notes & Assumptions
- Duplicate detection uses `(name, age, gender)` fingerprint. If you prefer stricter dedupe, add DOB or national id in schema.
- SQLite chosen for portability; you can switch to SQL Server via `pyodbc` with minimal changes in `app/db.py`.
- Execution is deterministic and stateless beyond DB writes; safe for concurrent calls.

## Tests (Manual)
Try the following payloads in `/docs`:
- **Happy-path CSE**: JEE true + PCM >= 75 avg.
- **Fail on exam**: JEE false for engineering.
- **Fail on subjects**: Missing Mathematics for CSE.
- **Fail on cutoff**: PCM average below threshold; should propose lower-cutoff branches like Civil.

## Packaging
This repo includes:
- `app/main.py` (FastAPI endpoint)
- `app/eligibility.py` (validation + engine + persistence)
- `app/db.py` (SQLite setup + helpers)
- `app/logger.py` (I/O logging to DB)
- `app/schemas.py` (Pydantic models)
- `requirements.txt`

