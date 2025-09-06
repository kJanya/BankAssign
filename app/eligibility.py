
import re
import uuid
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .db import get_conn
from .logger import log_payload

NAME_RE = re.compile(r"^[A-Za-z ]+$")
GENDER_SET = {"male","female","other"}

# Course catalog with subject requirements and cutoffs/qual exam
COURSE_CATALOG = [
    # Engineering (requires JEE and PCM)
    {"course":"Computer Science Engineering","family":"Engineering","required":["Physics","Chemistry","Mathematics"],"cutoff":75,"exam":"JEE"},
    {"course":"Mechanical Engineering","family":"Engineering","required":["Physics","Chemistry","Mathematics"],"cutoff":70,"exam":"JEE"},
    {"course":"Electrical Engineering","family":"Engineering","required":["Physics","Chemistry","Mathematics"],"cutoff":70,"exam":"JEE"},
    {"course":"Civil Engineering","family":"Engineering","required":["Physics","Chemistry","Mathematics"],"cutoff":65,"exam":"JEE"},
    {"course":"Electronics and Communication Engineering","family":"Engineering","required":["Physics","Chemistry","Mathematics"],"cutoff":70,"exam":"JEE"},

    # Medicine (requires NEET and PCB)
    {"course":"MBBS","family":"Medicine","required":["Physics","Chemistry","Biology"],"cutoff":85,"exam":"NEET"},
    {"course":"BDS","family":"Medicine","required":["Physics","Chemistry","Biology"],"cutoff":80,"exam":"NEET"},
    {"course":"BAMS","family":"Medicine","required":["Physics","Chemistry","Biology"],"cutoff":75,"exam":"NEET"},
    {"course":"BHMS","family":"Medicine","required":["Physics","Chemistry","Biology"],"cutoff":75,"exam":"NEET"},
    {"course":"BPT","family":"Medicine","required":["Physics","Chemistry","Biology"],"cutoff":70,"exam":"NEET"},

    # Commerce (subjects only, no cutoff)
    {"course":"B.Com","family":"Commerce","required":["Accountancy","Business Studies","Economics"],"cutoff":0,"exam":None},
    {"course":"BBA","family":"Commerce","required":["Accountancy","Business Studies","Economics"],"cutoff":0,"exam":None},
    {"course":"BBM","family":"Commerce","required":["Accountancy","Business Studies","Economics"],"cutoff":0,"exam":None},
    {"course":"CA","family":"Commerce","required":["Accountancy","Business Studies","Economics"],"cutoff":0,"exam":None},

    # Humanities (subjects only, no cutoff)
    {"course":"BA in History","family":"Humanities","required":["History","Political Science","Geography"],"cutoff":0,"exam":None},
    {"course":"BA in Psychology","family":"Humanities","required":["Psychology","Sociology","English"],"cutoff":0,"exam":None},
    {"course":"BA in Sociology","family":"Humanities","required":["Sociology","Political Science","History"],"cutoff":0,"exam":None},
    {"course":"BA in Political Science","family":"Humanities","required":["Political Science","History","Geography"],"cutoff":0,"exam":None},
    {"course":"BA in English","family":"Humanities","required":["English","History","Political Science"],"cutoff":0,"exam":None},
]

CATALOG_DF = pd.DataFrame(COURSE_CATALOG)

@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]

def validate_payload(payload: dict) -> ValidationResult:
    errors = []

    # Name
    name = str(payload.get("name","")).strip()
    if not NAME_RE.match(name):
        errors.append("Invalid name: only letters and spaces allowed.")

    # Age
    age = payload.get("age", None)
    if not isinstance(age, int) or not (17 <= age <= 25):
        errors.append("Invalid age: must be integer between 17 and 25.")

    # Gender
    gender = str(payload.get("gender","")).lower()
    if gender not in GENDER_SET:
        errors.append('Invalid gender: must be one of "Male", "Female", "Other".')

    # Desired course
    desired = str(payload.get("desired_course","")).strip()
    if desired not in set(CATALOG_DF["course"].tolist()):
        errors.append("Invalid desired_course: must be one of predefined courses.")

    # Marks
    marks = payload.get("marks", {})
    if not isinstance(marks, dict) or len(marks) < 3:  # must at least include required triplets later
        errors.append("Invalid marks: provide a dict of subjects to marks.")
    else:
        for subj, val in marks.items():
            try:
                v = float(val)
                if v < 0 or v > 100:
                    errors.append(f"Invalid marks for {subj}: {val} (must be 0-100).")
            except Exception:
                errors.append(f"Invalid marks (non-numeric) for {subj}: {val}.")

    # Exams
    exams = payload.get("qualification_exams", {})
    if not isinstance(exams, dict):
        errors.append("qualification_exams must be a dict (e.g., {'JEE': true, 'NEET': false}).")

    return ValidationResult(ok = len(errors)==0, errors = errors)

def fingerprint(name: str, age: int, gender: str) -> str:
    return f"{name.strip().lower()}|{age}|{gender.strip().lower()}"

def compute_eligibility(payload: dict) -> Tuple[bool, List[str], List[str]]:
    desired = payload["desired_course"]
    marks: Dict[str, float] = {k: float(v) for k,v in payload["marks"].items()}
    exams: Dict[str, bool] = {k.upper(): bool(v) for k,v in payload.get("qualification_exams", {}).items()}

    row = CATALOG_DF[CATALOG_DF["course"] == desired].iloc[0]
    required = row["required"]
    cutoff = row["cutoff"]
    exam_req = row["exam"]

    reasons: List[str] = []
    eligible = True

    # Check exam requirement
    if exam_req is not None:
        if exams.get(exam_req.upper(), False) is not True:
            eligible = False
            reasons.append(f"{desired} requires qualifying {exam_req}.")

    # Check required subjects presence
    for subj in required:
        if subj not in marks:
            eligible = False
            reasons.append(f"Missing required subject: {subj}.")

    # Check cutoff if applicable
    if cutoff and all(s in marks for s in required):
        req_scores = np.array([marks[s] for s in required], dtype=float)
        avg = float(np.mean(req_scores))
        if avg < cutoff:
            eligible = False
            reasons.append(f"Average across required subjects {required} is {avg:.1f}%, below cutoff {cutoff}%.")

    # Recommendations if not eligible
    recs: List[str] = []
    if not eligible:
        # 1) Same family with lower/equal requirements the student might meet
        # Check engineering path if PCM present but cutoff too high -> lower cutoff branches
        families = CATALOG_DF.groupby("family")
        # Filter courses where required subjects are subset of provided marks keys
        def has_required(req_list):
            return all(sub in marks for sub in req_list)

        subset = CATALOG_DF[CATALOG_DF["required"].apply(has_required)]
        # For those with exams, only include if exam passed
        def exam_ok(ex):
            return (ex is None) or exams.get(str(ex).upper(), False)

        subset = subset[subset["exam"].apply(exam_ok)]
        # For cutoffs, include ones where mean meets cutoff
        def meets_cutoff(row):
            if int(row["cutoff"]) == 0:
                return True
            arr = np.array([marks[s] for s in row["required"]], dtype=float)
            return float(np.mean(arr)) >= float(row["cutoff"])

        viable = subset[subset.apply(meets_cutoff, axis=1)]
        # Exclude the originally requested course (since it was ineligible)
        viable = viable[viable["course"] != desired]
        recs = viable["course"].tolist()[:5]  # top few

        # If still empty, provide closest matches ignoring cutoff (subject match + exam ok)
        if not recs:
            close = subset["course"].tolist()
            recs = [c for c in close if c != desired][:5]

        if not recs:
            # Fall back: list some Humanities/Commerce compatible courses solely by available subjects
            humcom = CATALOG_DF[(CATALOG_DF["family"].isin(["Humanities","Commerce"])) & (CATALOG_DF["required"].apply(has_required))]
            recs = humcom["course"].tolist()[:5]

        if not recs:
            recs = ["Consider improving exam eligibility or marks and reapplying."]

    return eligible, reasons, recs

def upsert_student(payload: dict) -> str:
    name = payload["name"]
    age = payload["age"]
    gender = payload["gender"]
    fp = fingerprint(name, age, gender)
    now = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        # Delete previous record with same fingerprint (if any)
        cur = conn.execute("SELECT student_id FROM students WHERE fp = ?", (fp,))
        row = cur.fetchone()
        if row:
            old_id = row[0]
            conn.execute("DELETE FROM decisions WHERE student_id = ?", (old_id,))
            conn.execute("DELETE FROM students WHERE student_id = ?", (old_id,))

        student_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO students(student_id, fp, name, age, gender, desired_course, request_json, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (student_id, fp, name, age, gender, payload["desired_course"], json.dumps(payload, ensure_ascii=False), now)
        )
        return student_id

def persist_decision(student_id: str, response: dict, eligible: bool, reasons: List[str], recs: List[str]):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO decisions(decision_id, student_id, eligible, reasons, recommendations, response_json, created_at) VALUES(?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), student_id, int(eligible), json.dumps(reasons, ensure_ascii=False), json.dumps(recs, ensure_ascii=False), json.dumps(response, ensure_ascii=False), now)
        )
