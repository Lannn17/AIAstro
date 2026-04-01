import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..db import db_insert_prompt_evaluation, db_insert_user_feedback
from ..security import get_optional_user

router = APIRouter(prefix="/api/user", tags=["user"])

VALID_CALLERS = {
    "interpret_planets", "transits_full_new", "transits_full_summary",
    "analyze_synastry", "analyze_solar_return", "analyze_rectification",
    "chat_with_chart", "generate", "generate_asc_quiz", "calc_confidence", "system",
}


class UserEvalRequest(BaseModel):
    log_id: str
    score: int
    notes: str = ""


class FeedbackRequest(BaseModel):
    caller_label: str
    content: str


@router.post("/prompt-evaluations")
def submit_user_eval(body: UserEvalRequest, user=Depends(get_optional_user)):
    if body.score not in (1, 3, 5):
        raise HTTPException(400, "score must be 1, 3, or 5")
    eval_id = uuid.uuid4().hex[:16]
    db_insert_prompt_evaluation(
        id_=eval_id, log_id=body.log_id, version_id=None,
        evaluator_type="user",
        score_overall=float(body.score),
        dimensions=None,
        notes=body.notes or None,
        suggestions=None,
    )
    return {"id": eval_id, "status": "ok"}


@router.post("/feedback")
def submit_feedback(body: FeedbackRequest, user=Depends(get_optional_user)):
    caller = body.caller_label if body.caller_label in VALID_CALLERS else None
    fb_id = uuid.uuid4().hex[:16]
    user_id = str(user["user_id"]) if user and user.get("user_id") else None
    db_insert_user_feedback(
        id_=fb_id,
        caller=caller,
        content=body.content,
        user_id=user_id,
    )
    return {"id": fb_id, "status": "ok"}