import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { StatusBadge } from '../components/common/Badges.jsx';
import { PlotlyChart } from '../components/common/PlotlyChart.jsx';
import { LoadingState } from '../components/common/States.jsx';
import { Icons } from '../components/Icons.jsx';
import { fmtNum, fmtDate } from '../utils/format.js';

export default function Home({ dataset, metrics, isDemo, onReplaceDataset }) {
  const navigate = useNavigate();

  const salesOverTimeChart = useMemo(() => {
    if (!metrics) return { data: [], layout: {} };
    const x = metrics.weeklyTotals.map((w) => w.label);
    const y = metrics.weeklyTotals.map((w) => w.total);
    return {
      data: [{
        x,
        y,
        type: 'scatter',
        mode: x.length === 1 ? 'markers' : 'lines+markers',
        line: { color: '#2563EB', width: 2.25 },
        marker: { color: '#2563EB', size: 4 },
        fill: 'tozeroy',
        fillcolor: 'rgba(37, 99, 235, 0.08)',
        hovertemplate: '<b>Week ending %{x}</b><br>Total demand: %{y:,.0f} units<extra></extra>',
      }],
      layout: {
        margin: { l: 54, r: 16, t: 12, b: 42 },
        xaxis: { showgrid: false, zeroline: false, linecolor: 'rgba(15,23,42,0.08)', tickfont: { size: 11, color: '#64748B' }, nticks: 6, automargin: true },
        yaxis: { showgrid: true, gridcolor: '#EDF2F7', zeroline: false, rangemode: 'tozero', tickfont: { size: 11, color: '#64748B' }, automargin: true },
      },
    };
  }, [metrics]);

  const stockHealthChart = useMemo(() => {
    if (!metrics) return { data: [], layout: {} };
    const hc = metrics.healthCounts;
    const maxVal = Math.max(hc.order_now, hc.order_soon, hc.healthy, hc.excess, 2);
    return {
      data: [{
        x: ['Order now', 'Order soon', 'Healthy', 'Excess'],
        y: [hc.order_now, hc.order_soon, hc.healthy, hc.excess],
        type: 'bar',
        width: 0.48,
        marker: { color: ['#DC2626', '#D97706', '#16A34A', '#64748B'] },
        hovertemplate: '<b>%{x}</b><br>%{y} products<extra></extra>',
      }],
      layout: {
        margin: { l: 40, r: 16, t: 12, b: 38 },
        yaxis: { showgrid: true, gridcolor: '#EDF2F7', zeroline: false, dtick: Math.max(1, Math.ceil(maxVal / 4)), rangemode: 'tozero', tickfont: { size: 11, color: '#64748B' }, automargin: true },
      },
    };
  }, [metrics]);

  const categoryDemandChart = useMemo(() => {
    if (!metrics) return { data: [], layout: {} };
    const catNames = metrics.categories.map((c) => c.category);
    const catSales = metrics.categories.map((c) => c.weeklyDemand);
    return {
      data: [{
        x: catNames,
        y: catSales,
        type: 'bar',
        width: 0.48,
        marker: { color: '#2563EB' },
        hovertemplate: '<b>%{x}</b><br>Avg. weekly demand: %{y:,.0f} units<extra></extra>',
      }],
      layout: {
        margin: { l: 48, r: 16, t: 12, b: 54 },
        xaxis: { showgrid: false, zeroline: false, linecolor: 'rgba(15,23,42,0.08)', tickfont: { size: 11, color: '#64748B' }, tickangle: catNames.length > 4 ? -14 : 0, automargin: true },
        yaxis: { showgrid: true, gridcolor: '#EDF2F7', zeroline: false, rangemode: 'tozero', tickfont: { size: 11, color: '#64748B' }, automargin: true },
      },
    };
  }, [metrics]);

  const bestSellersChart = useMemo(() => {
    if (!metrics) return { data: [], layout: {} };
    const topProducts = metrics.bestSellers.slice(0, 6).reverse();
    return {
      data: [{
        y: topProducts.map((p) => p.product_name),
        x: topProducts.map((p) => Math.round(p.avgWeeklyDemand)),
        type: 'bar',
        orientation: 'h',
        width: 0.56,
        marker: { color: '#2563EB' },
        hovertemplate: '<b>%{y}</b><br>Avg. weekly demand: %{x:,.0f} units<extra></extra>',
      }],
      layout: {
        margin: { l: 120, r: 24, t: 10, b: 34 },
        xaxis: { showgrid: true, gridcolor: '#EDF2F7', zeroline: false, rangemode: 'tozero', tickfont: { size: 11, color: '#64748B' }, automargin: true },
        yaxis: { showgrid: false, zeroline: false, tickfont: { size: 11, color: '#475569' }, automargin: true },
      },
    };
  }, [metrics]);

  if (!dataset || !metrics) return <LoadingState message="Loading dashboard..." />;

  const meta = dataset.meta || {};
  const criticalCount = metrics.healthCounts.order_now;
  const soonCount = metrics.healthCounts.order_soon;

  let bannerClass = 'surface-success';
  let bannerIcon = <span className="banner-icon text-success" style={{ width: 18, height: 18 }}>{Icons.checkCircle}</span>;
  let bannerText = 'All stock levels look healthy in the uploaded snapshot.';
  let bannerSub = 'Every tracked product has more than two weeks of estimated cover.';
  let bannerAction = null;

  if (!metrics.hasInventoryData) {
    bannerClass = 'surface-info';
    bannerIcon = <span className="banner-icon" style={{ color: 'var(--primary)', width: 18, height: 18 }}>{Icons.info}</span>;
    bannerText = 'Demand forecast is active. Inventory columns were not present in this CSV.';
    bannerSub = 'Add Inventory Level and Units Sold columns to unlock stockout risk and reorder alerts.';
  } else if (criticalCount > 0) {
    bannerClass = 'surface-critical';
    bannerIcon = <span className="banner-icon text-critical" style={{ width: 18, height: 18 }}>{Icons.alertCircle}</span>;
    bannerText = `${criticalCount} ${criticalCount === 1 ? 'item' : 'items'} may run out soon based on the ${fmtDate(meta.latest_snapshot_date)} snapshot.`;
    bannerSub = soonCount > 0 ? `Another ${soonCount} items have 8–14 days of estimated cover.` : 'Indicative reorder suggestions are ready for review.';
    bannerAction = (
      <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate('/what-to-order')}>
        Review order list
      </button>
    );
  } else if (soonCount > 0) {
    bannerClass = 'surface-warning';
    bannerIcon = <span className="banner-icon text-warning" style={{ width: 18, height: 18 }}>{Icons.clock}</span>;
    bannerText = `No critical stockouts under 7 days, though ${soonCount} items need restocking soon.`;
    bannerSub = 'Plan orders ahead to maintain your safety buffer.';
    bannerAction = (
      <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/what-to-order')}>
        View suggestions
      </button>
    );
  }

  const topAttention = metrics.needsAttention.slice(0, 5);

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">Inventory Overview</h1>
          <p className="page-subtitle">
            Historical snapshot ({fmtDate(meta.latest_snapshot_date || meta.week_end)}) &amp; weekly demand across all stores.
          </p>
        </div>
        <div className="page-header-actions">
          <span className="pill">
            <span className="pill-dot" aria-hidden="true" />
            <span>{meta.file_name}</span>
            <span className="text-muted">· {metrics.weekCount} wks</span>
          </span>
          {isDemo && (
            <span className="pill pill-demo">
              {meta.model_info?.model_ready ? 'Server Demo (RF)' : 'Demo'}
            </span>
          )}
          <button type="button" className="btn btn-secondary btn-sm" onClick={onReplaceDataset}>
            <span style={{ width: 15, height: 15, display: 'inline-flex' }}>{Icons.upload}</span>
            Replace dataset
          </button>
        </div>
      </header>

      <div className={`banner ${bannerClass}`} role="region" aria-label="Inventory summary alert">
        <div className="banner-left">
          {bannerIcon}
          <div>
            <div className="banner-text">{bannerText}</div>
            <div className="banner-sub">{bannerSub}</div>
          </div>
        </div>
        {bannerAction}
      </div>

      <section className="grid-kpi-4" aria-label="Key inventory metrics">
        <div className="card kpi-card">
          <div className="eyebrow">Total Products</div>
          <div className="kpi-value">{fmtNum(metrics.totalProducts)}</div>
          <div className="kpi-meta"><span className="text-muted">Across {fmtNum(metrics.categories.length)} categories</span></div>
        </div>
        <div className="card kpi-card">
          <div className="eyebrow">Total Stores</div>
          <div className="kpi-value">{fmtNum(metrics.totalStores)}</div>
          <div className="kpi-meta"><span className="text-muted">Aggregated per product</span></div>
        </div>
        <div className="card kpi-card">
          <div className="eyebrow">Latest Week Demand</div>
          <div className="kpi-value">{fmtNum(metrics.latestWeeklyDemand)}</div>
          <div className="kpi-meta">
            {metrics.weeklyDeltaPct !== null ? (
              <>
                <span className={metrics.weeklyDeltaPct >= 0 ? 'delta-up' : 'delta-down'}>
                  {metrics.weeklyDeltaPct >= 0 ? '+' : ''}{metrics.weeklyDeltaPct.toFixed(1)}%
                </span>{' '}
                <span className="text-muted">vs prior week</span>
                {meta.has_partial_weeks && <span className="text-muted">(final week {meta.last_week_days}d partial)</span>}
              </>
            ) : (
              <span className="text-muted">Latest W-SUN week</span>
            )}
          </div>
        </div>
        <div className={`card kpi-card ${criticalCount > 0 ? 'surface-critical' : ''}`}>
          <div className="eyebrow">Items at Risk</div>
          <div className={`kpi-value ${criticalCount > 0 ? 'text-critical' : ''}`}>
            {metrics.hasInventoryData ? fmtNum(criticalCount) : '—'}
          </div>
          <div className="kpi-meta">
            <span className={criticalCount > 0 ? 'text-critical' : 'text-muted'} style={criticalCount > 0 ? { fontWeight: 500 } : undefined}>
              {metrics.hasInventoryData ? (criticalCount > 0 ? 'Under 7 days cover' : 'None under 7 days') : 'No inventory column'}
            </span>
          </div>
        </div>
      </section>

      <section className="grid-2" aria-label="Sales and stock charts">
        <div className="card chart-card">
          <div className="chart-header">
            <h2 className="card-title">Weekly demand over time</h2>
            <p className="card-subtitle">Total demand per Sunday-ending week (W-SUN) across stores</p>
          </div>
          <div className="chart-box"><PlotlyChart data={salesOverTimeChart.data} layout={salesOverTimeChart.layout} /></div>
        </div>
        <div className="card chart-card">
          <div className="chart-header">
            <h2 className="card-title">Stock health breakdown</h2>
            <p className="card-subtitle">Products by estimated days of closing stock cover</p>
          </div>
          <div className="chart-box"><PlotlyChart data={stockHealthChart.data} layout={stockHealthChart.layout} /></div>
        </div>
        <div className="card chart-card">
          <div className="chart-header">
            <h2 className="card-title">Demand by category</h2>
            <p className="card-subtitle">Average weekly demand per product category</p>
          </div>
          <div className="chart-box"><PlotlyChart data={categoryDemandChart.data} layout={categoryDemandChart.layout} /></div>
        </div>
        <div className="card chart-card">
          <div className="chart-header">
            <h2 className="card-title">Best-selling products</h2>
            <p className="card-subtitle">Top items by average weekly demand</p>
          </div>
          <div className="chart-box"><PlotlyChart data={bestSellersChart.data} layout={bestSellersChart.layout} /></div>
        </div>
      </section>

      <section className="card" aria-label="Items needing attention">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h2 className="card-title">Needs attention</h2>
            <p className="card-subtitle">Lowest stock-cover products. Click a row to open its multi-week forecast.</p>
          </div>
          {metrics.needsAttention.length > 0 && (
            <button type="button" className="btn-link" onClick={() => navigate('/what-to-order')}>
              View all ({metrics.needsAttention.length}) →
            </button>
          )}
        </div>

        {topAttention.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No urgent restocks flagged</div>
            <p>No items need immediate ordering under current assumptions.</p>
          </div>
        ) : (
          <div className="attention-list">
            {topAttention.map((p) => (
              <div
                key={p.product_id}
                className="attention-row"
                role="button"
                tabIndex={0}
                onClick={() => navigate('/future-sales', { state: { productId: p.product_id } })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate('/future-sales', { state: { productId: p.product_id } });
                  }
                }}
              >
                <div>
                  <div className="row-product-name">{p.product_name}</div>
                  <div className="row-product-cat">{p.category} · {p.product_id}</div>
                </div>
                <div><StatusBadge statusKey={p.statusKey} /></div>
                <div className="row-stat">
                  <div className={`row-stat-val ${p.statusKey === 'order_now' ? 'text-critical' : 'text-warning'}`}>
                    {p.daysLeft !== null ? `${p.daysLeft}d` : '—'}
                  </div>
                  <div className="row-stat-lbl">Cover</div>
                </div>
                <div className="row-stat">
                  <div className="row-stat-val">{p.currentStock !== null ? `${fmtNum(p.currentStock)} units` : '—'}</div>
                  <div className="row-stat-lbl">Closing stock</div>
                </div>
                <div className="row-stat">
                  <div className="row-stat-val" style={{ color: 'var(--primary)' }}>+{fmtNum(p.suggestedOrderQty)} units</div>
                  <div className="row-stat-lbl">Suggested order</div>
                </div>
                <div className="row-chevron text-muted" aria-hidden="true" style={{ width: 16, height: 16 }}>
                  {Icons.chevronRight}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
