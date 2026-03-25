"""
Agent responsible for generating SQL DDL from a validated JSON data model.
"""

import os
import json
import re
import logging
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# LLM Loader
# -------------------------------------------------------------------------
def _get_llm():
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    if not (api_key and endpoint and deployment):
        return None

    return AzureChatOpenAI(
        api_key=api_key,
        api_version="2024-02-15-preview",
        azure_endpoint=endpoint,
        model=deployment,
        temperature=0,
        max_tokens=4096,   # FIX 1
    )


# -------------------------------------------------------------------------
# Resolve Database Type
# -------------------------------------------------------------------------
def _resolve_db_type(validated_model: dict) -> str:
    if validated_model.get("db_type"):
        return validated_model["db_type"]

    for key in ("relational_model", "analytical_model"):
        sub = validated_model.get(key) or {}
        if isinstance(sub, dict) and sub.get("db_type"):
            return sub["db_type"]

    return os.getenv("DATABASE_TYPE", "MySQL")


# -------------------------------------------------------------------------
# Build Prompt
# -------------------------------------------------------------------------
def _build_prompt(model_dict: dict, db_type: str) -> str:
    """
    Build a plain f-string prompt — never use PromptTemplate (breaks on JSON {}).
    Each engine gets an explicit list of what IS and IS NOT supported.
    """

    engine_rules = {
        "BigQuery": """
TARGET: Google BigQuery
WHAT TO GENERATE:
- CREATE TABLE IF NOT EXISTS `table_name` (…) OPTIONS(description="…");
- Column types: STRING, INT64, FLOAT64, NUMERIC, BOOL, DATE, DATETIME, TIMESTAMP, BYTES, JSON
- PRIMARY KEY (col) NOT ENFORCED
- FOREIGN KEY (col) REFERENCES other_table(col) NOT ENFORCED
- Add clustering as comment: -- CLUSTER BY col1, col2
- Add partitioning as comment: -- PARTITION BY DATE(created_at)

WHAT NOT TO GENERATE:
- DO NOT generate CREATE INDEX
- DO NOT use ON DELETE CASCADE
- DO NOT use UNIQUE constraints
- DO NOT use CHECK constraints
- DO NOT use AUTO_INCREMENT, SERIAL, IDENTITY
- DO NOT use VARCHAR, INT, INTEGER, FLOAT, BOOLEAN, TEXT
- DO NOT duplicate tables
        """,

        "PostgreSQL": """
TARGET: PostgreSQL
WHAT TO GENERATE:
- CREATE TABLE IF NOT EXISTS table_name (...);
- Column types: TEXT, VARCHAR(n), INTEGER, BIGINT, SERIAL, BIGSERIAL, BOOLEAN, JSONB, UUID, TIMESTAMP, DATE
- PRIMARY KEY, FOREIGN KEY with ON DELETE CASCADE
- CREATE INDEX idx_name ON table(col);
- UNIQUE and CHECK constraints

WHAT NOT TO GENERATE:
- DO NOT use AUTO_INCREMENT
- DO NOT use NVARCHAR
- DO NOT duplicate tables
        """,

        "MSSQL": """
TARGET: Microsoft SQL Server
WHAT TO GENERATE:
- CREATE TABLE [table_name] (...);
- Column types: NVARCHAR(n), NVARCHAR(MAX), INT, BIGINT, BIT, DECIMAL(p,s), DATETIME2, UNIQUEIDENTIFIER
- IDENTITY(1,1) for auto-increment
- FOREIGN KEY with ON DELETE CASCADE
- CREATE INDEX idx_name ON col;
- UNIQUE and CHECK constraints

WHAT NOT TO GENERATE:
- DO NOT use AUTO_INCREMENT
- DO NOT use SERIAL
- DO NOT duplicate tables
        """,

        "Snowflake": """
TARGET: Snowflake
WHAT TO GENERATE:
- CREATE TABLE IF NOT EXISTS table_name (...);
- Column types: VARCHAR, NUMBER, FLOAT, BOOLEAN, DATE, TIMESTAMP_NTZ, VARIANT, ARRAY, OBJECT
- Use AUTOINCREMENT or IDENTITY(1,1) for surrogate primary keys
- PRIMARY KEY and FOREIGN KEY (not enforced)
- Add clustering: -- CLUSTER BY (col)

WHAT NOT TO GENERATE:
- DO NOT generate CREATE INDEX
- DO NOT use ON DELETE CASCADE
- DO NOT duplicate tables
        """,

        "SQLite": """
TARGET: SQLite
WHAT TO GENERATE:
- CREATE TABLE IF NOT EXISTS table_name (...);
- Column types: TEXT, INTEGER, REAL, BLOB, NUMERIC
- INTEGER PRIMARY KEY for auto-increment
- FOREIGN KEY constraints
- CREATE INDEX IF NOT EXISTS idx_name ON table(col);

WHAT NOT TO GENERATE:
- DO NOT use AUTO_INCREMENT
- DO NOT use SERIAL
- DO NOT use database prefixes
- DO NOT duplicate tables
        """,

        "MySQL": """
TARGET: MySQL
WHAT TO GENERATE:
- CREATE TABLE IF NOT EXISTS `table_name` (...) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
- Column types: VARCHAR(n), TEXT, INT, BIGINT, TINYINT(1), DECIMAL(p,s), DATETIME, TIMESTAMP, JSON
- AUTO_INCREMENT for PK
- FOREIGN KEY with ON DELETE CASCADE
- CREATE INDEX idx_name ON table(col);
- UNIQUE and CHECK constraints

WHAT NOT TO GENERATE:
- DO NOT use SERIAL or IDENTITY
- DO NOT duplicate tables
        """,
    }

    rules = engine_rules.get(
        db_type,
        f"""
TARGET: {db_type}
Generate SQL DDL using only valid syntax for this database.
Do not duplicate any table.
"""
    )

    return f"""
You are a senior database engineer expert in {db_type}.
Convert the data model JSON below into production-ready SQL DDL for ALL tables.

{rules}

OUTPUT RULES:
- Raw SQL only — no markdown fences, no JSON, no explanation
- Generate CREATE TABLE statements for EVERY table
- Add separator before each table: -- ============================================================
- End every statement with a semicolon
- Each table must appear EXACTLY ONCE

Data Model:
{json.dumps(model_dict, indent=2)}
"""


# -------------------------------------------------------------------------
# Strip Markdown Fences
# -------------------------------------------------------------------------
def _strip_fences(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        parts = text.split("```")
        inner = parts[1] if len(parts) > 1 else text
        if inner.lower().startswith("sql"):
            inner = inner[3:]
        return inner.strip()

    return text


# -------------------------------------------------------------------------
# Deduplicate CREATE TABLE blocks
# -------------------------------------------------------------------------
def _deduplicate_tables(sql: str) -> str:
    """Remove duplicate CREATE TABLE blocks — keep first occurrence only."""
    seen, result = set(), []

    parts = re.split(r'(?=CREATE\s+TABLE)', sql, flags=re.IGNORECASE | re.DOTALL)
    logger.info("Dedup: split into %d parts", len(parts))

    for part in parts:
        if not part.strip():
            continue

        m = re.search(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(\w+)[`"\]]?',
            part,
            re.IGNORECASE,
        )

        if m:
            name = m.group(1).lower()
            if name in seen:
                logger.info("Deduplicating table: %s", name)
                continue
            seen.add(name)

        result.append(part)

    logger.info("Dedup: kept %d unique tables", len(seen))
    return "".join(result)


# -------------------------------------------------------------------------
# SQL Generator Agent
# -------------------------------------------------------------------------
class SQLGeneratorAgent:
    def __init__(self):
        self.llm = _get_llm()

    def generate_sql(self, validated_model: dict) -> dict:
        db_type = _resolve_db_type(validated_model)
        logger.info("Generating SQL — db_type: %s", db_type)

        if not self.llm:
            msg = f"-- LLM not configured (target: {db_type})"
            return {
                "relational_sql": msg,
                "analytical_sql": msg,
                "combined_sql": msg,
                "db_type": db_type,
            }

        rel_model = validated_model.get("relational_model")
        anal_model = validated_model.get("analytical_model")

        relational_sql = ""
        analytical_sql = ""

        if rel_model:
            m = dict(rel_model)
            m["db_type"] = db_type
            relational_sql = self._generate_section(m, db_type)

        if anal_model:
            m = dict(anal_model)
            m["db_type"] = db_type
            analytical_sql = self._generate_section(m, db_type)

        if not rel_model and not anal_model:
            relational_sql = self._generate_section(validated_model, db_type)

        relational_sql = _deduplicate_tables(relational_sql) if relational_sql else ""
        analytical_sql = _deduplicate_tables(analytical_sql) if analytical_sql else ""

        combined = "\n\n".join(filter(None, [relational_sql, analytical_sql]))

        return {
            "relational_sql": relational_sql,
            "analytical_sql": analytical_sql,
            "combined_sql": combined,
            "db_type": db_type,
        }

    def _generate_section(self, model_dict: dict, db_type: str) -> str:
        prompt = _build_prompt(model_dict, db_type)

        try:
            resp = self.llm.invoke(prompt)
            logger.info("Raw LLM response length: %d chars", len(resp.content))

            sql = _strip_fences(resp.content)
            logger.info("SQL generated (%d chars) for %s", len(sql), db_type)

            return sql

        except Exception as e:
            logger.error("SQL generation error: %s", e)
            return f"-- SQL generation failed: {e}"


# -------------------------------------------------------------------------
# Convenience Wrapper
# -------------------------------------------------------------------------
def generate_sql_from_model(validated_model: dict) -> dict:
    return SQLGeneratorAgent().generate_sql(validated_model)