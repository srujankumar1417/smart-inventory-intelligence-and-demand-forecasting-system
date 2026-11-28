import { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { LoadingState, ErrorMessage, EmptyState } from '../components/common/States.jsx';
import { ReliabilityBadge } from '../components/common/Badges.jsx';
import { PlotlyChart } from '../components/common/PlotlyChart.jsx';
import { Icons } from '../components/Icons.jsx';
import { fetchForecast } from '../services/api.js';
import { fmtDate, fmtNum, downloadCSVFile, MAX_HORIZON_WEEKS } from '../utils/format.js';

const PRESET_HORIZONS = [1, 2, 4, 8];

export default function FutureSales({ dataset, metrics, isDemo, onToast }) {
  const location = useLocation();
  const products = metrics?.products || [];
  const datasetId = dataset?.dataset_id || '';

  const [selectedId, setSelectedId] = useState(
    location.state?.productId || products[0]?.product_id || ''
  );
  const [horizon, setHorizon] = useState(4);
  const [customInput, setCustomInput] = useState('4');
  const [horizonError, setHorizonError] = useState(false);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [refreshTick, setRefreshTick] = useState(0);

  const selectedProduct = products.find((p) => p.product_id === selectedId) || products[0];
  const activeProductId = selectedProduct?.product_id || '';

  useEffect(() => {
    if (!datasetId || !activeProductId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const result = await fetchForecast(datasetId, activeProductId, horizon);
        if (!cancelled) setForecast(result);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Unable to generate forecast.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [datasetId, activeProductId, horizon, refreshTick]);

  const forecastChart = useMemo(() => {
    if (!forecast) return { data: [], layout: {} };
    const histSlice = (forecast.history || []).slice(-26);
    const actualX = histSlice.map((h) => fmtDate(h.week_ending));
    const actualY = histSlice.map((h) => h.actual);
    const lastActual = histSlice[histSlice.length - 1];

    const forecastX = [
      ...(lastActual ? [fmtDate(lastActual.week_ending)] : []),
      ...forecast.forecast.map((f) => fmtDate(f.week_ending)),
    ];
    const forecastY = [
      ...(lastActual ? [lastActual.actual] : []),
      ...forecast.forecast.map((f) => f.predicted),
    ];

    const traces = [];
    if (forecast.has_calibrated_intervals) {
      const bandX = forecast.forecast.map((f) => fmtDate(f.week_ending));
      const upperY = forecast.forecast.map((f) => f.upper_bound ?? f.predicted);
      const lowerY = forecast.forecast.map((f) => f.lower_bound ?? f.predicted);
      traces.push({
        name: '80% range (upper)',
        x: bandX,
        y: upperY,
        type: 'scatter',
        mode: 'lines',
        line: { width: 0 },
        showlegend: false,
        hoverinfo: 'skip',
      });
      traces.push({
        name: '80% calibrated range',
        x: bandX,
        y: lowerY,
        type: 'scatter',
        mode: 'lines',
        fill: 'tonexty',
        fillcolor: 'rgba(37, 99, 235, 0.14)',
        line: { width: 0 },
        hovertemplate: '<b>Week ending %{x}</b><br>Lower 80% bound: %{y:,.0f} units<extra></extra>',
      });
    }

    traces.push({
      name: 'Actual demand',
      x: actualX,
      y: actualY,
      type: 'scatter',
      mode: actualX.length === 1 ? 'markers' : 'lines+markers',
      line: { color: '#2563EB', width: 2.5 },
      marker: { color: '#2563EB', size: 5 },
      hovertemplate: '<b>Week ending %{x}</b><br>Actual: %{y:,.0f} units<extra></extra>',
    });

    traces.push({
      name: 'Predicted demand',
      x: forecastX,
      y: forecastY,
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: '#1D4ED8', width: 2.25, dash: 'dash' },
      marker: { color: '#60A5FA', size: 6 },
      hovertemplate: '<b>Week ending %{x}</b><br>Forecast: ~%{y:,.0f} units<extra></extra>',
    });

    const shapes = [];
    const annotations = [];
    if (lastActual) {
      const anchor = fmtDate(lastActual.week_ending);
      shapes.push({
        type: 'line',
        x0: anchor,
        x1: anchor,
        y0: 0,
        y1: 1,
        yref: 'paper',
        line: { color: 'rgba(15,23,42,0.25)', width: 1.25, dash: 'dot' },
      });
      annotations.push({
        x: anchor,
        y: 1.06,
        yref: 'paper',
        text: 'Forecast starts',
        showarrow: false,
        xanchor: 'left',
        xshift: 6,
        font: { size: 11, color: '#64748B' },
      });
    }

    return {
      data: traces,
      layout: {
        margin: { l: 54, r: 24, t: 36, b: 56 },
        showlegend: true,
        legend: { orientation: 'h', x: 0, y: -0.24, font: { size: 12, color: '#475569' } },
        shapes,
        annotations,
        xaxis: { showgrid: false, zeroline: false, linecolor: 'rgba(15,23,42,0.08)', tickfont: { size: 11, color: '#64748B' }, nticks: 8, automargin: true },
        yaxis: { showgrid: true, gridcolor: '#EDF2F7', zeroline: false, rangemode: 'tozero', title: { text: 'Units per week', font: { size: 11, color: '#64748B' }, standoff: 10 }, tickfont: { size: 11, color: '#64748B' }, automargin: true },
      },
    };
  }, [forecast]);

  if (!dataset || !metrics) return <LoadingState message="Loading..." />;
  if (products.length === 0) {
    return <EmptyState title="No products found" message="Upload a CSV with product data to see forecasts." />;
  }

  function handlePresetClick(wk) {
    setHorizonError(false);
    setCustomInput(String(wk));
    setHorizon(wk);
  }

  function handleCustomChange(e) {
    const raw = e.target.value;
    setCustomInput(raw);
    const val = Number(raw);
    const valid = Number.isInteger(val) && val >= 1 && val <= MAX_HORIZON_WEEKS;
    setHorizonError(!valid);
    if (valid) setHorizon(val);
  }

  function handleGenerateClick() {
    const val = Number(customInput);
    const valid = Number.isInteger(val) && val >= 1 && val <= MAX_HORIZON_WEEKS;
    setHorizonError(!valid);
    if (!valid) return;
    setHorizon(val);
    setRefreshTick((t) => t + 1);
  }

  function handleDownloadCsv() {
    if (!forecast || !selectedProduct) return;
    downloadCSVFile(
      `forecast_${selectedProduct.product_id}_${forecast.horizon_weeks}w.csv`,
      ['Product ID', 'Product Name', 'Week Ending', 'Predicted Demand', 'Lower 80%', 'Upper 80%'],
      forecast.forecast.map((f) => [
        selectedProduct.product_id,
        selectedProduct.product_name,
        f.week_ending,
        f.predicted,
        f.lower_bound ?? '',
        f.upper_bound ?? '',
      ])
    );
    onToast?.(`Downloaded forecast CSV for ${selectedProduct.product_name}`);
  }

  const meta = dataset.meta || {};
  const wkWord = forecast?.horizon_weeks === 1 ? 'week' : 'weeks';
  const stockNote =
    selectedProduct?.currentStock !== null && forecast
      ? forecast.total_predicted - selectedProduct.currentStock > 0
        ? `Latest closing stock: ${fmtNum(selectedProduct.currentStock)} units — about ${fmtNum(forecast.total_predicted - selectedProduct.currentStock)} units below ${forecast.horizon_weeks}-${wkWord} expected demand.`
        : `Latest closing stock: ${fmtNum(selectedProduct.currentStock)} units, covering expected demand for the next ${forecast.horizon_weeks} ${wkWord}.`
      : 'Upload Inventory Level data to compare forecast against stock on hand.';
  const partialNote = meta.has_partial_weeks
    ? ` Note: the final observed week (${fmtDate(meta.week_end)}) had only ${meta.last_week_days} operating days, which lowers lag-1 estimates.`
    : '';

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Future Sales</h1>
          <p className="page-subtitle">Recursive weekly demand forecast (1–12 weeks ahead, W-SUN) with calibrated uncertainty intervals.</p>
        </div>
        <div className="page-header-actions">
          {isDemo && (
            <span className="pill pill-demo">{meta.model_info?.model_ready ? 'Random Forest' : 'Demo'}</span>
          )}
        </div>
      </header>

      <section className="card forecast-controls" aria-label="Forecast settings">
        <div className="control-group" style={{ flex: 1, minWidth: 220, maxWidth: 320 }}>
          <label htmlFor="forecastProductSelect">Product</label>
          <select
            id="forecastProductSelect"
            className="select"
            value={activeProductId}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            {products.map((p) => (
              <option key={p.product_id} value={p.product_id}>
                {p.product_name} ({p.category})
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="customHorizonInput">Forecast horizon (1–12 weeks)</label>
          <div className="horizon-row">
            <div className="segmented" role="group" aria-label="Select preset weeks">
              {PRESET_HORIZONS.map((wk) => (
                <button
                  key={wk}
                  type="button"
                  className={`segmented-btn${!horizonError && horizon === wk ? ' is-active' : ''}`}
                  onClick={() => handlePresetClick(wk)}
                >
                  {wk} {wk === 1 ? 'week' : 'weeks'}
                </button>
              ))}
            </div>
            <div className="custom-week-wrap">
              <label htmlFor="customHorizonInput" style={{ fontSize: 13, color: 'var(--ink-secondary)', margin: 0 }}>
                Custom:
              </label>
              <input
                id="customHorizonInput"
                type="number"
                min={1}
                max={MAX_HORIZON_WEEKS}
                value={customInput}
                aria-invalid={horizonError ? 'true' : 'false'}
                aria-describedby={horizonError ? 'horizonErrorMsg' : undefined}
                className={`input custom-week-input${horizonError ? ' is-invalid' : ''}`}
                aria-label="Custom number of weeks (1 to 12)"
                onChange={handleCustomChange}
              />
              <span>wks</span>
            </div>
          </div>
          <span id="horizonErrorMsg" className={`field-error-msg${horizonError ? ' is-shown' : ''}`}>
            Enter a whole number between 1 and 12 weeks.
          </span>
        </div>

        <div>
          <button type="button" className="btn btn-primary" onClick={handleGenerateClick} disabled={loading}>
            {loading ? <><span className="spinner" aria-hidden="true" /> Generating...</> : 'Generate forecast'}
          </button>
        </div>
      </section>

      {error && <ErrorMessage message={error} />}

      {forecast && (
        <section className="card answer-card" aria-live="polite">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <span className="eyebrow">{forecast.engine}</span>
              <ReliabilityBadge label={forecast.reliability_label} />
              {forecast.historical_wape != null && (
                <span className="pill">Hist. WAPE: {forecast.historical_wape.toFixed(1)}%</span>
              )}
            </div>
            <div className="answer-headline">
              Expected demand: <span className="highlight-num">{fmtNum(forecast.total_predicted)} units</span>{' '}
              for {selectedProduct?.product_name} over {forecast.horizon_weeks} {wkWord}.
            </div>
            <div className="answer-sub">
              {stockNote} {forecast.reliability_message}{partialNote}
            </div>
          </div>
          <div>
            <button type="button" className="btn btn-secondary" onClick={handleDownloadCsv}>
              <span style={{ width: 15, height: 15, display: 'inline-flex' }}>{Icons.download}</span>
              Download CSV
            </button>
          </div>
        </section>
      )}

      <section className="card chart-card" style={{ marginBottom: 24 }}>
        <div className="chart-header">
          <h2 className="card-title">Recent actuals &amp; predicted weekly demand</h2>
          <p className="card-subtitle">
            Solid blue shows actual weekly demand; dashed blue shows recursive forecast; shaded band (when calibrated) shows 80% split-conformal range, not a guarantee.
          </p>
        </div>
        {loading && !forecast ? (
          <LoadingState message="Generating forecast..." />
        ) : (
          <div className="chart-box-tall">
            <PlotlyChart data={forecastChart.data} layout={forecastChart.layout} />
          </div>
        )}
      </section>

      {forecast?.forecast?.length > 0 && (
        <section className="card table-card" aria-label="Weekly forecast breakdown">
          <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border-hairline)' }}>
            <h2 className="card-title">Week-by-week forecast (W-SUN)</h2>
          </div>
          <div className="table-wrapper" tabIndex={0} role="region" aria-label="Weekly forecast table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Week ending</th>
                  <th className="align-right">Predicted demand</th>
                  <th className="align-right">Lower 80%</th>
                  <th className="align-right">Upper 80%</th>
                </tr>
              </thead>
              <tbody>
                {forecast.forecast.map((f) => (
                  <tr key={f.step}>
                    <td>{fmtDate(f.week_ending)}</td>
                    <td className="align-right">{fmtNum(f.predicted)} units</td>
                    <td className="align-right text-muted">{f.lower_bound != null ? fmtNum(f.lower_bound) : '—'}</td>
                    <td className="align-right text-muted">{f.upper_bound != null ? fmtNum(f.upper_bound) : '—'}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td>Total ({forecast.horizon_weeks} {wkWord})</td>
                  <td className="align-right">{fmtNum(forecast.total_predicted)} units</td>
                  <td className="align-right" />
                  <td className="align-right" />
                </tr>
              </tfoot>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
