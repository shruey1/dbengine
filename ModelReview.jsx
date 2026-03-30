import { useState } from 'react';

import { Btn, Badge, ErrorBanner, Spinner } from './ui/Primitives';
import { ModelViewer } from './ModelViewer';
import { ValidationPanel } from './ValidationPanel';
import { generateERDFromModel } from '../api/client';

var C = {
  surface: '#13161e',
  border: '#232840',
  card: '#181c27',
  accent: '#4f8ef7',
  green: '#34d399',
  amber: '#fbbf24',
  purple: '#a78bfa',
  red: '#f87171',
  redSoft: 'rgba(248,113,113,0.12)',
  text: '#e2e8f0',
  textMuted: '#64748b',
  textDim: '#94a3b8',
};

function innerTabStyle(active, color) {
  var c = color || C.accent;
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

function SuggestionChips({ suggestions, onApply }) {
  if (!suggestions || !suggestions.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
      {suggestions.map(function (s, i) {
        return (
          <button
            key={i}
            onClick={function () {
              onApply(s);
            }}
            style={{
              padding: '6px 14px',
              borderRadius: 20,
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              border: '1px solid ' + C.amber + '55',
              background: C.amber + '12',
              color: C.amber,
              transition: 'all 0.15s',
              textAlign: 'left',
            }}
          >
            ⚡ {s}
          </button>
        );
      })}
    </div>
  );
}

// ── Inline ERD panel ─────────────────────────────────────────────────────────
function ERDPanel({ dataModel }) {
  var [erdData, setErdData] = useState(null);
  var [erdLoading, setErdLoading] = useState(false);
  var [erdError, setErdError] = useState('');
  var [zoom, setZoom] = useState(1);
  var [generated, setGenerated] = useState(false);

  function generate() {
    setErdLoading(true);
    setErdError('');
    setGenerated(false);
    generateERDFromModel(dataModel)
      .then(function (res) {
        setErdData(res);
        setGenerated(true);
        if (res.error) setErdError(res.error);
      })
      .catch(function (e) {
        setErdError(e.message);
      })
      .finally(function () {
        setErdLoading(false);
      });
  }

  function downloadPNG() {
    if (!erdData || !erdData.image_base64) return;
    var link = document.createElement('a');
    link.href = 'data:image/png;base64,' + erdData.image_base64;
    link.download = 'erd_preview.png';
    link.click();
  }

  // Not yet generated
  if (!generated && !erdLoading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 24px',
          gap: 16,
          background: '#090b10',
          border: '1px solid ' + C.border,
          borderRadius: 12,
        }}
      >
        <div style={{ fontSize: 40 }}>⬡</div>
        <p style={{ fontWeight: 700, fontSize: 16 }}>Preview ER Diagram</p>
        <p
          style={{
            color: C.textMuted,
            fontSize: 13,
            textAlign: 'center',
            maxWidth: 400,
          }}
        >
          Generate an ERD directly from your data model JSON — no SQL step
          required. Download it, review it, then proceed to validate and
          generate SQL.
        </p>
        <Btn
          onClick={generate}
          style={{
            background: 'linear-gradient(135deg, #4f8ef7, #a78bfa)',
            color: '#fff',
            border: 'none',
          }}
        >
          Generate ERD Preview
        </Btn>
      </div>
    );
  }

  if (erdLoading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '64px 24px',
          gap: 16,
          background: '#090b10',
          border: '1px solid ' + C.border,
          borderRadius: 12,
        }}
      >
        <Spinner size={32} />
        <p style={{ color: C.textMuted, fontSize: 13 }}>
          Generating ERD from model…
        </p>
      </div>
    );
  }

  if (erdError) {
    return (
      <div
        style={{
          background: C.redSoft,
          border: '1px solid ' + C.red + '44',
          borderRadius: 12,
          padding: 20,
        }}
      >
        <p style={{ fontWeight: 700, color: C.red, marginBottom: 8 }}>
          ⚠ ERD Generation Failed
        </p>
        <p style={{ color: C.textDim, fontSize: 13, marginBottom: 16 }}>
          {erdError}
        </p>

        {erdError.includes('Graphviz') && (
          <div
            style={{
              background: '#0d0f14',
              borderRadius: 8,
              padding: 12,
              fontSize: 12,
              fontFamily: 'monospace',
              color: C.textDim,
              marginBottom: 16,
            }}
          >
            <p style={{ color: C.amber, marginBottom: 6 }}>Install Graphviz:</p>
            <p style={{ marginBottom: 4 }}>
              Windows:{' '}
              <span style={{ color: C.green }}>winget install graphviz</span>
            </p>
            <p>Then restart uvicorn.</p>
          </div>
        )}
        <Btn onClick={generate}>↺ Try Again</Btn>
      </div>
    );
  }

  var hasImage = erdData && erdData.image_base64;
  return (
    <div>
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 12,
          flexWrap: 'wrap',
        }}
      >
        {erdData && erdData.table_count > 0 && (
          <Badge color={C.accent}>{erdData.table_count} tables</Badge>
        )}
        {erdData && erdData.relationship_count > 0 && (
          <Badge color={C.purple}>
            {erdData.relationship_count} relationships
          </Badge>
        )}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginLeft: 8,
          }}
        >
          <button
            onClick={function () {
              setZoom(function (z) {
                return Math.max(0.3, z - 0.15);
              });
            }}
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              border: '1px solid ' + C.border,
              background: C.card,
              color: C.text,
              cursor: 'pointer',
              fontSize: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            −
          </button>
          <span
            style={{
              color: C.textMuted,
              fontSize: 12,
              minWidth: 40,
              textAlign: 'center',
            }}
          >
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={function () {
              setZoom(function (z) {
                return Math.min(3, z + 0.15);
              });
            }}
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              border: '1px solid ' + C.border,
              background: C.card,
              color: C.text,
              cursor: 'pointer',
              fontSize: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            +
          </button>
          <button
            onClick={function () {
              setZoom(1);
            }}
            style={{
              padding: '3px 10px',
              borderRadius: 6,
              border: '1px solid ' + C.border,
              background: C.card,
              color: C.textMuted,
              cursor: 'pointer',
              fontSize: 11,
            }}
          >
            Reset
          </button>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <Btn
            variant="ghost"
            onClick={generate}
            style={{ padding: '6px 14px', fontSize: 12 }}
          >
            ↺ Regenerate
          </Btn>

          {hasImage && (
            <Btn
              variant="ghost"
              onClick={downloadPNG}
              style={{ padding: '6px 14px', fontSize: 12 }}
            >
              ⬇ Download PNG
            </Btn>
          )}
        </div>
      </div>

      {/* Image */}
      {hasImage && (
        <div
          style={{
            background: '#090b10',
            border: '1px solid ' + C.border,
            borderRadius: 12,
            overflow: 'auto',
            maxHeight: 560,
            padding: 16,
            cursor: 'grab',
          }}
        >
          <div
            style={{
              display: 'inline-block',
              transform: 'scale(' + zoom + ')',
              transformOrigin: 'top left',
              transition: 'transform 0.15s',
            }}
          >
            <img
              src={'data:image/png;base64,' + erdData.image_base64}
              alt="ER Diagram Preview"
              style={{ display: 'block', maxWidth: 'none' }}
            />
          </div>
        </div>
      )}

      {/* Legend */}
      <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {[
          { color: C.amber, symbol: '🔑', label: 'Primary Key' },
          { color: C.purple, symbol: '🔗', label: 'Foreign Key' },
          { color: C.green, symbol: '*', label: 'NOT NULL' },
          { color: C.green, symbol: 'U', label: 'UNIQUE' },
        ].map(function (item) {
          return (
            <div
              key={item.label}
              style={{ display: 'flex', alignItems: 'center', gap: 5 }}
            >
              <span style={{ color: item.color, fontSize: 13 }}>
                {item.symbol}
              </span>
              <span style={{ color: C.textMuted, fontSize: 11 }}>
                {item.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function ModelReview({
  dataModel,
  operation,
  validationMode,
  validation,
  loading,
  error,
  onAutoValidate,
  onApprove,
  onFeedback,
}) {
  var hasRelational = !!(dataModel && dataModel.relational_model);
  var hasAnalytical = !!(dataModel && dataModel.analytical_model);
  var modelViewerKey = hasRelational ? 'relational' : 'analytical';
  // tabs: 'model' | 'json' | 'erd'
  var [activeTab, setActiveTab] = useState('model');
  var [feedbackOpen, setFeedbackOpen] = useState(false);
  var [feedbackText, setFeedbackText] = useState('');
  var autoFailed = validationMode === 'auto' && validation && !validation.is_valid;

  function getScopedJson() {
    if (!dataModel) return {};
    if (hasRelational && hasAnalytical) return dataModel;
    if (hasRelational) return dataModel.relational_model;
    if (hasAnalytical) return dataModel.analytical_model;
    return dataModel;
    // falls back to entire object
  }

  function handleFeedbackSubmit() {
    if (!feedbackText.trim()) return;
    onFeedback(feedbackText);
    setFeedbackText('');
    setFeedbackOpen(false);
  }

  function handleChipClick(suggestion) {
    setFeedbackText(suggestion);
    setFeedbackOpen(true);
  }

  function handleFixAll() {
    var parts = [];
    if (validation.errors && validation.errors.length)
      parts.push('Fix these errors: ' + validation.errors.join('; '));
    if (validation.suggestions && validation.suggestions.length)
      parts.push('Also apply: ' + validation.suggestions.join('; '));
    setFeedbackText(parts.join('\n'));
    setFeedbackOpen(true);
  }

  var modelLabel =
    hasRelational && hasAnalytical
      ? 'Model'
      : hasRelational
      ? 'Relational Model'
      : 'Analytical Model';

  var modelColor =
    hasRelational && !hasAnalytical
      ? C.green
      : hasAnalytical && !hasRelational
      ? C.purple
      : C.accent;

  return (
    <div>
      {/* Page header */}
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
            <h2 style={{ fontSize: 22, fontWeight: 700 }}>Data Model</h2>
            <Badge color={operation === 'CREATE' ? C.green : C.amber}>
              {operation}
            </Badge>
            <Badge color={modelColor}>
              {hasRelational && !hasAnalytical
                ? 'Relational'
                : hasAnalytical && !hasRelational
                ? 'Analytical'
                : 'Both'}
            </Badge>

            {dataModel && dataModel.db_type && (
              <Badge color={C.textMuted}>{dataModel.db_type}</Badge>
            )}

            <Badge color={validationMode === 'auto' ? C.purple : C.accent}>
              {validationMode === 'auto' ? 'Auto Validate' : 'Manual Review'}
            </Badge>
          </div>
          <p style={{ color: C.textMuted, fontSize: 14 }}>
            Review your data model. Preview the ERD, check the raw JSON, then
            validate and generate SQL.
          </p>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {validationMode === 'auto' ? (
            (!validation || validation.is_valid) && (
              <Btn onClick={onAutoValidate} loading={loading}>
                Validate &amp; Generate SQL →
              </Btn>
            )
          ) : (
            <>
              <Btn
                variant="ghost"
                onClick={function () {
                  setFeedbackOpen(function (o) {
                    return !o;
                  });
                }}
                disabled={loading}
              >
                ✎ Suggest Changes
              </Btn>
              <Btn variant="success" onClick={onApprove} loading={loading}>
                ✓ Approve &amp; Generate SQL
              </Btn>
            </>
          )}
        </div>
      </div>

      {/* Validation result */}
      {validation && <ValidationPanel result={validation} />}

      {/* Auto-validation failed: fix panel */}
      {autoFailed && (
        <div
          style={{
            background: C.surface,
            border: '1px solid ' + C.amber + '44',
            borderRadius: 14,
            padding: 20,
            marginBottom: 20,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 12,
              marginBottom: 14,
            }}
          >
            <div>
              <p
                style={{
                  fontWeight: 700,
                  fontSize: 15,
                  color: C.text,
                  marginBottom: 4,
                }}
              >
                Fix &amp; Retry
              </p>
              <p style={{ color: C.textMuted, fontSize: 13 }}>
                Apply suggested fixes or describe changes, then re-validate.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <Btn
                variant="ghost"
                onClick={handleFixAll}
                disabled={loading}
                style={{ borderColor: C.amber + '55', color: C.amber }}
              >
                ⚡ Auto-fix All
              </Btn>
              <Btn onClick={onAutoValidate} loading={loading} style={{ background: C.accent }}>
                ↺ Re-validate
              </Btn>
            </div>
          </div>

          {validation.suggestions && validation.suggestions.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <p
                style={{
                  color: C.textMuted,
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: 8,
                }}
              >
                Quick fixes
              </p>
              <SuggestionChips
                suggestions={validation.suggestions}
                onApply={handleChipClick}
              />
            </div>
          )}

          {validation.errors && validation.errors.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <p
                style={{
                  color: C.textMuted,
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: 8,
                }}
              >
                Fix errors
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {validation.errors.map(function (e, i) {
                  return (
                    <button
                      key={i}
                      onClick={function () {
                        handleChipClick('Fix: ' + e);
                      }}
                      style={{
                        padding: '6px 14px',
                        borderRadius: 20,
                        fontSize: 12,
                        fontWeight: 500,
                        cursor: 'pointer',
                        border: '1px solid ' + C.red + '55',
                        background: C.redSoft,
                        color: C.red,
                        transition: 'all 0.15s',
                        textAlign: 'left',
                      }}
                    >
                      🔧 {e}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div>
            <p
              style={{
                color: C.textMuted,
                fontSize: 12,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 8,
              }}
            >
              Custom changes
            </p>
            <textarea
              value={feedbackText}
              onChange={function (e) {
                setFeedbackText(e.target.value);
              }}
              placeholder="e.g. Add foreign key constraints, fix data type mismatches..."
              style={{
                width: '100%',
                minHeight: 90,
                background: C.card,
                border: '1px solid ' + C.border,
                borderRadius: 8,
                padding: 12,
                fontSize: 14,
                color: C.text,
                resize: 'vertical',
                outline: 'none',
                marginBottom: 10,
              }}
            />
            <Btn
              onClick={handleFeedbackSubmit}
              loading={loading}
              disabled={!feedbackText.trim()}
            >
              Apply Changes &amp; Generate SQL
            </Btn>
          </div>
        </div>
      )}

      {/* Manual feedback panel */}
      {validationMode === 'manual' && feedbackOpen && (
        <div
          style={{
            background: C.surface,
            border: '1px solid ' + C.border,
            borderRadius: 12,
            padding: 20,
            marginBottom: 20,
          }}
        >
          <p style={{ fontWeight: 700, marginBottom: 10 }}>Suggest Changes</p>
          <textarea
            value={feedbackText}
            onChange={function (e) {
              setFeedbackText(e.target.value);
            }}
            placeholder="Describe what you'd like to change, add, or remove..."
            style={{
              width: '100%',
              minHeight: 100,
              background: C.card,
              border: '1px solid ' + C.border,
              borderRadius: 8,
              padding: 12,
              fontSize: 14,
              color: C.text,
              resize: 'vertical',
              outline: 'none',
              marginBottom: 12,
            }}
          />
          <div style={{ display: 'flex', gap: 10 }}>
            <Btn
              onClick={handleFeedbackSubmit}
              loading={loading}
              disabled={!feedbackText.trim()}
            >
              Apply &amp; Generate SQL
            </Btn>
            <Btn
              variant="ghost"
              onClick={function () {
                setFeedbackOpen(false);
              }}
            >
              Cancel
            </Btn>
          </div>
        </div>
      )}

      <ErrorBanner message={error} />

      {/* Tabs: Model | ERD Preview | Raw JSON */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <button
          style={innerTabStyle(activeTab === 'model', modelColor)}
          onClick={function () {
            setActiveTab('model');
          }}
        >
          {modelLabel}
        </button>
        <button
          style={innerTabStyle(activeTab === 'erd', C.purple)}
          onClick={function () {
            setActiveTab('erd');
          }}
        >
          ⬡ ERD Preview
        </button>
        <button
          style={innerTabStyle(activeTab === 'json', C.textMuted)}
          onClick={function () {
            setActiveTab('json');
          }}
        >
          Raw JSON
        </button>
      </div>

      {/* Tab content */}
      {activeTab === 'model' && (
        <ModelViewer dataModel={dataModel} activeTab={modelViewerKey} />
      )}

      {activeTab === 'erd' && <ERDPanel dataModel={dataModel} />}

      {activeTab === 'json' && (
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
          {JSON.stringify(getScopedJson(), null, 2)}
        </pre>
      )}
    </div>
  );
}
``