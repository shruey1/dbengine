"""
erd_generator.py

Parses DDL SQL and renders an Entity Relationship Diagram via Graphviz.
Returns the diagram as a base64-encoded PNG so the FastAPI endpoint can
serve it without writing temp files to disk.
"""

import re
import base64
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from graphviz import Digraph

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class Column:
    name: str
    data_type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_nullable: bool = True
    is_unique: bool = False
    default: Optional[str] = None


@dataclass
class ForeignKey:
    from_table: str
    from_col: str
    to_table: str
    to_col: str


@dataclass
class Table:
    name: str
    columns: List[Column] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)


# ── DDL Parser ────────────────────────────────────────────────────────────────
class DDLParser:
    TABLE_RE         = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["\[]?(\w+)["\]]?', re.IGNORECASE)
    COLUMN_RE        = re.compile(r'^\s*[`"\[]?(\w+)[`"\]]?\s+([\w]+(?:\s*\([^)]*\))?)(.*?)$', re.IGNORECASE)
    PK_INLINE_RE     = re.compile(r'\bPRIMARY\s+KEY\b', re.IGNORECASE)
    FK_CONSTRAINT_RE = re.compile(r'FOREIGN\s+KEY\s*\([`"\[]?(\w+)[`"\]]?\)\s*REFERENCES\s+[`"\[]?(\w+)[`"\]]?\s*\([`"\[]?(\w+)[`"\]]?\)', re.IGNORECASE)
    PK_CONSTRAINT_RE = re.compile(r'PRIMARY\s+KEY\s*\(([^)]+)\)', re.IGNORECASE)
    NOT_NULL_RE      = re.compile(r'\bNOT\s+NULL\b', re.IGNORECASE)
    UNIQUE_RE        = re.compile(r'\bUNIQUE\b', re.IGNORECASE)
    DEFAULT_RE       = re.compile(r"\bDEFAULT\s+('?[^,\s)]+'?)", re.IGNORECASE)

    def parse(self, sql_text: str) -> Tuple[Dict[str, Table], List[ForeignKey]]:
        tables: Dict[str, Table] = {}
        foreign_keys: List[ForeignKey] = []

        blocks = re.split(r'(?=CREATE\s+TABLE)', sql_text, flags=re.IGNORECASE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            m = self.TABLE_RE.match(block)
            if not m:
                continue

            table_name = m.group(1)
            table = Table(name=table_name)
            body = self._extract_body(block)
            if not body:
                continue

            for line in self._split_definitions(body):
                line = line.strip().rstrip(',').strip()
                if not line:
                    continue

                upper = line.upper().lstrip()

                # Table-level PK
                pk_m = self.PK_CONSTRAINT_RE.search(line)
                if upper.startswith('PRIMARY') and pk_m:
                    pks = [c.strip().strip('`"[]') for c in pk_m.group(1).split(',')]
                    table.primary_keys.extend(pks)
                    continue

                # Table-level FK
                fk_m = self.FK_CONSTRAINT_RE.search(line)
                if upper.startswith(('FOREIGN', 'CONSTRAINT')) and fk_m:
                    foreign_keys.append(ForeignKey(
                        from_table=table_name,
                        from_col=fk_m.group(1),
                        to_table=fk_m.group(2),
                        to_col=fk_m.group(3),
                    ))
                    continue

                # Skip other table constraints / indexes
                if re.match(r'^(UNIQUE|INDEX|KEY|CHECK|CONSTRAINT)\b', upper):
                    continue

                # Column definition
                col_m = self.COLUMN_RE.match(line)
                if col_m:
                    col_name = col_m.group(1)
                    col_type = col_m.group(2).strip()
                    rest     = col_m.group(3)

                    is_pk     = bool(self.PK_INLINE_RE.search(rest))
                    is_unique = bool(self.UNIQUE_RE.search(rest))
                    nullable  = not bool(self.NOT_NULL_RE.search(rest)) and not is_pk
                    default_m = self.DEFAULT_RE.search(rest)

                    if is_pk:
                        table.primary_keys.append(col_name)

                    table.columns.append(Column(
                        name=col_name,
                        data_type=col_type.upper(),
                        is_primary_key=is_pk,
                        is_nullable=nullable,
                        is_unique=is_unique,
                        default=default_m.group(1) if default_m else None,
                    ))

            tables[table_name] = table

        # Back-fill FK and PK flags on column objects
        fk_lookup = {(fk.from_table, fk.from_col): fk for fk in foreign_keys}
        for table in tables.values():
            for col in table.columns:
                if (table.name, col.name) in fk_lookup:
                    col.is_foreign_key = True
            for pk_name in table.primary_keys:
                for col in table.columns:
                    if col.name == pk_name:
                        col.is_primary_key = True

        return tables, foreign_keys

    def _extract_body(self, block: str) -> Optional[str]:
        depth, start = 0, None
        for i, ch in enumerate(block):
            if ch == '(':
                if depth == 0:
                    start = i + 1
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and start is not None:
                    return block[start:i]
        return None

    def _split_definitions(self, body: str) -> List[str]:
        parts: List[str] = []
        current: List[str] = []
        depth = 0
        for ch in body:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current))
        return parts


# ── ERD renderer ──────────────────────────────────────────────────────────────
def _html_table(table: Table) -> str:
    """Build an HTML-label Graphviz node for a table."""
    # Header
    rows = [
        (
            '<TR>'
            '<TD COLSPAN="3" BGCOLOR="#1e2d4a" ALIGN="CENTER">'
            '<FONT COLOR="#4f8ef7" FACE="Helvetica Bold" POINT-SIZE="13">'
            f'<B>{table.name}</B>'
            '</FONT>'
            '</TD>'
            '</TR>'
        )
    ]

    for col in table.columns:
        # Icon column
        if col.is_primary_key:
            icon = '<FONT COLOR="#fbbf24">🔑</FONT>'
        elif col.is_foreign_key:
            icon = '<FONT COLOR="#a78bfa">🔗</FONT>'
        else:
            icon = ''

        # Nullable marker
        nullable_marker = '' if col.is_nullable else '<FONT COLOR="#f87171"> *</FONT>'
        # Unique marker
        unique_marker = '<FONT COLOR="#34d399"> U</FONT>' if col.is_unique else ''

        row_bg = '#162032' if col.is_primary_key else '#0d1520'
        name_color = '#4f8ef7' if col.is_primary_key else '#e2e8f0'

        rows.append(
            '<TR>'
            f'<TD BGCOLOR="{row_bg}" ALIGN="LEFT" WIDTH="20">{icon}</TD>'
            f'<TD BGCOLOR="{row_bg}" ALIGN="LEFT">'
            f'<FONT COLOR="{name_color}" FACE="Helvetica" POINT-SIZE="11">'
            f'{"<B>" if col.is_primary_key else ""}{col.name}{"</B>" if col.is_primary_key else ""}'
            f'{nullable_marker}{unique_marker}'
            '</FONT>'
            '</TD>'
            f'<TD BGCOLOR="{row_bg}" ALIGN="RIGHT">'
            f'<FONT COLOR="#34d399" FACE="Courier" POINT-SIZE="10">{col.data_type}</FONT>'
            '</TD>'
            '</TR>'
        )

    inner = '\n'.join(rows)
    # Graphviz HTML-like labels must be wrapped with label=<<TABLE ...>> in the node call.
    return f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6">\n{inner}\n</TABLE>>'


def generate_erd_base64(sql_text: str, title: str = "Entity Relationship Diagram") -> dict:
    """
    Parse SQL DDL and render an ERD as a base64 PNG.
    Returns:
        {
            "image_base64": "<base64 PNG string>",
            "format": "png",
            "table_count": N,
            "relationship_count": N,
            "error": None | "<error message>"
        }
    """
    parser = DDLParser()
    try:
        tables, foreign_keys = parser.parse(sql_text)
    except Exception as e:
        logger.error("DDL parse error: %s", e)
        return {"image_base64": None, "format": "png", "table_count": 0, "relationship_count": 0, "error": str(e)}

    if not tables:
        return {
            "image_base64": None,
            "format": "png",
            "table_count": 0,
            "relationship_count": 0,
            "error": "No tables found in SQL. Make sure the input contains CREATE TABLE statements.",
        }

    # Build Graphviz diagram
    dot = Digraph(
        name="ERD",
        comment=title,
        format="png",
    )
    dot.attr(
        rankdir="LR",
        bgcolor="#0d0f14",
        fontname="Helvetica",
        pad="0.5",
        nodesep="0.8",
        ranksep="1.2",
        label=title,
        labelloc="t",
        fontcolor="#64748b",
        fontsize="14",
    )
    dot.attr(
        "node",
        shape="none",
        margin="0",
        fontname="Helvetica",
    )
    dot.attr(
        "edge",
        color="#4f8ef7",
        fontcolor="#94a3b8",
        fontsize="10",
        fontname="Helvetica",
        arrowsize="0.8",
    )

    # Add table nodes
    for table in tables.values():
        dot.node(table.name, label=_html_table(table))

    # Add FK edges with crow's foot notation labels
    for fk in foreign_keys:
        if fk.from_table in tables and fk.to_table in tables:
            dot.edge(
                fk.from_table,
                fk.to_table,
                label=f" {fk.from_col} → {fk.to_col} ",
                arrowhead="crow",
                arrowtail="tee",
                dir="both",
                color="#a78bfa",
                style="solid",
            )

    # Render to PNG bytes
    try:
        png_bytes = dot.pipe(format="png")
        image_b64 = base64.b64encode(png_bytes).decode("utf-8")
        return {
            "image_base64": image_b64,
            "format": "png",
            "table_count": len(tables),
            "relationship_count": len(foreign_keys),
            "error": None,
        }
    except Exception as e:
        logger.error("Graphviz render error: %s", e)
        return {
            "image_base64": None,
            "format": "png",
            "table_count": len(tables),
            "relationship_count": len(foreign_keys),
            "error": f"Graphviz render failed: {str(e)}. Make sure Graphviz is installed: https://graphviz.org/download/",
        }


def generate_erd_xml(sql_text: str, title: str = "Entity Relationship Diagram") -> dict:
    """
    Parse SQL DDL and render an ERD as SVG XML.
    Returns:
        {
            "xml": "<SVG XML string>",
            "format": "svg",
            "table_count": N,
            "relationship_count": N,
            "error": None | "<error message>"
        }
    """
    parser = DDLParser()
    try:
        tables, foreign_keys = parser.parse(sql_text)
    except Exception as e:
        logger.error("DDL parse error: %s", e)
        return {"xml": None, "format": "svg", "table_count": 0, "relationship_count": 0, "error": str(e)}

    if not tables:
        return {
            "xml": None,
            "format": "svg",
            "table_count": 0,
            "relationship_count": 0,
            "error": "No tables found in SQL. Make sure the input contains CREATE TABLE statements.",
        }

    # Build Graphviz diagram
    dot = Digraph(
        name="ERD",
        comment=title,
        format="svg",
    )
    dot.attr(
        rankdir="LR",
        bgcolor="#0d0f14",
        fontname="Helvetica",
        pad="0.5",
        nodesep="0.8",
        ranksep="1.2",
        label=title,
        labelloc="t",
        fontcolor="#64748b",
        fontsize="14",
    )
    dot.attr(
        "node",
        shape="none",
        margin="0",
        fontname="Helvetica",
    )
    dot.attr(
        "edge",
        color="#4f8ef7",
        fontcolor="#94a3b8",
        fontsize="10",
        fontname="Helvetica",
        arrowsize="0.8",
    )

    # Add table nodes
    for table in tables.values():
        dot.node(table.name, label=_html_table(table))

    # Add FK edges with crow's foot notation labels
    for fk in foreign_keys:
        if fk.from_table in tables and fk.to_table in tables:
            dot.edge(
                fk.from_table,
                fk.to_table,
                label=f" {fk.from_col} → {fk.to_col} ",
                arrowhead="crow",
                arrowtail="tee",
                dir="both",
                color="#a78bfa",
                style="solid",
            )

    # Render to SVG string
    try:
        svg_bytes = dot.pipe(format="svg")
        svg_xml = svg_bytes.decode("utf-8")
        return {
            "xml": svg_xml,
            "format": "svg",
            "table_count": len(tables),
            "relationship_count": len(foreign_keys),
            "error": None,
        }
    except Exception as e:
        logger.error("Graphviz render error: %s", e)
        return {
            "xml": None,
            "format": "svg",
            "table_count": len(tables),
            "relationship_count": len(foreign_keys),
            "error": f"Graphviz render failed: {str(e)}. Make sure Graphviz is installed: https://graphviz.org/download/",
        }


# ── ERD directly from JSON model (no SQL required) ───────────────────────────
def _tables_from_model_json(data_model: dict) -> Tuple[Dict[str, Table], List[ForeignKey]]:
    """
    Convert a JSON data model (relational or analytical) into
    Table + ForeignKey objects that the existing Graphviz renderer understands.
    Handles both wrapped { relational_model: {...} } and flat { tables: [...] }.
    """
    tables: Dict[str, Table] = {}
    foreign_keys: List[ForeignKey] = []

    def _col_type(col: dict) -> str:
        return str(col.get("type") or col.get("data_type") or "TEXT").upper()

    def _process_table(t: dict, label: str = ""):
        name = t.get("name", "unknown")
        tbl = Table(name=name)
        pk_list = t.get("primary_key", [])
        if isinstance(pk_list, str):
            pk_list = [pk_list]
        tbl.primary_keys = list(pk_list)

        for col in t.get("columns", []):
            cname = col.get("name", "col")
            ctype = _col_type(col)
            is_pk = col.get("primary_key", False) or cname in tbl.primary_keys
            is_fk = col.get("is_foreign_key", False)
            nullable = col.get("nullable", True)
            unique = col.get("unique", False)

            if is_pk and cname not in tbl.primary_keys:
                tbl.primary_keys.append(cname)

            tbl.columns.append(Column(
                name=cname,
                data_type=ctype,
                is_primary_key=is_pk,
                is_foreign_key=is_fk,
                is_nullable=nullable,
                is_unique=unique,
            ))
        tables[name] = tbl

    def _process_relationships(rels: list):
        for r in (rels or []):
            fk = ForeignKey(
                from_table=r.get("from_table", ""),
                from_col=r.get("from_column", r.get("from_col", "")),
                to_table=r.get("to_table", ""),
                to_col=r.get("to_column", r.get("to_col", "")),
            )
            if fk.from_table and fk.to_table:
                foreign_keys.append(fk)
                # Back-fill FK flag on the column
                if fk.from_table in tables:
                    for col in tables[fk.from_table].columns:
                        if col.name == fk.from_col:
                            col.is_foreign_key = True

    # ── Relational model ──────────────────────────────────────────────────────
    rel = data_model.get("relational_model") or (data_model if data_model.get("tables") else None)
    if rel:
        for t in rel.get("tables", []):
            _process_table(t)
        _process_relationships(rel.get("relationships", []))

    # ── Analytical model ──────────────────────────────────────────────────────
    anal = data_model.get("analytical_model") or (data_model if data_model.get("fact_tables") else None)
    if anal:
        for t in anal.get("fact_tables", []):
            _process_table(t, "fact")
        for t in anal.get("dimension_tables", []):
            _process_table(t, "dim")
        _process_relationships(anal.get("relationships", []))

    return tables, foreign_keys


def generate_erd_from_model(data_model: dict, title: str = "Entity Relationship Diagram") -> dict:
    """
    Generate an ERD PNG directly from a JSON data model —
    no SQL generation step required.
    Returns the same shape as generate_erd_base64().
    """
    try:
        tables, foreign_keys = _tables_from_model_json(data_model)
    except Exception as e:
        logger.error("Model-to-ERD parse error: %s", e)
        return {"image_base64": None, "format": "png", "table_count": 0, "relationship_count": 0, "error": str(e)}

    if not tables:
        return {
            "image_base64": None, "format": "png",
            "table_count": 0, "relationship_count": 0,
            "error": "No tables found in data model.",
        }

    dot = Digraph(name="ERD", comment=title, format="png")
    dot.attr(
        rankdir="LR", bgcolor="#0d0f14", fontname="Helvetica",
        pad="0.5", nodesep="0.8", ranksep="1.2",
        label=title, labelloc="t", fontcolor="#64748b", fontsize="14",
    )
    dot.attr("node", shape="none", margin="0", fontname="Helvetica")
    dot.attr("edge", color="#4f8ef7", fontcolor="#94a3b8", fontsize="10",
             fontname="Helvetica", arrowsize="0.8")

    for table in tables.values():
        dot.node(table.name, label=_html_table(table))

    for fk in foreign_keys:
        if fk.from_table in tables and fk.to_table in tables:
            dot.edge(
                fk.from_table, fk.to_table,
                label=f" {fk.from_col} → {fk.to_col} ",
                arrowhead="crow", arrowtail="tee", dir="both",
                color="#a78bfa", style="solid",
            )
    try:
        png_bytes = dot.pipe(format="png")
        return {
            "image_base64": base64.b64encode(png_bytes).decode("utf-8"),
            "format": "png",
            "table_count": len(tables),
            "relationship_count": len(foreign_keys),
            "error": None,
        }
    except Exception as e:
        logger.error("Graphviz render error: %s", e)
        return {
            "image_base64": None, "format": "png",
            "table_count": len(tables),
            "relationship_count": len(foreign_keys),
            "error": f"Graphviz render failed: {str(e)}. Make sure Graphviz is installed: https://graphviz.org/download/",
        }