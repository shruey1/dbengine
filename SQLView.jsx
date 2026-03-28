import { useState } from 'react';

import { Btn, Badge } from './ui/Primitives';
import { ValidationPanel } from './ValidationPanel';

const C = {
  border: '#232840',
  accent: '#4f8ef7',
  green: '#34d399',
  purple: '#a78bfa',
  amber: '#fbbf24',
  textMuted: '#64748b',
  text: '#e2e8f0',
};

const SQL_TABS = [
  { key: 'combined_sql', label: 'Combined', color: '#4f8ef7' },
  { key: 'relational_sql', label: 'Relational DDL', color: '#34d399' },
  { key: 'analytical_sql', label: 'Analytical DDL', color: '#a78bfa' },
];

function innerTabStyle(active, color) {
  const c = color || C.accent;
  return {
    padding: '7px 18px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    border: '1px solid ' + (active ? c : C.border),
    background: active ? c + '18' : 'transparent',
    color: active ? c : C.textMuted,
    transition: 'all 0.15s',
  };
}

function SQLBlock({ sql }) {
  const [copied, setCopied] = useState(false);

  if (!sql)
    return (
      <p style={{ color: C.textMuted, padding: 20 }}>
        No SQL generated for this section.
      </p>
    );

  function copy() {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(function () {
      setCopied(false);
    }, 2000);
  }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10 }}>
        <Btn variant="ghost" onClick={copy} style={{ padding: '6px 14px', fontSize: 12 }}>
          {copied ? '✓ Copied' : 'Copy'}
        </Btn>
      </div>
      <pre
        style={{
          background: '#090b10',
          border: '1px solid ' + C.border,
          borderRadius: 12,
          padding: 20,
          overflowX: 'auto',
          fontSize: 13,
          lineHeight: 1.7,
          color: '#c9d1d9',
          fontFamily: '"Fira Code", monospace',
          maxHeight: 520,
          overflowY: 'auto',
        }}
      >
        <code>{sql}</code>
      </pre>
    </div>
  );
}

export function SQLView({
  sqlOutput,
  validation,
  onBack,
  onReset,
  onGenerateERD,
  erdLoading,
}) {
  const [activeTab, setActiveTab] = useState('combined_sql');

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: 24,
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginBottom: 6,
              flexWrap: 'wrap',
            }}
          >
            <h2 style={{ fontSize: 22, fontWeight: 700 }}>SQL Scripts</h2>
            <Badge color={C.green}>Ready</Badge>
            {sqlOutput && sqlOutput.db_type && (
              <Badge color={C.textMuted}>{sqlOutput.db_type}</Badge>
            )}
          </div>
          <p style={{ color: C.textMuted, fontSize: 14 }}>
            Production-ready DDL scripts generated from your validated data model.
          </p>
        </div>

        <Btn variant="ghost" onClick={onBack}>
          ← Back to Model
        </Btn>
      </div>

      {/* Validation results (if present) */}
      {validation && <ValidationPanel result={validation} />}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {SQL_TABS.map(function (t) {
          return sqlOutput && sqlOutput[t.key] ? (
            <button
              key={t.key}
              style={innerTabStyle(activeTab === t.key, t.color)}
              onClick={function () {
                setActiveTab(t.key);
              }}
            >
              {t.label}
            </button>
          ) : null;
        })}
      </div>

      {/* SQL content */}
      <SQLBlock sql={sqlOutput && sqlOutput[activeTab]} />

      {/* Action bar */}
      <div
        style={{
          marginTop: 28,
          padding: '20px 24px',
          background: '#13161e',
          border: '1px solid ' + C.border,
          borderRadius: 14,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div>
          <p style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
            Generate ER Diagram
          </p>
          <p style={{ color: C.textMuted, fontSize: 13 }}>
            Visualise your schema as an interactive entity-relationship diagram.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <Btn variant="ghost" onClick={onReset}>
            ✦ Start New
          </Btn>

          <Btn
            onClick={function () {
              onGenerateERD(sqlOutput && sqlOutput.combined_sql);
            }}
            loading={erdLoading}
            disabled={!sqlOutput || !sqlOutput.combined_sql}
            style={{
              background: 'linear-gradient(135deg, #4f8ef7, #a78bfa)',
              color: '#fff',
              border: 'none',
            }}
          >
            ⬡ Generate ERD →
          </Btn>
        </div>
      </div>
    </div>
  );
}