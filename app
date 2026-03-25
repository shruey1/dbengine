import { useState } from 'react';

import { Header } from './components/ui/Header';
import { InputForm } from './components/InputForm';
import { ModelReview } from './components/ModelReview';
import { SQLView } from './components/SQLView';
import { ERDView } from './components/ERDView';

import {
  generateModel,
  validateAndGenerateSQL,
  approveAndGenerateSQL,
  applyFeedbackAndGenerateSQL,
  generateERD,
} from './api/client';

var BG = '#0d0f14';

export default function App() {
  var [step, setStep] = useState(0);
  var [operation, setOperation] = useState('CREATE');
  var [validationMode, setValidationMode] = useState('auto');
  var [dataModel, setDataModel] = useState(null);
  var [validation, setValidation] = useState(null);
  var [sqlOutput, setSqlOutput] = useState(null);
  var [erdData, setErdData] = useState(null);
  var [dbEngine, setDbEngine] = useState('MySQL');
  var [loading, setLoading] = useState(false);
  var [erdLoading, setErdLoading] = useState(false);
  var [error, setError] = useState('');

  function wrap(fn) {
    setLoading(true);
    setError('');
    fn()
      .catch(function (e) {
        setError(e.message);
      })
      .finally(function () {
        setLoading(false);
      });
  }

  function reset() {
    setStep(0);
    setDataModel(null);
    setValidation(null);
    setSqlOutput(null);
    setErdData(null);
    setError('');
  }

  function handleGenerate(opts) {
    wrap(async function () {
      var res = await generateModel(
        opts.userQuery,
        opts.operation,
        opts.existingModel,
        opts.modelType,
        opts.dbEngine
      );
      var model = res.data_model || {};
      var engine = res.db_engine || opts.dbEngine || 'MySQL';
      model.db_type = engine;

      setDbEngine(engine);
      setDataModel(model);
      setOperation(res.operation || opts.operation);
      setValidationMode(opts.validationMode);
      setValidation(null);
      setStep(1);
    });
  }

  function handleAutoValidate() {
    wrap(async function () {
      var model = Object.assign({}, dataModel, { db_type: dbEngine });
      var res = await validateAndGenerateSQL(model, operation);
      setValidation(res.validation);
      if (res.sql_output && Object.keys(res.sql_output).length > 0) {
        setSqlOutput(res.sql_output);
        setStep(2);
      }
    });
  }

  function handleApprove() {
    wrap(async function () {
      var model = Object.assign({}, dataModel, { db_type: dbEngine });
      var res = await approveAndGenerateSQL(model, operation);
      setSqlOutput(res.sql_output);
      setStep(2);
    });
  }

  function handleFeedback(feedbackText) {
    wrap(async function () {
      var model = Object.assign({}, dataModel, { db_type: dbEngine });
      var res = await applyFeedbackAndGenerateSQL(
        model,
        feedbackText,
        operation
      );
      setDataModel(res.data_model);
      if (res.sql_output && Object.keys(res.sql_output).length > 0) {
        setSqlOutput(res.sql_output);
        setStep(2);
      }
    });
  }

  function handleSqlERD(sql) {
    setErdLoading(true);
    setError('');
    generateERD(sql)
      .then(function (res) {
        setErdData(res);
        setStep(3);
      })
      .catch(function (e) {
        setError(e.message);
      })
      .finally(function () {
        setErdLoading(false);
      });
  }

  return (
    <div
      style={{
        background: BG,
        minHeight: '100vh',
        color: '#e2e8f0',
        fontFamily: '"DM Sans", system-ui, sans-serif',
      }}
    >
      <style>{'@keyframes spin { to { transform: rotate(360deg); } }'}</style>

      <Header step={step} onReset={reset} />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 40px' }}>
        {step === 0 && (
          <InputForm onSubmit={handleGenerate} loading={loading} error={error} />
        )}

        {step === 1 && (
          <ModelReview
            dataModel={dataModel}
            operation={operation}
            validationMode={validationMode}
            validation={validation}
            loading={loading}
            error={error}
            onAutoValidate={handleAutoValidate}
            onApprove={handleApprove}
            onFeedback={handleFeedback}
          />
        )}

        {step === 2 && (
          <SQLView
            sqlOutput={sqlOutput}
            validation={validation}
            onBack={function () {
              setStep(1);
            }}
            onReset={reset}
            onGenerateERD={handleSqlERD}
            erdLoading={erdLoading}
          />
        )}

        {step === 3 && (
          <ERDView
            erdData={erdData}
            sqlOutput={sqlOutput}
            onBack={function () {
              setStep(2);
            }}
            onReset={reset}
            onRegenerate={handleSqlERD}
            loading={erdLoading}
          />
        )}
      </div>
    </div>
  );
}
