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


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()

    # Strip code fences (``` or ```json ... ```)
    if "`" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

    # Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first { ... } block
    m = re.search(r"{[\s\S]*}", cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.error("JSON parse failed. Raw (500 chars): %s", raw[:500])
    return {"parse_error": True, "raw": raw}


def _invoke_llm(llm, prompt_text: str) -> dict:
    try:
        resp = llm.invoke(prompt_text)
        result = _parse_json(resp.content)
        logger.info("LLM response keys: %s", list(result.keys()) if isinstance(result, dict) else type(result))
        return result
    except Exception as e:
        logger.error("LLM error: %s", e)
        return {"error": str(e)}


# ── Prompt builders ───────────────────────────────────────────────────────────

def _relational_prompt(request: str, db_type: str) -> str:
    return f"""
You are a senior database architect specialising in normalised relational models.
Given the user request below, produce a RELATIONAL data model following these rules:
- Apply 3rd Normal Form (3NF).
- Every table must have a primary key.
- Express all foreign-key relationships explicitly.
- Use data types appropriate for {db_type}.
- Include NOT NULL, UNIQUE, and CHECK constraints where appropriate.
- Do NOT output any SQL DDL — output structured JSON only.
- Target database: {db_type}
Output ONLY valid JSON with no markdown fences, no extra commentary, using exactly this structure:
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
          "type": "SQL_type",
          "nullable": false,
          "primary_key": false,
          "unique": false,
          "default": null,
          "description": "brief description"
        }}
      ],
      "primary_key": ["col_name"],
      "indexes": [
        {{"name": "idx_name", "columns": ["col"], "unique": false}}
      ]
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
""".strip()


def _analytical_prompt(request: str, db_type: str) -> str:
    return f"""
You are a senior data warehouse architect specialising in dimensional modelling.
Given the user request below, produce an ANALYTICAL data model (Star Schema) following these rules:
- Design a star schema with central fact tables and surrounding dimension tables.
- Fact tables hold measurable numeric metrics and foreign keys to dimensions.
- Dimension tables hold descriptive attributes.
- Use surrogate integer keys as primary keys in dimension tables.
- Use data types appropriate for {db_type}.
- Do NOT output any SQL DDL — output structured JSON only.
- Target database: {db_type}
Output ONLY valid JSON with no markdown fences, no extra commentary, using exactly this structure:
{{
  "model_type": "analytical",
  "schema_pattern": "star",
  "db_type": "{db_type}",
  "fact_tables": [
    {{
      "name": "fact_table_name",
      "description": "what business process this measures",
      "grain": "one sentence describing one row",
      "columns": [
        {{
          "name": "col_name",
          "type": "SQL_type",
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
      "description": "what entity this describes",
      "scd_type": 1,
      "columns": [
        {{
          "name": "col_name",
          "type": "SQL_type",
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
      "cardinality": "many-to-one"
    }}
  ]
}}
User Request: {request}
""".strip()


def _modification_prompt(existing_model: dict, request: str) -> str:
    return f"""
You are a senior database architect.
Apply the requested changes to the existing data model and return a complete updated JSON.
Preserve all unchanged parts exactly.
Modification Request: {request}
Existing Model:
{json.dumps(existing_model, indent=2)}
Return ONLY valid JSON of the complete updated model — no markdown, no commentary.
""".strip()


# ── Agent ─────────────────────────────────────────────────────────────────────

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
        """
        Generate JSON data model(s).
        model_type: 'relational' | 'analytical' | 'both'
        """
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
            result["relational_model"] = self.apply_modification(existing_model, request)
        return result


# ── Convenience functions ─────────────────────────────────────────────────────

def create_schema(request: str, model_type: str = "both", db_engine: str = "MySQL") -> dict:
    return SchemaAgent(db_engine=db_engine).process_create(request, model_type=model_type)


def modify_schema(request: str, existing_model: dict, db_engine: str = "MySQL") -> dict:
    return SchemaAgent(db_engine=db_engine).process_modify(request, existing_model)