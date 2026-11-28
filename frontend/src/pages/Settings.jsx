import { useState } from 'react';
import { LoadingState, ErrorMessage } from '../components/common/States.jsx';
import { Icons } from '../components/Icons.jsx';
import { fmtNum } from '../utils/format.js';

export default function Settings({
  dataset,
  metrics,
  leadTimeWeeks,
  safetyStockWeeks,
  onUpdatePolicy,
  onReplaceDataset,
  onOpenResetDialog,
  onToast,
}) {
  const [lt, setLt] = useState(String(leadTimeWeeks));
  const [ss, setSs] = useState(String(safetyStockWeeks));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!dataset || !metrics) return <LoadingState message="Loading settings..." />;

  const meta = dataset.meta || {};
  const model = meta.model_info || {};

  async function handleApplyPolicy() {
    const ltv = Number(lt);
    const ssv = Number(ss);
    if (ltv < 0 || ssv < 0 || Number.isNaN(ltv) || Number.isNaN(ssv)) {
      setError('Lead time and safety buffer must be >= 0.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onUpdatePolicy(ltv, ssv);
      onToast?.('Updated reorder suggestions with new lead time & buffer');
    } catch (err) {
      setError(err.message || 'Could not update policy.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Settings &amp; Model Details</h1>
          <p className="page-subtitle">Configure indicative reorder assumptions, inspect dataset metadata, and review verified model performance.</p>
        </div>
      </header>

      <div className="settings-stack">
        <section className="card" aria-label="Replenishment policy assumptions">
          <h2 className="card-title">Indicative Replenishment Assumptions</h2>
          <p className="card-subtitle">Since supplier lead times and pack sizes are not fixed in the CSV, configure your planning horizon here.</p>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 16, alignItems: 'flex-end' }}>
            <div className="control-group">
              <label htmlFor="policyLeadTime">Lead time (weeks)</label>
              <input
                id="policyLeadTime"
                type="number"
                step="0.5"
                min="0"
                max="8"
                value={lt}
                className="input"
                style={{ width: 130 }}
                onChange={(e) => setLt(e.target.value)}
              />
            </div>
            <div className="control-group">
              <label htmlFor="policySafetyStock">Safety buffer (weeks)</label>
              <input
                id="policySafetyStock"
                type="number"
                step="0.5"
                min="0"
                max="8"
                value={ss}
                className="input"
                style={{ width: 130 }}
                onChange={(e) => setSs(e.target.value)}
              />
            </div>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!dataset.dataset_id || saving}
              onClick={handleApplyPolicy}
            >
              {saving ? 'Recalculating...' : 'Recalculate orders'}
            </button>
          </div>
          {error && <div style={{ marginTop: 12 }}><ErrorMessage message={error} /></div>}
        </section>

        <section className="card" aria-label="Dataset details">
          <h2 className="card-title">Dataset Details</h2>
          <div className="kv-list">
            <div className="kv-row">
              <span className="kv-key">File name</span>
              <span className="kv-val">{meta.file_name}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key">Date range (W-SUN)</span>
              <span className="kv-val">{metrics.dateRange} ({metrics.weekCount} weeks)</span>
            </div>
            <div className="kv-row">
              <span className="kv-key">Records loaded</span>
              <span className="kv-val">{fmtNum(meta.total_rows)} rows · {fmtNum(metrics.totalProducts)} products · {fmtNum(metrics.totalStores)} stores</span>
            </div>
            <div className="kv-row">
              <span className="kv-key">Closing stock semantics</span>
              <span className="kv-val">{meta.verified_opening_stock_semantics ? 'Verified: Inventory Level - Units Sold' : 'Latest Inventory Level'}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key">Partial boundary weeks</span>
              <span className="kv-val">{meta.has_partial_weeks ? `Yes (First: ${meta.first_week_days}d, Last: ${meta.last_week_days}d)` : 'No'}</span>
            </div>
          </div>
          <div className="settings-actions">
            <button type="button" className="btn btn-secondary" onClick={onReplaceDataset}>
              <span style={{ width: 15, height: 15, display: 'inline-flex' }}>{Icons.upload}</span>
              Replace dataset
            </button>
            <button type="button" className="btn btn-danger-outline" onClick={onOpenResetDialog}>
              Reset dashboard
            </button>
          </div>
        </section>

        <section className="card" aria-label="Model performance details">
          <details className="model-details" open>
            <summary>
              <div>
                <div className="card-title">Model &amp; Evaluation Summary</div>
                <div className="card-subtitle">Verified chronological 80/20 evaluation metrics (never hardcoded)</div>
              </div>
              <span className="chevron-icon" aria-hidden="true" style={{ width: 16, height: 16 }}>
                {Icons.chevronDown}
              </span>
            </summary>
            <div className="metric-explain-grid">
              <div className="metric-explain-box">
                <div className="metric-explain-top"><span className="eyebrow">Algorithm</span></div>
                <div className="metric-explain-val" style={{ fontSize: 15 }}>{model.algorithm || 'N/A'}</div>
                <p className="metric-explain-desc">
                  {model.model_ready
                    ? `Evaluated on ${model.evaluated_rows} chronological test rows (${model.test_weeks} weeks).`
                    : (model.notes?.[0] || 'Insufficient weeks for ML evaluation.')}
                </p>
              </div>
              <div className="metric-explain-box">
                <div className="metric-explain-top">
                  <span className="eyebrow">MAE / WAPE</span>
                  <span className="metric-explain-val">{model.mae != null ? `${model.mae.toFixed(1)} (${model.wape}%)` : '—'}</span>
                </div>
                <p className="metric-explain-desc">Average absolute error across all eligible test rows (including boundary partial weeks).</p>
              </div>
              <div className="metric-explain-box">
                <div className="metric-explain-top">
                  <span className="eyebrow">RMSE / R²</span>
                  <span className="metric-explain-val">{model.rmse != null ? `${model.rmse.toFixed(1)} / ${model.r2}` : '—'}</span>
                </div>
                <p className="metric-explain-desc">Negative R² occurs when partial boundary weeks create sharp drops vs full-week training lags.</p>
              </div>
              <div className="metric-explain-box">
                <div className="metric-explain-top">
                  <span className="eyebrow">80% Conformal Interval</span>
                  <span className="metric-explain-val">{model.conformal_1w_half_width != null ? `±${model.conformal_1w_half_width}` : 'Deferred'}</span>
                </div>
                <p className="metric-explain-desc">
                  {model.conformal_1w_empirical_coverage != null
                    ? `Measured held-out coverage: ${model.conformal_1w_empirical_coverage}% (calibrated on validation slice).`
                    : 'Requires >= 20 training weeks for validation calibration.'}
                </p>
              </div>
            </div>
          </details>
        </section>
      </div>
    </>
  );
}
