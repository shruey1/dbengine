"""
Agent responsible for generating structured JSON data models.
"""

import os
import json
import logging
import re
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# LLM Loader
# ------------------------------------------------------------
def _get_llm(temperature: float = 0.1):
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    if not (api_key and endpoint and deployment):
        logger.error("Azure OpenAI credentials not found")
        return None

    return AzureChatOpenAI(
        api_key=api_key,
        api_version="2024-02-15-preview",
        azure_endpoint=endpoint,
        model=deployment,
        temperature=temperature,
    )


# ------------------------------------------------------------
# JSON Parser
# ------------------------------------------------------------
def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()

    # Handle ```json blocks
    if "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]

    if cleaned.startswith("json"):
        cleaned = cleaned[4:]

    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: extract {...}
    m = re.search(r"{[\s\S]*}", cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.error("JSON parse failed. Raw (500 chars): %s", raw[:500])
    return {"parse_error": True, "raw": raw}


# ------------------------------------------------------------
# LLM Invocation Wrapper
# ------------------------------------------------------------
def _invoke_llm(llm, prompt_text: str) -> dict:
    try:
        resp = llm.invoke(prompt_text)
        result = _parse_json(resp.content)
        logger.info("LLM response keys: %s", list(result.keys()) if isinstance(result, dict) else type(result))
        return result
    except Exception as e:
        logger.error("LLM error: %s", e)
        return {"error": str(e)}


# ------------------------------------------------------------
# Namespace Extraction
# ------------------------------------------------------------
def _extract_namespace(request: str, db_type: str) -> dict:
    result = {}

    if db_type == "BigQuery":
        m = re.search(r"`?([\w-]+)\.([\w-]+)`?", request)
        if m:
            result["project"] = m.group(1)
            result["dataset"] = m.group(2)
        else:
            pm = re.search(r'\bproject[:\s]+([`\w-]+)', request, re.IGNORECASE)
            dm = re.search(r'\bdataset[:\s]+([`\w-]+)', request, re.IGNORECASE)
            if pm:
                result["project"] = pm.group(1).strip('`')
            if dm:
                result["dataset"] = dm.group(1).strip('`')
    else:
        m = re.search(r"`?([\w-]+)\.([\w-]+)`?", request)
        if m:
            result["schema"] = m.group(1)
        else:
            sm = re.search(r'\b(?:schema|database|db)[:\s]+([`\w-]+)', request, re.IGNORECASE)
            if sm:
                result["schema"] = sm.group(1).strip('`')

    logger.info("Extracted namespace for %s: %s", db_type, result)
    return result


# ------------------------------------------------------------
# Namespace Stamping
# ------------------------------------------------------------
def _stamp_namespace(model: dict, namespace: dict, db_type: str) -> dict:
    if not namespace or not model or model.get("parse_error"):
        return model

    def _prefix(table_name: str) -> str:
        if "." in table_name:
            return table_name
        if db_type == "BigQuery":
            project = namespace.get("project", "")
            dataset = namespace.get("dataset", "")
            if project and dataset:
                return f"{project}.{dataset}.{table_name}"
            if dataset:
                return f"{dataset}.{table_name}"
        else:
            schema = namespace.get("schema", "")
            if schema:
                return f"{schema}.{table_name}"
        return table_name

    def _patch_tables(table_list: list) -> list:
        return [{**t, "name": _prefix(t["name"])} for t in table_list]

    def _patch_relationships(rel_list: list) -> list:
        return [
            {**r,
             "from_table": _prefix(r["from_table"]),
             "to_table": _prefix(r["to_table"])}
            for r in rel_list
        ]

    model = dict(model)

    for key in ("tables", "fact_tables", "dimension_tables"):
        if key in model:
            model[key] = _patch_tables(model[key])

    if "relationships" in model:
        model["relationships"] = _patch_relationships(model["relationships"])

    model["namespace"] = namespace
    return model


# ------------------------------------------------------------
# Engine-Specific Hints
# ------------------------------------------------------------
def _engine_hints(db_type: str) -> str:
    hints = {
        "BigQuery": """
Engine-specific rules for BigQuery:
- Use BigQuery native types: STRING, INT64, FLOAT64, NUMERIC, BOOL, DATE, DATETIME, TIMESTAMP, BYTES, JSON.
- Do NOT use VARCHAR, INT, INTEGER, FLOAT, BOOLEAN, TEXT.
- All constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE) must be marked NOT ENFORCED.
- No AUTO_INCREMENT, SERIAL, or IDENTITY.
- BigQuery requires fully qualified names: project.dataset.table.
- BigQuery does not support CREATE INDEX.
- No ON DELETE CASCADE — foreign keys are informational only.
""",
        "PostgreSQL": """
Engine-specific rules for PostgreSQL:
- Preferred types: TEXT, VARCHAR(n), INTEGER, BIGINT, BOOLEAN, JSONB, UUID, TIMESTAMPTZ, NUMERIC.
- SERIAL is deprecated — use GENERATED ALWAYS AS IDENTITY.
- Supports UNIQUE, CHECK, composite keys, and indexes.
- Supports ON DELETE CASCADE and full referential integrity.
- Use JSONB instead of JSON unless required.
""",
        "MSSQL": """
Engine-specific rules for SQL Server:
- Use NVARCHAR(n), NVARCHAR(MAX), INT, BIGINT, BIT, DECIMAL(p,s), DATETIME2, UNIQUEIDENTIFIER.
- Auto-increment keys must use IDENTITY(1,1).
- Avoid deprecated TEXT type.
- Supports UNIQUE, CHECK, indexes, and ON DELETE CASCADE.
""",
        "Snowflake": """
Engine-specific rules for Snowflake:
- Supported types: VARCHAR, NUMBER, FLOAT, BOOLEAN, DATE, TIMESTAMP_NTZ, VARIANT, ARRAY, OBJECT.
- PK/FK constraints are accepted but NOT enforced.
- Do NOT generate indexes — Snowflake does not support CREATE INDEX.
- Supports AUTOINCREMENT or IDENTITY for surrogate keys.
""",
        "SQLite": """
Engine-specific rules for SQLite:
- Use TEXT, INTEGER, REAL, BLOB, NUMERIC (SQLite storage classes).
- BOOLEAN should be mapped to INTEGER.
- Use INTEGER PRIMARY KEY for auto-increment.
- Very limited CHECK/FOREIGN KEY enforcement.
""",
        "MySQL": """
Engine-specific rules for MySQL:
- Use VARCHAR(n), TEXT, INT, BIGINT, TINYINT(1), DECIMAL, DATETIME(6), TIMESTAMP, JSON.
- BOOLEAN maps to TINYINT(1).
- Auto-increment keys must use AUTO_INCREMENT.
- ENGINE=InnoDB DEFAULT CHARSET=utf8mb4.
""",
        "Redshift": """
Engine-specific rules for Redshift:
- Use VARCHAR, TEXT, INTEGER, BIGINT, SMALLINT, DECIMAL, REAL, DOUBLE PRECISION, BOOLEAN, DATE, TIMESTAMP, TIMESTAMPTZ, SUPER.
- Do NOT use SERIAL — use IDENTITY(0,1) for auto-increment columns.
- Foreign keys are declared but NOT enforced.
- Do NOT add indexes — Redshift does not support CREATE INDEX.
- Suggest dist_key and sort_keys.
""",
    }

    return hints.get(db_type, f"\nUse data types and constraints appropriate for {db_type}.\n")


# ------------------------------------------------------------
# SCD Rules
# ------------------------------------------------------------
_SCD_RULES = """
SCD (Slowly Changing Dimension) type selection rules — apply to EVERY dimension table:
- SCD Type 0 : Static / never changes.
- SCD Type 1 : Overwrite old value.
- SCD Type 2 : Add new row with effective/expiry dates and is_current.
- SCD Type 3 : Track only one previous value.
- SCD Type 4 : Separate history table.
- SCD Type 6 : Hybrid of 1+2+3.
"""


# ------------------------------------------------------------
# Prompt Summary
# ------------------------------------------------------------
def get_prompt_summary(request: str, db_type: str, model_type: str) -> dict:
    engine_summary = {
        "BigQuery": "BigQuery types · NOT ENFORCED constraints · fully-qualified names · no indexes",
        "PostgreSQL": "TEXT/JSONB/UUID · IDENTITY · indexes · CASCADE",
        "MSSQL": "NVARCHAR/IDENTITY · DATETIME2 · CASCADE",
        "Snowflake": "VARCHAR/NUMBER/VARIANT · AUTOINCREMENT · no indexes",
        "SQLite": "TEXT/INTEGER/REAL · limited FK",
        "MySQL": "VARCHAR/INT/AUTO_INCREMENT · InnoDB · CASCADE",
        "Redshift": "VARCHAR/SUPER/IDENTITY · no indexes · dist/sort keys",
    }.get(db_type, f"Standard SQL for {db_type}")

    return {
        "db_engine": db_type,
        "model_type": model_type,
        "normal_form": "3NF" if model_type in ("relational", "both") else "N/A",
        "schema_pattern": "Star Schema" if model_type in ("analytical", "both") else "N/A",
        "engine_rules": engine_summary,
        "scd_applied": model_type in ("analytical", "both"),
        "scd_summary": "SCD 0–6 per dimension" if model_type in ("analytical", "both") else "Not applicable",
        "namespace_extraction": "project.dataset auto-detected (BigQuery)" if db_type == "BigQuery" else "schema auto-detected",
    }


# ------------------------------------------------------------
# Relational Model Prompt
# ------------------------------------------------------------
def _relational_prompt(request: str, db_type: str) -> str:
    return f"""
You are a senior database architect specialising in 3NF relational models.

Target database: {db_type}
{_engine_hints(db_type)}

Output ONLY valid JSON:
{{
  "model_type": "relational",
  "normal_form": "3NF",
  "db_type": "{db_type}",
  "tables": [],
  "relationships": []
}}

User Request: {request}
"""


# ------------------------------------------------------------
# Analytical Model Prompt
# ------------------------------------------------------------
def _analytical_prompt(request: str, db_type: str) -> str:
    return f"""
You are a senior data warehouse architect specialising in STAR SCHEMA modelling.

Target: {db_type}
{_engine_hints(db_type)}
{_SCD_RULES}

Output ONLY JSON:
{{
  "model_type": "analytical",
  "schema_pattern": "star",
  "db_type": "{db_type}",
  "fact_tables": [],
  "dimension_tables": [],
  "relationships": []
}}

User Request: {request}
"""


# ------------------------------------------------------------
# Modification Prompt
# ------------------------------------------------------------
def _modification_prompt(existing_model: dict, request: str) -> str:
    return f"""
You are a senior database architect.
Apply the requested modification.

Return FULL UPDATED MODEL as JSON.

Modification Request:
{request}

Existing Model:
{json.dumps(existing_model, indent=2)}
"""


# ------------------------------------------------------------
# SchemaAgent Class
# ------------------------------------------------------------
class SchemaAgent:
    def __init__(self, db_engine: str = "MySQL"):
        self.llm = _get_llm(temperature=0.1)
        self.db_type = db_engine or os.getenv("DATABASE_TYPE", "MySQL")

    def generate_relational_model(self, request: str) -> dict:
        if not self.llm:
            return {"error": "LLM not configured"}

        model = _invoke_llm(self.llm, _relational_prompt(request, self.db_type))
        namespace = _extract_namespace(request, self.db_type)
        return _stamp_namespace(model, namespace, self.db_type)

    def generate_analytical_model(self, request: str) -> dict:
        if not self.llm:
            return {"error": "LLM not configured"}

        model = _invoke_llm(self.llm, _analytical_prompt(request, self.db_type))
        namespace = _extract_namespace(request, self.db_type)
        return _stamp_namespace(model, namespace, self.db_type)

    def apply_modification(self, existing_model: dict, request: str) -> dict:
        if not self.llm:
            return {"error": "LLM not configured"}

        return _invoke_llm(self.llm, _modification_prompt(existing_model, request))
    def process_create(self, request: str, model_type: str = "both") -> dict:
        result = {}

        if model_type in ("relational", "both"):
            result["relational_model"] = self.generate_relational_model(request)

        if model_type in ("analytical", "both"):
            result["analytical_model"] = self.generate_analytical_model(request)

        return result


def process_modify(self, request: str, existing_model: dict) -> dict:
    result = {}

    # If the existing model has separate relational/analytical parts
    if "relational_model" in existing_model:
        result["relational_model"] = self.apply_modification(
            existing_model["relational_model"], request
        )

    if "analytical_model" in existing_model:
        result["analytical_model"] = self.apply_modification(
            existing_model["analytical_model"], request
        )

    # If it's a single model, modify directly
    if not result:
        result["relational_model"] = self.apply_modification(existing_model, request)

    return result


# ------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------
def create_schema(request: str, model_type: str = "both", db_engine: str = "MySQL") -> dict:
    return SchemaAgent(db_engine=db_engine).process_create(request, model_type=model_type)


def modify_schema(request: str, existing_model: dict, db_engine: str = "MySQL") -> dict:
    return SchemaAgent(db_engine=db_engine).process_modify(request, existing_model)
    