import { useNavigate } from 'react-router-dom';
import { LoadingState } from '../components/common/States.jsx';
import { StatusBadge } from '../components/common/Badges.jsx';
import { Icons } from '../components/Icons.jsx';
import { fmtNum, fmtCurrency, fmtDate, downloadCSVFile } from '../utils/format.js';

export default function WhatToOrder({ dataset, metrics, leadTimeWeeks, safetyStockWeeks, onToast }) {
  const navigate = useNavigate();

  if (!dataset || !metrics) return <LoadingState message="Loading recommendations..." />;

  const meta = dataset.meta || {};
  const itemsToOrder = metrics.needsAttention;
  const excessItems = metrics.excessProducts;
  const policy = meta.policy || { lead_time_weeks: leadTimeWeeks, safety_stock_weeks: safetyStockWeeks };

  function handleDownloadOrderList() {
    downloadCSVFile(
      `smartventory_order_list_${meta.uploaded_at || 'export'}.csv`,
      ['Status', 'Product ID', 'Product Name', 'Category', 'Closing Stock', 'Cover Days', 'Suggested Order Qty', 'Assumptions'],
      itemsToOrder.map((p) => [
        p.stock_status,
        p.product_id,
        p.product_name,
        p.category,
        p.currentStock ?? '',
        p.daysLeft ?? '',
        p.suggestedOrderQty,
        p.assumptions,
      ])
    );
    onToast?.('Order list CSV downloaded');
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">What to Order</h1>
          <p className="page-subtitle">
            Indicative reorder quantities assuming {policy.lead_time_weeks}-week lead time + {policy.safety_stock_weeks}-week safety buffer.
          </p>
        </div>
        <div className="page-header-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={itemsToOrder.length === 0}
            onClick={handleDownloadOrderList}
          >
            <span style={{ width: 15, height: 15, display: 'inline-flex' }}>{Icons.download}</span>
            Download order list (CSV)
          </button>
        </div>
      </header>

      <div className="banner surface-info" role="note">
        <div className="banner-left">
          <span className="banner-icon" style={{ color: 'var(--primary)', width: 18, height: 18 }}>{Icons.info}</span>
          <div className="banner-text" style={{ fontWeight: 400 }}>
            Indicative decision support only based on historical snapshot ({fmtDate(meta.latest_snapshot_date || meta.week_end)}), assuming 0 confirmed incoming stock and no fixed MOQ. Adjust lead time in Settings.
          </div>
        </div>
      </div>

      <section className="grid-kpi-2" aria-label="Order summary">
        <div className="card kpi-card">
          <div className="eyebrow">Items to Order</div>
          <div className="kpi-value">{fmtNum(itemsToOrder.length)}</div>
          <div className="kpi-meta">
            <span className="text-critical" style={{ fontWeight: 500 }}>{metrics.healthCounts.order_now} critical (&le;7d)</span>{' '}
            <span className="text-muted">· {metrics.healthCounts.order_soon} order soon</span>
          </div>
        </div>
        <div className="card kpi-card">
          <div className="eyebrow">Total Suggested Units</div>
          <div className="kpi-value">{fmtNum(itemsToOrder.reduce((s, p) => s + p.suggestedOrderQty, 0))}</div>
          <div className="kpi-meta">
            <span className="text-muted">
              {metrics.hasUnitCost
                ? `Est. wholesale spend: ${fmtCurrency(metrics.totalEstimatedOrderSpend)}`
                : 'Wholesale Unit Cost column not in CSV'}
            </span>
          </div>
        </div>
      </section>

      <section aria-label="Suggested order list">
        <div style={{ marginBottom: 14 }}><h2 className="section-title">Priority restock suggestions</h2></div>
        {itemsToOrder.length === 0 ? (
          <div className="card empty-state" style={{ marginBottom: 32 }}>
            <div className="empty-state-title">No reorders needed under current buffer</div>
          </div>
        ) : (
          <div className="order-stack">
            {itemsToOrder.map((p) => (
              <article
                key={p.product_id}
                className={`card order-card ${p.statusKey === 'order_now' ? 'surface-critical' : 'surface-warning'}`}
              >
                <div>
                  <div className="order-card-head">
                    <button
                      type="button"
                      className="product-link"
                      style={{ fontSize: 15 }}
                      onClick={() => navigate('/future-sales', { state: { productId: p.product_id } })}
                    >
                      {p.product_name}
                    </button>
                    <StatusBadge statusKey={p.statusKey} />
                  </div>
                  <div className="order-reason">{p.plainReason}</div>
                </div>
                <div className="order-metric">
                  <div className="order-metric-label">Cover left</div>
                  <div className={`order-metric-val ${p.statusKey === 'order_now' ? 'text-critical' : 'text-warning'}`}>
                    {p.daysLeft !== null ? `${p.daysLeft}d` : '—'}
                  </div>
                </div>
                <div className="order-metric">
                  <div className="order-metric-label">Closing stock</div>
                  <div className="order-metric-val">
                    {p.currentStock !== null ? `${fmtNum(p.currentStock)} units` : '—'}
                  </div>
                </div>
                <div className="order-metric">
                  <div className="order-metric-label">Suggested order</div>
                  <div className="order-metric-val" style={{ color: 'var(--primary)' }}>
                    {fmtNum(p.suggestedOrderQty)} units
                  </div>
                </div>
                <div className="order-metric">
                  <div className="order-metric-label">{metrics.hasUnitCost ? 'Est. cost' : 'Reliability'}</div>
                  <div className="order-metric-val">
                    {metrics.hasUnitCost ? fmtCurrency(p.estimatedOrderCost) : (p.reliability_label || 'Moderate')}
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section aria-label="Excess stock">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
          <div>
            <h2 className="section-title">Excess stock (&gt; 45 days cover)</h2>
            <p className="card-subtitle">Items with high inventory relative to expected demand.</p>
          </div>
          {metrics.hasUnitCost && excessItems.length > 0 && (
            <span className="pill">Capital tied up: <strong>{fmtCurrency(metrics.totalExcessCapital)}</strong></span>
          )}
        </div>

        {excessItems.length === 0 ? (
          <div className="card empty-state"><div className="empty-state-title">No excess stock detected</div></div>
        ) : (
          <div className="card table-card">
            <div className="table-wrapper" tabIndex={0} role="region" aria-label="Excess stock table">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Category</th>
                    <th className="align-right">Closing stock</th>
                    <th className="align-right">Weeks of cover</th>
                  </tr>
                </thead>
                <tbody>
                  {excessItems.map((p) => (
                    <tr key={p.product_id}>
                      <td>
                        <button
                          type="button"
                          className="product-link"
                          onClick={() => navigate('/future-sales', { state: { productId: p.product_id } })}
                        >
                          {p.product_name}
                        </button>
                      </td>
                      <td>{p.category}</td>
                      <td className="align-right">{fmtNum(p.currentStock)} units</td>
                      <td className="align-right">{p.weeksOfStock !== null ? `${p.weeksOfStock.toFixed(1)} wks` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
