import { useState } from 'react';

const C = {
  card: '#181c27',
  border: '#232840',
  accent: '#4f8ef7',
  accentSoft: 'rgba(79,142,247,0.12)',
  green: '#34d399',
  amber: '#fbbf24',
  purple: '#a78bfa',
  purpleSoft: 'rgba(167,139,250,0.12)',
  text: '#e2e8f0',
  textMuted: '#64748b',
  textDim: '#94a3b8',
};

function Badge({ color, children }) {
  const col = color || C.accent;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 10px',
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        background: col + '22',
        color: col,
        border: '1px solid ' + col + '44',
      }}
    >
      {children}
    </span>
  );
}

function TableCard({ table, badge,addedColumns, removedColumns, modifiedColumns }) {
  const [open, setOpen] = useState(true);
  const cols = table.columns || [];
  const pk = Array.isArray(table.primary_key)
    ? table.primary_key
    : [table.primary_key].filter(Boolean);

  return (
    <div
      style={{
        background: C.card,
        border: '1px solid ' + C.border,
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 12,
      }}
    >
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          cursor: 'pointer',
          background: open ? C.accentSoft : 'transparent',
          borderBottom: open ? '1px solid ' + C.border : 'none',
          flexWrap: 'wrap',
        }}
      >
        <span>{open ? '▾' : '▸'}</span>
        <span
          style={{
            fontFamily: 'monospace',
            fontWeight: 700,
            color: C.text,
            fontSize: 14,
          }}
        >
          {table.name}
        
        </span>

        {badge && <Badge color={badge.color}>{badge.label}</Badge>}

        {addedTables?.has(table.name) && (
          <Badge color={C.green}>NEW</Badge>
        )}

        {modifiedTables?.has(table.name) && (
          <Badge color={C.amber}>MODIFIED</Badge>
        )}


        <span style={{ marginLeft: 'auto', color: C.textMuted, fontSize: 12 }}>
          {cols.length} cols
        </span>

        {table.description && (
          <span
            style={{
              color: C.textDim,
              fontSize: 12,
              maxWidth: 300,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            — {table.description}
          </span>
        )}
      </div>

      {open && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#ffffff08' }}>
                {['Column', 'Type', 'PK', 'Nullable', 'Notes'].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: '8px 14px',
                      textAlign: 'left',
                      color: C.textMuted,
                      fontWeight: 600,
                      fontSize: 11,
                      letterSpacing: '0.05em',
                      textTransform: 'uppercase',
                      borderBottom: '1px solid ' + C.border,
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cols.map((col, i) => {
                const isPk = pk.includes(col.name) || col.primary_key;
                const notes = [
                  col.unique && 'UNIQUE',
                  col.is_measure && 'measure',
                  col.is_foreign_key && 'FK',
                ]
                  .filter(Boolean)
                  .join(', ');
                return (
                  <tr
                    key={i}
                    style={{
                      borderBottom: '1px solid ' + C.border + '22',
                      background:
                        addedColumns?.has(table.name + '.' + col.name)
                          ? C.green + '14'
                          : modifiedColumns?.has(table.name + '.' + col.name)
                          ? C.amber + '14'
                          : isPk
                          ? C.accentSoft
                          : 'transparent',
                    }}
                  >
                    <td
                     style={{
                       padding: '8px 14px',
                       fontFamily: 'monospace',
                       color: isPk ? C.accent : C.text,
                       fontWeight: isPk ? 700 : 400,
                     }}
>
                     {col.name}
                     {addedColumns?.has(table.name + '.' + col.name) && (
<span style={{ fontSize: 10, color: C.green, fontWeight: 700, marginLeft: 6 }}>NEW</span>
                     )}
                     {modifiedColumns?.has(table.name + '.' + col.name) && (
<span style={{ fontSize: 10, color: C.amber, fontWeight: 700, marginLeft: 6 }}>CHANGED</span>
                     )}
</td>
                    <td
                      style={{
                        padding: '8px 14px',
                        fontFamily: 'monospace',
                        color: C.green,
                        fontSize: 12,
                      }}
                    >
                      {col.type}
                    </td>
                    <td style={{ padding: '8px 14px', textAlign: 'center' }}>
                      {isPk && <span style={{ color: C.accent }}>✦</span>}
                    </td>
                    <td
                      style={{
                        padding: '8px 14px',
                        textAlign: 'center',
                        color: col.nullable === false ? C.textMuted : C.amber,
                        fontSize: 12,
                      }}
                    >
                      {col.nullable === false ? 'NOT NULL' : 'NULL'}
                    </td>
                    <td style={{ padding: '8px 14px', color: C.textDim, fontSize: 12 }}>
                      {notes}
                      {col.description && ' ' + col.description}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RelationshipsList({ rels }) {
  if (!rels || !rels.length) return null;
  return (
    <div style={{ marginTop: 16 }}>
      <p
        style={{
          color: C.textMuted,
          fontSize: 11,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          fontWeight: 700,
          marginBottom: 8,
        }}
      >
        Relationships
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {rels.map((r, i) => (
          <div
            key={i}
            style={{
              background: C.purpleSoft,
              border: '1px solid ' + C.purple + '33',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              color: C.textDim,
              fontFamily: 'monospace',
            }}
          >
            <span style={{ color: C.purple }}>
              {r.from_table}.{r.from_column}
            </span>
            {' → '}
            <span style={{ color: C.accent }}>
              {r.to_table}.{r.to_column}
            </span>
            {r.cardinality && <span style={{ opacity: 0.6 }}> ({r.cardinality})</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ModelViewer({ dataModel, activeTab, changes }) {
  const addedTables = new Set(changes?.added_tables || []);
  const removedTables = new Set(changes?.removed_tables || []);
  const modifiedTables = new Set(changes?.modified_tables || []);
  const addedColumns = new Set(changes?.added_columns || []);
  const removedColumns = new Set(changes?.removed_columns || []);
  const modifiedColumns = new Set(changes?.modified_columns || []);

  if (!dataModel) return null;

  if (activeTab === 'json') {
    return (
      <pre
        style={{
          background: '#090b10',
          border: '1px solid ' + C.border,
          borderRadius: 12,
          padding: 20,
          fontSize: 12,
          color: '#c9d1d9',
          overflowX: 'auto',
          maxHeight: 600,
          overflowY: 'auto',
          fontFamily: '"Fira Code", monospace',
          lineHeight: 1.6,
        }}
      >
        {JSON.stringify(dataModel, null, 2)}
      </pre>
    );
  }

  if (activeTab === 'relational') {
    // Support both wrapped { relational_model: {…} } and flat { tables: […] }
    const m = dataModel.relational_model || (dataModel.tables ? dataModel : null);
    if (!m) return <p style={{ color: C.textMuted }}>No relational model found.</p>;

    return (
      <div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 16,
            flexWrap: 'wrap',
          }}
        >
          <Badge color={C.accent}>Relational</Badge>
          {m.normal_form && <Badge color={C.green}>{m.normal_form}</Badge>}
          {m.db_type && <Badge color={C.textMuted}>{m.db_type}</Badge>}
          <span style={{ color: C.textMuted, fontSize: 12 }}>
            {(m.tables || []).length} tables
          </span>
        </div>

        {(m.tables || []).map((t, i) => (
<TableCard key={i} table={t}
           addedTables={addedTables} modifiedTables={modifiedTables}
           addedColumns={addedColumns} modifiedColumns={modifiedColumns} />
       ))}
        <RelationshipsList rels={m.relationships} />
      </div>
    );
  }

  if (activeTab === 'analytical') {
    // Support both wrapped { analytical_model: {…} } and flat { fact_tables: […] }
    const a = dataModel.analytical_model || (dataModel.fact_tables ? dataModel : null);
    if (!a) return <p style={{ color: C.textMuted }}>No analytical model found.</p>;

    return (
      <div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 16,
            flexWrap: 'wrap',
          }}
        >
          <Badge color={C.purple}>Analytical</Badge>
          {a.schema_pattern && <Badge color={C.amber}>{a.schema_pattern} schema</Badge>}
          {a.db_type && <Badge color={C.textMuted}>{a.db_type}</Badge>}
          <span style={{ color: C.textMuted, fontSize: 12 }}>
            {(a.fact_tables || []).length} fact · {(a.dimension_tables || []).length} dim
          </span>
        </div>

        {(a.fact_tables || []).map((t, i) => (
<TableCard key={i} table={t} badge={{ color: C.purple, label: 'fact' }}
           addedTables={addedTables} modifiedTables={modifiedTables}
           addedColumns={addedColumns} modifiedColumns={modifiedColumns} />
       ))}
        {(a.dimension_tables || []).map((t, i) => (
          <TableCard key={i} table={t} badge={{ color: C.amber, label: 'dim' }}
                     addedTables={addedTables} modifiedTables={modifiedTables}
                     addedColumns={addedColumns} modifiedColumns={modifiedColumns} />
        ))}
        <RelationshipsList rels={a.relationships} />
      </div>
    );
  }

  return <p style={{ color: C.textMuted }}>No data for this tab.</p>;
}
