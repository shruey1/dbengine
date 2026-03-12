"""
LangGraph workflow for schema modelling — JSON-first, then SQL.
"""

from __future__ import annotations

import re
import json
import logging
from typing import Any, Dict, Optional, TypedDict
from dotenv import load_dotenv

from backend.agents.classifier import classify_request
from backend.agents.schema_agent import create_schema, modify_schema
from backend.agents.validation_agent import validate_model
from backend.agents.sql_generator import generate_sql_from_model

load_dotenv()

logger = logging.getLogger(__name__)

# ── DB engine detection ───────────────────────────────────────────────────────
# Known engines and common aliases / keywords users might type
_ENGINE_PATTERNS = [
    (r'\bpostgres(?:ql)?\b',        'PostgreSQL'),
    (r'\bmssql\b|\bsql\s*server\b', 'MSSQL'),
    (r'\bbigquery\b',               'BigQuery'),
    (r'\bsnowflake\b',              'Snowflake'),
    (r'\bsqlite\b',                 'SQLite'),
    (r'\boracle\b',                 'Oracle'),
    (r'\bredshift\b',               'Redshift'),
    (r'\bmysql\b',                  'MySQL'),
]


def detect_db_engine(text: str, explicit_engine: str = '') -> str:
    """
    Return the database engine to use.
    Priority: explicit UI selection > keyword in prompt > default MySQL.
    """
    if explicit_engine and explicit_engine.strip():
        logger.info("DB engine from UI selection: %s", explicit_engine)
        return explicit_engine.strip()

    lower = text.lower()
    for pattern, engine in _ENGINE_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            logger.info("DB engine detected from prompt: %s", engine)
            return engine

    logger.info("No DB engine found — defaulting to MySQL")
    return 'MySQL'


# ── Public entry points ───────────────────────────────────────────────────────
def run_generate_model(
    user_input: str,
    operation: str = '',
    existing_model: dict = None,
    model_type: str = 'both',       # 'relational' | 'analytical' | 'both'
    db_engine: str = '',            # explicit engine from UI (may be empty)
) -> dict:
    """
    Step 1: classify + generate JSON data model only.
    Respects model_type (relational / analytical / both).
    Detects or uses the specified db_engine.
    """
    # Resolve operation
    op = operation or classify_request(user_input)

    # Resolve DB engine
    engine = detect_db_engine(user_input, db_engine)
    try:
        if op == 'CREATE':
            data_model = create_schema(user_input, model_type=model_type, db_engine=engine)
        else:
            data_model = modify_schema(user_input, existing_model or {}, db_engine=engine)
        # Stamp db_type onto the model so sql_generator reads it later
        data_model['db_type'] = engine
        error = None
    except Exception as exc:
        logger.exception("Error generating model")
        data_model = {}
        error = str(exc)

    return {
        'data_model': data_model,
        'operation':  op,
        'db_engine':  engine,
        'error':      error,
    }


def run_auto_validate_and_sql(data_model: dict, operation: str) -> dict:
    """Step 2 AUTO: validate model then generate SQL."""
    # Log what db_type we received — helps debug engine not being respected
    db_type = data_model.get('db_type') or 'NOT SET — will default to MySQL'
    logger.info("run_auto_validate_and_sql: db_type received = %s", db_type)

    try:
        validated = validate_model(data_model)
    except Exception as exc:
        validated = {'is_valid': False, 'score': 0, 'errors': [str(exc)], 'warnings': [], 'suggestions': []}

    # Always attempt SQL so user isn't left with nothing
    try:
        sql = generate_sql_from_model(data_model)
        logger.info("run_auto_validate_and_sql: SQL generated for db_type = %s", sql.get('db_type'))
    except Exception as exc:
        sql = {}
        logger.error("SQL generation error: %s", exc)

    return {
        'validation': validated,
        'sql_output': sql,
        'data_model': data_model,
    }


def run_apply_feedback_and_sql(data_model: dict, feedback: str, operation: str) -> dict:
    """Manual path: apply user feedback, then generate SQL."""
    try:
        updated_model = modify_schema(feedback, data_model)
        error = None
    except Exception as exc:
        updated_model = data_model
        error = str(exc)

    try:
        sql = generate_sql_from_model(updated_model)
    except Exception as exc:
        sql = {}
        error = str(exc)

    return {'data_model': updated_model, 'sql_output': sql, 'error': error}


def run_approve_and_generate_sql(data_model: dict, operation: str) -> dict:
    """Manual path: user approved model, generate SQL."""
    try:
        sql = generate_sql_from_model(data_model)
        error = None
    except Exception as exc:
        sql = {}
        error = str(exc)

    return {'data_model': data_model, 'sql_output': sql, 'error': error}