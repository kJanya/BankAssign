from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, Response
from typing import Any, Dict

from .db import init_db
from .schemas import EligibilityInput, EligibilityOutput
from .eligibility import (
    validate_payload,
    compute_eligibility,
    upsert_student,
    persist_decision,
)
from .logger import log_payload

app = FastAPI(title="College Eligibility API", version="1.0.0")

# Initialize DB at import time
init_db()

# --- Convenience routes ---
@app.get("/", include_in_schema=False)
def home():
    # Locally this redirects to /docs; on Vercel you’ll typically use /api/docs.
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "healthy"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Avoid 404 log spam from browsers requesting a favicon.
    return Response(status_code=204)
# --- End convenience routes ---


@app.post("/check_eligibility", response_model=EligibilityOutput)
async def check_eligibility(payload: EligibilityInput):
    # Convert to dict early for logging and custom validation (regex rules etc.)
    payload_dict: Dict[str, Any] = payload.dict()
    log_payload("in", payload_dict)

    v = validate_payload(payload_dict)
    if not v.ok:
        # Still log a structured error output
        out = {
            "student_id": "",
            "desired_course": payload_dict.get("desired_course", ""),
            "eligible": False,
            "reasons": v.errors,
            "recommendations": [],
        }
        log_payload("out", out)
        raise HTTPException(status_code=422, detail=v.errors)

    try:
        student_id = upsert_student(payload_dict)
        eligible, reasons, recs = compute_eligibility(payload_dict)
        response = {
            "student_id": student_id,
            "desired_course": payload_dict["desired_course"],
            "eligible": eligible,
            "reasons": reasons,
            "recommendations": recs,
        }
        persist_decision(student_id, response, eligible, reasons, recs)
        log_payload("out", response)
        return JSONResponse(content=response)
    except Exception as e:
        # Graceful error handling
        err = {
            "student_id": "",
            "desired_course": payload_dict.get("desired_course", ""),
            "eligible": False,
            "reasons": [f"Internal error: {str(e)}"],
            "recommendations": [],
        }
        log_payload("out", err)
        raise HTTPException(status_code=500, detail="Internal Server Error")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
