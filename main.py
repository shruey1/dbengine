"""main.py — FastAPI backend for Agentic Schema Modelling"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.graph.langgraph_flow import (
    run_generate_model,
    run_auto_validate_and_sql,
    run_apply_feedback_and_sql,
    run_approve_and_generate_sql,
)
from backend.agents.erd_generator import generate_erd_base64, generate_erd_xml, generate_erd_from_model

# Load .env
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    load_dotenv()

app = FastAPI(title="Agentic Schema Modelling Service", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ── Request models ─────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    user_query:     str
    operation:      Optional[str]            = ""
    existing_model: Optional[Dict[str, Any]] = None
    model_type:     Optional[str]            = "both"   # relational | analytical | both
    db_engine:      Optional[str]            = ""       # empty = auto-detect from prompt


class ValidateRequest(BaseModel):
    data_model: Dict[str, Any]
    operation:  str = "CREATE"


class ApproveRequest(BaseModel):
    data_model: Dict[str, Any]
    operation:  str = "CREATE"


class FeedbackRequest(BaseModel):
    data_model: Dict[str, Any]
    feedback:   str
    operation:  str = "CREATE"


class ERDRequest(BaseModel):
    sql:   str
    title: Optional[str] = "Entity Relationship Diagram"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/workflow/generate")
def generate(req: GenerateRequest):
    try:
        result = run_generate_model(
            user_input=req.user_query,
            operation=req.operation or "",
            existing_model=req.existing_model,
            model_type=req.model_type or "both",
            db_engine=req.db_engine or "",
        )
        return {"status": "success", "timestamp": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.exception("Error in /workflow/generate")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/validate")
def validate(req: ValidateRequest):
    try:
        # Ensure db_type is preserved in the model before SQL generation
        model = req.data_model
        result = run_auto_validate_and_sql(model, req.operation)
        return {"status": "success", "timestamp": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.exception("Error in /workflow/validate")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/approve")
def approve(req: ApproveRequest):
    try:
        result = run_approve_and_generate_sql(req.data_model, req.operation)
        return {"status": "success", "timestamp": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.exception("Error in /workflow/approve")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/feedback")
def feedback(req: FeedbackRequest):
    try:
        result = run_apply_feedback_and_sql(req.data_model, req.feedback, req.operation)
        return {"status": "success", "timestamp": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.exception("Error in /workflow/feedback")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/erd")
def generate_erd(req: ERDRequest):
    try:
        result = generate_erd_base64(req.sql, req.title)
        return {"status": "success", "timestamp": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.exception("Error in /workflow/erd")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/erd/xml")
def generate_erd_xml_endpoint(req: ERDRequest):
    try:
        result = generate_erd_xml(req.sql, req.title)
        return {"status": "success", "timestamp": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.exception("Error in /workflow/erd/xml")
        raise HTTPException(status_code=500, detail=str(e))


class ERDFromModelRequest(BaseModel):
    data_model: Dict[str, Any]
    title: Optional[str] = "Entity Relationship Diagram"


@app.post("/workflow/erd/from-model")
def generate_erd_from_model_endpoint(req: ERDFromModelRequest):
    """
    Generate ERD directly from a JSON data model — skips SQL generation.
    Used at the Review Model step so the user can visualise before validating.
    """
    try:
        result = generate_erd_from_model(req.data_model, req.title)
        return {"status": "success", "timestamp": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.exception("Error in /workflow/erd/from-model")
        raise HTTPException(status_code=500, detail=str(e))