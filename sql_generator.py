"""
Agent responsible for generating SQL DDL from a validated JSON data model.
"""

import os
import json
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import PromptTemplate

from backend.utils.prompts import SQL_GENERATION_PROMPT

load_dotenv()


def _get_llm() -> Optional[AzureChatOpenAI]:
    """Configure and return an AzureChatOpenAI instance if env vars are present; otherwise None."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    if not (api_key and endpoint and deployment):
        return None

    # NOTE: adjust api_version if your Azure OpenAI resource uses a different one
    return AzureChatOpenAI(
        api_key=api_key,
        api_version="2024-02-15-preview",
        azure_endpoint=endpoint,
        model=deployment,
        temperature=0,
    )


class SQLGeneratorAgent:
    def __init__(self) -> None:
        self.llm = _get_llm()
        self.db_type = os.getenv("DATABASE_TYPE", "MySQL")

    def generate_sql(self, validated_model: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate SQL DDL scripts from a validated JSON data model.

        Args:
            validated_model: dict containing "relational_model" and/or "analytical_model"

        Returns:
            {
                "relational_sql": "<SQL string or empty>",
                "analytical_sql": "<SQL string or empty>",
                "combined_sql": "<full SQL>",
                "db_type": "MySQL"
            }
        """
        if not self.llm:
            not_configured = "-- LLM not configured: set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT"
            return {
                "relational_sql": not_configured,
                "analytical_sql": not_configured,
                "combined_sql": not_configured,
                "db_type": self.db_type,
            }

        relational_sql = ""
        analytical_sql = ""

        rel_model = validated_model.get("relational_model")
        anal_model = validated_model.get("analytical_model")

        if rel_model:
            relational_sql = self._generate_section(rel_model)

        if anal_model:
            analytical_sql = self._generate_section(anal_model)

        # If a flat model was passed (not wrapped)
        if not rel_model and not anal_model:
            relational_sql = self._generate_section(validated_model)

        combined = "\n\n".join(s for s in [relational_sql, analytical_sql] if s)

        return {
            "relational_sql": relational_sql or "",
            "analytical_sql": analytical_sql or "",
            "combined_sql": combined or "",
            "db_type": self.db_type,
        }

    def _generate_section(self, model_dict: Dict[str, Any]) -> str:
        """Generate SQL DDL for a single model section."""
        prompt = PromptTemplate(
            input_variables=["model_json", "db_type"],
            template=SQL_GENERATION_PROMPT,
        )

        formatted = prompt.format(
            model_json=json.dumps(model_dict, indent=2),
            db_type=self.db_type,
        )

        try:
            resp = self.llm.invoke(formatted)
            raw = getattr(resp, "content", "") if resp is not None else ""
        except Exception as e:
            return f"-- Error generating SQL: {e}"

        sql = self._strip_markdown_fences((raw or "").strip())
        return sql.strip()

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """
        Remove common Markdown code fences from LLM output.
        Handles ```sql ...```, ``` ...```, and stray triple backticks.
        """
        if not text:
            return text

        # If starts with a fenced block, take the inner section
        if text.startswith("```"):
            parts = text.split("```")
            # parts typically: ["", "sql\nCREATE ...", ""]
            if len(parts) >= 2:
                candidate = parts[1]
                # Remove leading language tag like "sql\n" or "SQL\n"
                if candidate.lower().startswith("sql"):
                    # remove e.g., "sql" + optional newline or carriage return
                    candidate = candidate[3:].lstrip("\r\n")
                return candidate

        # If no classic fence, still try to remove any lingering backticks
        if text.endswith("```"):
            text = text[:-3].rstrip()

        return text


def generate_sql_from_model(validated_model: Dict[str, Any]) -> Dict[str, str]:
    """Convenience function: generate SQL DDL from a validated data model JSON."""
    return SQLGeneratorAgent().generate_sql(validated_model)