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


# -------------------------------------------------------------------------
# LLM Loader
# -------------------------------------------------------------------------
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


# -------------------------------------------------------------------------
# JSON Parser
# -------------------------------------------------------------------------
def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()

    if "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]

    if cleaned.startswith("json"):
        cleaned = cleaned[4:]

    cleaned = cleaned.strip()

    # Try direct load
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: extract JSON block
    m = re.search(r"{[\s\S]*}", cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.error("JSON parse failed. Raw (500 chars): %s", raw[:500])
    return {"parse_error": True, "raw": raw}


# -------------------------------------------------------------------------
# LLM Invocation Wrapper
# -------------------------------------------------------------------------
def _invoke_llm(llm, prompt_text: str) -> dict:
    try:
        resp = llm.invoke(prompt_text)
        result = _parse_json(resp.content)
        logger.info(
            "LLM response keys: %s",
            list(result.keys()) if isinstance(result, dict) else type(result),
        )
        return result
    except Exception as e:
        logger.error("LLM error: %s", e)
        return {"error": str(e)}


# -------------------------------------------------------------------------
# Engine-Specific Rules
# -------------------------------------------------------------------------
def _engine_hints(db_type: str) -> str:
    hints = {
        "BigQuery": """
Engine-specific rules for BigQuery:
- Use BigQuery native types: STRING, INT64, FLOAT64, NUMERIC, BOOL, DATE, DATETIME, TIMESTAMP, BYTES, JSON.
- Do NOT use VARCHAR, INT, INTEGER, FLOAT, BOOLEAN, TEXT.
- All constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE) must be marked NOT ENFORCED.
- Default values are mostly unsupported (no AUTO_INCREMENT, no SERIAL, no IDENTITY).
- BigQuery requires fully qualified names: project.dataset.table.
- BigQuery does not support CREATE INDEX.
- Use STRUCT and ARRAY<STRUCT<...>> for nested objects.
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
- PK/FK constraints are accepted but NOT enforced — avoid ON DELETE CASCADE.
- Do NOT generate indexes — Snowflake does not support CREATE INDEX.
- Supports AUTOINCREMENT or IDENTITY for surrogate keys.
- Default expressions using functions may require careful validation.
        """,

        "SQLite": """
Engine-specific rules for SQLite:
- Use TEXT, INTEGER, REAL, BLOB, NUMERIC (SQLite storage classes).
- BOOLEAN should be mapped to INTEGER.
- PRAGMA foreign_keys = ON; should be noted when using FK relationships.
- Use INTEGER PRIMARY KEY for auto-increment (rowid alias).
- Very limited CHECK/FOREIGN KEY enforcement.
        """,

        "MySQL": """
Engine-specific rules for MySQL:
- Use VARCHAR(n), TEXT, INT, BIGINT, TINYINT(1), DECIMAL, DATETIME(6), TIMESTAMP, JSON.
- BOOLEAN maps to TINYINT(1).
- Auto-increment keys must use AUTO_INCREMENT.
- ENGINE=InnoDB DEFAULT CHARSET=utf8mb4.
- Supports UNIQUE, CHECK, indexes, and ON DELETE CASCADE.
- JSON is supported but cannot be indexed directly without virtual columns.
        """,
    }

    return hints.get(db_type, f"\nUse data types and constraints appropriate for {db_type}.\n")


# -------------------------------------------------------------------------
# Relational Model Prompt
# -------------------------------------------------------------------------
def _relational_prompt(request: str, db_type: str) -> str:
    return f"""
You are a senior database architect specialising in normalised relational models.

Given the user request below, produce a RELATIONAL data model following these rules:
- Apply 3rd Normal Form (3NF)
- Every table must have a primary key
- Express all foreign-key relationships explicitly
- Use data types appropriate for {db_type}
- DO NOT output SQL — output structured JSON only

Target database: {db_type}
{_engine_hints(db_type)}

Output ONLY valid JSON, using this structure:

{{
  "model_type": "relational",
  "normal_form": "3NF",
  "db_type": "{db_type}",
  "tables": [
    {{
      "name": "table_name",
      "description": "one sentence purpose",
      "columns": [
        {{
          "name": "col_name",
          "type": "SQL_type_for_{db_type}",
          "nullable": false,
          "primary_key": false,
          "unique": false,
          "default": null,
          "description": "brief description"
        }}
      ],
      "primary_key": ["col_name"],
      "indexes": []
    }}
  ],
  "relationships": [
    {{
      "name": "fk_name",
      "from_table": "table",
      "from_column": "col",
      "to_table": "table",
      "to_column": "col",
      "on_delete": "CASCADE",
      "cardinality": "one-to-many"
    }}
  ]
}}

User Request: {request}
"""


# -------------------------------------------------------------------------
# Analytical Model Prompt
# -------------------------------------------------------------------------
def _analytical_prompt(request: str, db_type: str) -> str:
    return f"""
You are a senior data warehouse architect specialising in dimensional modelling.

Produce a STAR SCHEMA analytical model:
- Fact tables contain numeric metrics and FK references
- Dimensions contain descriptive attributes
- Use surrogate keys
- JSON output only
- Target: {db_type}

{_engine_hints(db_type)}

Output JSON using this structure:

{{
  "model_type": "analytical",
  "schema_pattern": "star",
  "db_type": "{db_type}",
  "fact_tables": [
    {{
      "name": "fact_table_name",
      "description": "business process measured",
      "grain": "one row represents...",
      "columns": [
        {{
          "name": "col_name",
          "type": "SQL_type_for_{db_type}",
          "nullable": false,
          "primary_key": false,
          "is_measure": false,
          "is_foreign_key": false,
          "description": "brief description"
        }}
      ],
      "primary_key": ["col_name"],
      "measures": ["measure_col_names"]
    }}
  ],
  "dimension_tables": [
    {{
      "name": "dim_table_name",
      "description": "what the dimension describes",
      "scd_type": 1,
      "columns": [
        {{
          "name": "col_name",
          "type": "SQL_type_for_{db_type}",
          "nullable": false,
          "primary_key": false,
          "description": "brief description"
        }}
      ],
      "primary_key": ["col_name"]
    }}
  ],
  "relationships": [
    {{
      "from_table": "fact_table",
      "from_column": "fk_col",
      "to_table": "dim_table",
      "to_column": "pk_col",
      "on_delete": null,
      "cardinality": "many-to-one"
    }}
  ]
}}

User Request: {request}
"""


# -------------------------------------------------------------------------
# Modification Prompt
# -------------------------------------------------------------------------
def _modification_prompt(existing_model: dict, request: str) -> str:
    return f"""
You are a senior database architect.

Apply the requested modification to the existing model.
Return the FULL UPDATED MODEL — valid JSON only.

Modification Request:
{request}

Existing Model:
{json.dumps(existing_model, indent=2)}
"""


# -------------------------------------------------------------------------
# Schema Agent
# -------------------------------------------------------------------------
class SchemaAgent:
    def __init__(self, db_engine: str = "MySQL"):
        self.llm = _get_llm(temperature=0.1)
        self.db_type = db_engine or os.getenv("DATABASE_TYPE", "MySQL")

    def generate_relational_model(self, request: str) -> dict:
        if not self.llm:
            return {"error": "LLM not configured"}
        return _invoke_llm(self.llm, _relational_prompt(request, self.db_type))

    def generate_analytical_model(self, request: str) -> dict:
        if not self.llm:
            return {"error": "LLM not configured"}
        return _invoke_llm(self.llm, _analytical_prompt(request, self.db_type))

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
        if "relational_model" in existing_model:
            result["relational_model"] = self.apply_modification(
                existing_model["relational_model"], request
            )
        if "analytical_model" in existing_model:
            result["analytical_model"] = self.apply_modification(
                existing_model["analytical_model"], request
            )
        if not result:
            result["relational_model"] = self.apply_modification(
                existing_model, request
            )
        return result


# -------------------------------------------------------------------------
# Convenience functions
# -------------------------------------------------------------------------
def create_schema(request: str, model_type: str = "both", db_engine: str = "MySQL") -> dict:
    return SchemaAgent(db_engine=db_engine).process_create(request, model_type=model_type)


def modify_schema(request: str, existing_model: dict, db_engine: str = "MySQL") -> dict:
    return SchemaAgent(db_engine=db_engine).process_modify(request, existing_model)