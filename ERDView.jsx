import { useState } from 'react';
import { Btn, Badge } from './ui/Primitives';
import { generateERDXML } from '../api/client';

const C = {
  surface: '#13161e',
  card: '#181c27',
  border: '#232840',
  accent: '#4f8ef7',
  green: '#34d399',
  purple: '#a78bfa',
  amber: '#fbbf24',
  red: '#f87171',
  redSoft: 'rgba(248,113,113,0.12)',
  text: '#e2e8f0',
  textMuted: '#64748b',
  textDim: '#94a3b8',
};

export function ERDView({
  erdData,
  sqlOutput,
  onBack,
  onReset,
  onRegenerate,
  loading,
}) {
  const [zoom, setZoom] = useState(1);
  const [xmlLoading, setXmlLoading] = useState(false);
  const [xmlError, setXmlError] = useState('');

  const hasImage = erdData && erdData.image_base64;
  const hasError = erdData && erdData.error;

  function downloadPNG() {
    if (!hasImage) return;
    const link = document.createElement('a');
    link.href = 'data:image/png;base64,' + erdData.image_base64;
    link.download = 'erd_diagram.png';
    link.click();
  }

  function downloadXML() {
    const sql = sqlOutput && sqlOutput.combined_sql;
    if (!sql) return;

    setXmlLoading(true);
    setXmlError('');

    generateERDXML(sql)
      .then(function (res) {
        if (res.error) {
          setXmlError(res.error);
          return;
        }
        const blob = new Blob([res.xml], { type: 'application/xml' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'erd_diagram.xml';
        link.click();
        URL.revokeObjectURL(url);
      })
      .catch(function (e) {
        setXmlError(e?.message || 'Failed to generate XML.');
      })
      .finally(function () {
        setXmlLoading(false);
      });
  }

  return (
    <div>
      {/* Header */}
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
            <h2 style={{ fontSize: 22, fontWeight: 700 }}>ER Diagram</h2>

            {hasImage && <Badge color={C.green}>Generated</Badge>}

            {erdData && erdData.table_count > 0 && (
              <Badge color={C.accent}>{erdData.table_count} tables</Badge>
            )}

            {erdData && erdData.relationship_count > 0 && (
              <Badge color={C.purple}>
                {erdData.relationship_count} relationships
              </Badge>
            )}
          </div>

          <p style={{ color: C.textMuted, fontSize: 14 }}>
            Entity relationship diagram generated from your SQL DDL scripts.
          </p>
        </div>

        <Btn variant="ghost" onClick={onBack}>
          ← Back to SQL
        </Btn>
      </div>

      {/* Error state */}
      {hasError && (
        <div
          style={{
            background: C.redSoft,
            border: '1px solid ' + C.red + '44',
            borderRadius: 12,
            padding: 20,
            marginBottom: 20,
          }}
        >
          <p style={{ fontWeight: 700, color: C.red, marginBottom: 8 }}>
            ⚠ ERD Generation Failed
          </p>

          <p style={{ color: C.textDim, fontSize: 13, marginBottom: 12 }}>
            {erdData.error}
          </p>

          {erdData.error && erdData.error.includes('Graphviz') && (
            <div
              style={{
                background: '#0d0f14',
                borderRadius: 8,
                padding: 12,
                fontSize: 12,
                fontFamily: 'monospace',
                color: C.textDim,
              }}
            >
              <p
                style={{
                  color: C.amber,
                  marginBottom: 6,
                  fontFamily: 'inherit',
                }}
              >
                Install Graphviz:
              </p>
              <p style={{ marginBottom: 4 }}>
                Windows: <span style={{ color: C.green }}>winget install graphviz</span>
              </p>
              <p style={{ marginBottom: 4 }}>
                Then: <span style={{ color: C.green }}>pip install graphviz</span>
              </p>
              <p>Restart uvicorn after installing.</p>
            </div>
          )}

          <div style={{ marginTop: 16 }}>
            <Btn
              onClick={() =>
                onRegenerate(sqlOutput && sqlOutput.combined_sql)
              }
              loading={loading}
            >
              ↺ Try Again
            </Btn>
          </div>
        </div>
      )}

      {/* XML error */}
      {xmlError && (
        <div
          style={{
            background: C.redSoft,
            border: '1px solid ' + C.red + '44',
            borderRadius: 8,
            padding: '10px 16px',
            marginBottom: 12,
            fontSize: 13,
            color: C.red,
          }}
        >
          ⚠ XML export failed: {xmlError}
        </div>
      )}

      {/* Diagram */}
      {hasImage && (
        <>
          {/* Zoom controls */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginBottom: 12,
            }}
          >
            {/* Zoom out */}
            <button
              onClick={() =>
                setZoom((z) => Math.max(0.3, z - 0.15))
              }
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                border: '1px solid ' + C.border,
                background: C.card,
                color: C.text,
                cursor: 'pointer',
                fontSize: 18,
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
                fontSize: 13,
                minWidth: 48,
                textAlign: 'center',
              }}
            >
              {Math.round(zoom * 100)}%
            </span>

            {/* Zoom in */}
            <button
              onClick={() =>
                setZoom((z) => Math.min(3, z + 0.15))
              }
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                border: '1px solid ' + C.border,
                background: C.card,
                color: C.text,
                cursor: 'pointer',
                fontSize: 18,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              +
            </button>

            {/* Reset zoom */}
            <button
              onClick={() => setZoom(1)}
              style={{
                padding: '4px 12px',
                borderRadius: 8,
                border: '1px solid ' + C.border,
                background: C.card,
                color: C.textMuted,
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              Reset
            </button>

            {/* Download buttons */}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
              <Btn
                variant="ghost"
                onClick={downloadPNG}
                style={{ padding: '7px 16px', fontSize: 13 }}
              >
                ⬇ Download PNG
              </Btn>

              <Btn
                variant="ghost"
                onClick={downloadXML}
                loading={xmlLoading}
                disabled={!sqlOutput || !sqlOutput.combined_sql}
                style={{
                  padding: '7px 16px',
                  fontSize: 13,
                  border: '1px solid ' + C.purple,
                  color: C.purple,
                }}
              >
                ⬇ Download XML
              </Btn>
            </div>
          </div>

          {/* XML hint */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 10,
              fontSize: 12,
              color: C.textMuted,
            }}
          >
            <span style={{ color: C.purple }}>ⓘ</span>
            XML is draw.io compatible — import via{' '}
            <span style={{ color: C.textDim }}>Extras → Edit Diagram</span>
            {' '}or{' '}
            <span style={{ color: C.textDim }}>File → Import from → XML</span>.
            Also works with Lucidchart and yEd.
          </div>

          {/* Image container */}
          <div
            style={{
              background: '#090b10',
              border: '1px solid ' + C.border,
              borderRadius: 14,
              overflow: 'auto',
              maxHeight: 640,
              padding: 20,
              cursor: 'grab',
            }}
          >
            <div
              style={{
                display: 'inline-block',
                transform: `scale(${zoom})`,
                transformOrigin: 'top left',
                transition: 'transform 0.15s',
              }}
            >
              <img
                src={'data:image/png;base64,' + erdData.image_base64}
                alt="ER Diagram"
                style={{ display: 'block', maxWidth: 'none' }}
              />
            </div>
          </div>

          {/* Legend */}
          <div
            style={{
              marginTop: 16,
              display: 'flex',
              gap: 20,
              flexWrap: 'wrap',
            }}
          >
            {[
              { color: C.amber, symbol: '🔑', label: 'Primary Key' },
              { color: C.purple, symbol: '🔗', label: 'Foreign Key' },
              { color: C.green, symbol: '*', label: 'NOT NULL' },
              { color: C.green, symbol: 'U', label: 'UNIQUE' },
            ].map((item) => (
              <div
                key={item.label}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <span style={{ color: item.color, fontSize: 14 }}>
                  {item.symbol}
                </span>
                <span style={{ color: C.textMuted, fontSize: 12 }}>
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Footer */}
      <div style={{ marginTop: 28, display: 'flex', gap: 12 }}>
        <Btn variant="ghost" onClick={onReset}>
          ✦ Start New Model
        </Btn>
      </div>
    </div>
  );
}