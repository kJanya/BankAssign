
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional

class EligibilityInput(BaseModel):
    name: str = Field(..., description="Full name")
    age: int = Field(..., ge=0)
    gender: str
    desired_course: str
    marks: Dict[str, float] = Field(..., description="Six subjects with marks 0-100")
    qualification_exams: Dict[str, bool] = Field(..., description="e.g., {'JEE': true, 'NEET': false}")

class EligibilityOutput(BaseModel):
    student_id: str
    desired_course: str
    eligible: bool
    reasons: list
    recommendations: list
