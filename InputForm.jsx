// components/InputForm.jsx
import { useState } from 'react';
import { Btn, ErrorBanner } from './ui/Primitives';

const C = {
  surface:   '#13161e',
  card:      '#181c27',
  border:    '#232840',
  accent:    '#4f8ef7',
  green:     '#34d399',
  purple:    '#a78bfa',
  amber:     '#fbbf24',
  text:      '#e2e8f0',
  textMuted: '#64748b',
  textDim:   '#94a3b8',
};

function tabStyle(active) {
  return {
    padding: '10px 24px',
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    border: 'none',
    background: active ? C.accent : 'transparent',
    color: active ? '#fff' : C.textMuted,
    transition: 'all 0.15s',
    letterSpacing: '0.02em',
  };
}

function modelTypeStyle(active, color) {
  const c = color || C.accent;
  return {
    flex: 1,
    padding: '14px 16px',
    borderRadius: 10,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    border: '2px solid ' + (active ? c : C.border),
    background: active ? c + '15' : C.card, // translucent when active
    color: active ? c : C.textMuted,
    transition: 'all 0.15s',
    textAlign: 'center',
  };
}

const DB_ENGINES = ['MySQL', 'PostgreSQL', 'MSSQL', 'BigQuery', 'Snowflake', 'SQLite'];

export function InputForm({ onSubmit, loading, error }) {
  const [mainTab, setMainTab]                 = useState('new');
  const [prompt, setPrompt]                   = useState('');
  const [uploadedSchema, setUploadedSchema]   = useState(null);
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [validationMode, setValidationMode]   = useState('auto');
  const [modelType, setModelType]             = useState('both'); // 'relational' | 'analytical' | 'both'
  const [dbEngine, setDbEngine]               = useState('');     // empty = auto-detect from prompt

  function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedFileName(file.name);
    const reader = new FileReader();
    reader.onload = function (ev) {
      try {
        setUploadedSchema(JSON.parse(ev.target.result));
      } catch (e) {
        setUploadedSchema({ raw: ev.target.result });
      }
    };
    reader.readAsText(file);
  }

  const canSubmit = prompt.trim().length > 0 && (mainTab === 'new' || uploadedSchema !== null);

  function handleSubmit() {
    if (!canSubmit) return;
    onSubmit({
      userQuery:      prompt,
      operation:      mainTab === 'new' ? 'CREATE' : 'MODIFY',
      existingModel:  mainTab === 'modify' ? uploadedSchema : null,
      validationMode: validationMode,
      modelType:      modelType,
      dbEngine:       dbEngine, // may be empty string — backend will detect from prompt
    });
  }

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      {/* Main tab switcher */}
      <div
        style={{
          display: 'flex',
          gap: 6,
          background: C.surface,
          padding: 6,
          borderRadius: 12,
          border: '1px solid ' + C.border,
          marginBottom: 28,
          width: 'fit-content',
        }}
      >
        <button style={tabStyle(mainTab === 'new')} onClick={() => setMainTab('new')}>
          ✦ New Schema
        </button>
        <button style={tabStyle(mainTab === 'modify')} onClick={() => setMainTab('modify')}>
          ⟳ Modify Existing
        </button>
      </div>

      <div
        style={{
          background: C.surface,
          border: '1px solid ' + C.border,
          borderRadius: 16,
          padding: 28,
        }}
      >
        <p style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>
          {mainTab === 'new' ? 'Describe your data model' : 'Describe your changes'}
        </p>
        <p style={{ color: C.textMuted, fontSize: 14, marginBottom: 20, lineHeight: 1.6 }}>
          {mainTab === 'new'
            ? 'Describe what you need. Mention the database engine (e.g. "PostgreSQL") if you want — otherwise MySQL is used.'
            : 'Describe what changes you want. Mention the DB engine if needed.'}
        </p>

        {/* Prompt */}
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            mainTab === 'new'
              ? 'e.g. I need a PostgreSQL database for an e-commerce platform with customers, products, orders and payments...'
              : 'e.g. Add a reviews table and an address column to customers...'
          }
          style={{
            width: '100%',
            minHeight: 130,
            background: C.card,
            border: '1px solid ' + C.border,
            borderRadius: 10,
            padding: 16,
            fontSize: 14,
            color: C.text,
            resize: 'vertical',
            outline: 'none',
            lineHeight: 1.6,
          }}
        />

        {/* ── Model type selector ── */}
        <div style={{ marginTop: 20 }}>
          <p style={{ color: C.textMuted, fontSize: 13, fontWeight: 600, marginBottom: 10 }}>
            Model type to generate
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              style={modelTypeStyle(modelType === 'both', C.accent)}
              onClick={() => setModelType('both')}
            >
              <div style={{ fontSize: 18, marginBottom: 4 }}>⬡</div>
              <div>Both</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>
                Relational + Analytical
              </div>
            </button>

            <button
              style={modelTypeStyle(modelType === 'relational', C.green)}
              onClick={() => setModelType('relational')}
            >
              <div style={{ fontSize: 18, marginBottom: 4 }}>⊞</div>
              <div>Relational</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>3NF normalised</div>
            </button>

            <button
              style={modelTypeStyle(modelType === 'analytical', C.purple)}
              onClick={() => setModelType('analytical')}
            >
              <div style={{ fontSize: 18, marginBottom: 4 }}>✦</div>
              <div>Analytical</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>Star schema</div>
            </button>
          </div>
        </div>

        {/* ── DB Engine override ── */}
        <div style={{ marginTop: 20 }}>
          <p style={{ color: C.textMuted, fontSize: 13, fontWeight: 600, marginBottom: 10 }}>
            Database engine
            <span style={{ color: C.textDim, fontWeight: 400, marginLeft: 8 }}>
              (auto-detected from your prompt, or pick one)
            </span>
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {/* Auto option */}
            <button
              onClick={() => setDbEngine('')}
              style={{
                padding: '7px 16px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                border: '1px solid ' + (dbEngine === '' ? C.amber : C.border),
                background: dbEngine === '' ? C.amber + '18' : C.card,
                color: dbEngine === '' ? C.amber : C.textMuted,
                transition: 'all 0.15s',
              }}
            >
              Auto-detect
            </button>

            {DB_ENGINES.map((eng) => {
              const active = dbEngine === eng;
              return (
                <button
                  key={eng}
                  onClick={() => setDbEngine(eng)}
                  style={{
                    padding: '7px 16px',
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: '1px solid ' + (active ? C.accent : C.border),
                    background: active ? C.accent + '18' : C.card,
                    color: active ? C.accent : C.textMuted,
                    transition: 'all 0.15s',
                  }}
                >
                  {eng}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Schema upload (modify only) ── */}
        {mainTab === 'modify' && (
          <div style={{ marginTop: 20 }}>
            <p style={{ color: C.textMuted, fontSize: 13, marginBottom: 8, fontWeight: 600 }}>
              Upload existing schema (JSON)
            </p>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 16px',
                background: C.card,
                border: '2px dashed ' + (uploadedSchema ? C.green : C.border),
                borderRadius: 10,
                cursor: 'pointer',
                transition: 'border-color 0.2s',
              }}
            >
              <span style={{ fontSize: 20 }}>{uploadedSchema ? '✓' : '⬆'}</span>
              <div>
                <p
                  style={{
                    fontWeight: 600,
                    fontSize: 13,
                    color: uploadedSchema ? C.green : C.textDim,
                  }}
                >
                  {uploadedFileName || 'Click to upload schema JSON'}
                </p>
                {uploadedSchema && (
                  <p style={{ fontSize: 11, color: C.textMuted, marginTop: 2 }}>
                    Schema loaded successfully
                  </p>
                )}
              </div>
              <input
                type="file"
                accept=".json"
                onChange={handleFile}
                style={{ display: 'none' }}
              />
            </label>
          </div>
        )}

        {/* ── Validation mode ── */}
        <div
          style={{
            marginTop: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <p style={{ color: C.textMuted, fontSize: 13, fontWeight: 600 }}>Validation mode:</p>
          <div
            style={{
              display: 'flex',
              gap: 6,
              background: C.card,
              padding: 4,
              borderRadius: 8,
              border: '1px solid ' + C.border,
            }}
          >
            {['auto', 'manual'].map((m) => (
              <button
                key={m}
                onClick={() => setValidationMode(m)}
                style={{
                  padding: '5px 14px',
                  borderRadius: 6,
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: 600,
                  background: validationMode === m ? C.accent : 'transparent',
                  color: validationMode === m ? '#fff' : C.textMuted,
                  transition: 'all 0.15s',
                  textTransform: 'capitalize',
                }}
              >
                {m}
              </button>
            ))}
          </div>
          <p style={{ fontSize: 12, color: C.textMuted }}>
            {validationMode === 'auto'
              ? 'LLM validates and auto-corrects'
              : 'You review and approve changes'}
          </p>
        </div>

        <ErrorBanner message={error} />

        <div style={{ marginTop: 24 }}>
          <Btn onClick={handleSubmit} loading={loading} disabled={!canSubmit}>
            Generate Data Model →
          </Btn>
        </div>
      </div>
    </div>
  );
}