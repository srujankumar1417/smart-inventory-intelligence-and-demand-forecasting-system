import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { LoadingState } from '../components/common/States.jsx';
import { StatusBadge } from '../components/common/Badges.jsx';
import { PlotlyChart } from '../components/common/PlotlyChart.jsx';
import { Icons } from '../components/Icons.jsx';
import { fmtNum, fmtDate } from '../utils/format.js';

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
const EMPTY_LIST = [];

function SortHeader({ col, label, alignRight, sortKey, sortDir, onSort }) {
  const ariaSort = sortKey === col ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined;
  return (
    <th scope="col" aria-sort={ariaSort} className={alignRight ? 'align-right' : undefined}>
      <button type="button" onClick={() => onSort(col)}>
        {label}
        <span className="sort-indicator">{Icons.sortArrow}</span>
      </button>
    </th>
  );
}

export default function MyStock({ dataset, metrics }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sortKey, setSortKey] = useState('daysLeft');
  const [sortDir, setSortDir] = useState('asc');

  const products = metrics?.products ?? EMPTY_LIST;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = products.filter((p) => {
      if (categoryFilter !== 'ALL' && p.category !== categoryFilter) return false;
      if (statusFilter !== 'ALL' && p.statusKey !== statusFilter) return false;
      if (q && !`${p.product_name} ${p.product_id} ${p.category}`.toLowerCase().includes(q)) return false;
      return true;
    });

    const dir = sortDir === 'asc' ? 1 : -1;
    return [...list].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'string' || typeof bv === 'string') {
        return collator.compare(String(av ?? ''), String(bv ?? '')) * dir;
      }
      return ((av ?? 999999) - (bv ?? 999999)) * dir;
    });
  }, [products, search, categoryFilter, statusFilter, sortKey, sortDir]);

  const categoryChart = useMemo(() => {
    const cats = metrics?.categories || [];
    return {
      data: [
        {
          name: 'Latest closing stock',
          x: cats.map((c) => c.category),
          y: cats.map((c) => c.currentStock),
          type: 'bar',
          marker: { color: '#CBD5E1' },
          hovertemplate: '<b>%{x}</b><br>Closing stock: %{y:,.0f} units<extra></extra>',
        },
        {
          name: 'Avg. weekly demand',
          x: cats.map((c) => c.category),
          y: cats.map((c) => c.weeklyDemand),
          type: 'bar',
          marker: { color: '#2563EB' },
          hovertemplate: '<b>%{x}</b><br>Weekly demand: %{y:,.0f} units<extra></extra>',
        },
      ],
      layout: {
        barmode: 'group',
        bargap: 0.28,
        bargroupgap: 0.1,
        margin: { l: 52, r: 16, t: 16, b: 56 },
        showlegend: true,
        legend: { orientation: 'h', x: 0, y: 1.12, font: { size: 12, color: '#475569' } },
        yaxis: { showgrid: true, gridcolor: '#EDF2F7', zeroline: false, rangemode: 'tozero', tickfont: { size: 11, color: '#64748B' }, automargin: true },
      },
    };
  }, [metrics]);

  if (!dataset || !metrics) return <LoadingState message="Loading stock..." />;

  const meta = dataset.meta || {};
  const uniqueCategories = metrics.categories.map((c) => c.category);
  const fastMovers = metrics.bestSellers.slice(0, 4);
  const slowMovers = metrics.slowMovers.slice(0, 4);
  const lowStockItems = metrics.needsAttention.slice(0, 6);

  function handleSort(col) {
    if (sortKey === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(col);
      setSortDir('asc');
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">My Stock</h1>
          <p className="page-subtitle">
            Latest closing stock ({fmtDate(meta.latest_snapshot_date || meta.week_end)}), movement speed, and estimated days of cover.
          </p>
        </div>
      </header>

      <div className="toolbar" role="region" aria-label="Filter stock table">
        <div className="toolbar-left">
          <div className="search-wrap">
            <span style={{ width: 15, height: 15 }}>{Icons.search}</span>
            <input
              type="search"
              className="input"
              placeholder="Search product or category..."
              value={search}
              aria-label="Search products"
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="select"
            aria-label="Filter by category"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="ALL">All categories</option>
            {uniqueCategories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
        <div className="segmented" role="group" aria-label="Filter by stock status">
          {[
            { id: 'ALL', label: 'All' },
            { id: 'order_now', label: 'Order now' },
            { id: 'order_soon', label: 'Order soon' },
            { id: 'enough', label: 'Enough stock' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`segmented-btn${statusFilter === tab.id ? ' is-active' : ''}`}
              onClick={() => setStatusFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <section className="card table-card" aria-label="Inventory stock table">
        <div className="table-wrapper" tabIndex={0} role="region" aria-label="Inventory stock levels">
          <table id="stockTable" className="data-table">
            <caption className="visually-hidden">Inventory stock levels and estimated cover by product</caption>
            <thead>
              <tr>
                <SortHeader col="product_name" label="Product" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <SortHeader col="category" label="Category" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <SortHeader col="currentStock" label="Closing stock" alignRight sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <SortHeader col="avgWeeklyDemand" label="Avg. weekly demand" alignRight sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <SortHeader col="daysLeft" label="Stock cover" alignRight sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <div className="empty-state">
                      <div className="empty-state-title">No matching products found</div>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ marginTop: 8 }}
                        onClick={() => { setSearch(''); setCategoryFilter('ALL'); setStatusFilter('ALL'); }}
                      >
                        Clear filters
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map((p) => {
                  const dl = p.daysLeft ?? 999;
                  const pct = p.daysLeft !== null ? Math.min(100, Math.max(4, Math.round((Math.min(dl, 45) / 45) * 100))) : 0;
                  const barColor =
                    p.statusKey === 'order_now'
                      ? 'var(--critical)'
                      : p.statusKey === 'order_soon'
                      ? 'var(--warning)'
                      : p.healthBucket === 'excess'
                      ? '#64748B'
                      : 'var(--success)';
                  const daysLabel =
                    p.daysLeft === null
                      ? p.currentStock === null ? '—' : 'No recent sales'
                      : `${p.daysLeft} ${p.daysLeft === 1 ? 'day' : 'days'}${p.healthBucket === 'excess' ? ' (Excess)' : ''}`;

                  return (
                    <tr key={p.product_id}>
                      <th scope="row">
                        <button
                          type="button"
                          className="product-link"
                          onClick={() => navigate('/future-sales', { state: { productId: p.product_id } })}
                        >
                          {p.product_name}
                        </button>
                        <div className="row-product-cat">{p.product_id}</div>
                      </th>
                      <td style={{ color: 'var(--ink-secondary)' }}>{p.category}</td>
                      <td className="align-right">{p.currentStock !== null ? fmtNum(p.currentStock) : '—'}</td>
                      <td className="align-right">{fmtNum(p.avgWeeklyDemand)}</td>
                      <td className="align-right">
                        <div className="cover-cell">
                          <span style={{ fontSize: 13, fontWeight: 500, color: p.statusKey === 'order_now' ? 'var(--critical)' : 'var(--ink-primary)' }}>
                            {daysLabel}
                          </span>
                          {p.daysLeft !== null && (
                            <div className="cover-bar-track" aria-hidden="true">
                              <div className="cover-bar-fill" style={{ width: `${pct}%`, backgroundColor: barColor }} />
                            </div>
                          )}
                        </div>
                      </td>
                      <td><StatusBadge statusKey={p.statusKey} /></td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid-2" aria-label="Fast and slow moving products">
        <div className="card card-compact">
          <h2 className="card-title">Fast-moving products</h2>
          <p className="card-subtitle">Highest average weekly demand</p>
          <div className="mini-list">
            {fastMovers.map((p) => (
              <div key={p.product_id} className="mini-list-item">
                <div>
                  <button
                    type="button"
                    className="product-link"
                    onClick={() => navigate('/future-sales', { state: { productId: p.product_id } })}
                  >
                    {p.product_name}
                  </button>
                  <div className="row-product-cat">{p.category}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="row-stat-val">{fmtNum(p.avgWeeklyDemand)} / wk</div>
                  <div className="row-product-cat">{p.currentStock !== null ? `${fmtNum(p.currentStock)} in stock` : '—'}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="card card-compact">
          <h2 className="card-title">Slow-moving products</h2>
          <p className="card-subtitle">Lowest weekly turnover</p>
          <div className="mini-list">
            {slowMovers.map((p) => (
              <div key={p.product_id} className="mini-list-item">
                <div>
                  <button
                    type="button"
                    className="product-link"
                    onClick={() => navigate('/future-sales', { state: { productId: p.product_id } })}
                  >
                    {p.product_name}
                  </button>
                  <div className="row-product-cat">{p.category}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="row-stat-val">{fmtNum(p.avgWeeklyDemand)} / wk</div>
                  <div className="row-product-cat">{p.daysLeft !== null ? `${p.daysLeft}d cover` : '—'}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid-2" aria-label="Category stock comparison and low stock list">
        <div className="card chart-card">
          <div className="chart-header">
            <h2 className="card-title">Closing Stock vs. Weekly Demand</h2>
            <p className="card-subtitle">Snapshot stock compared with average weekly demand by category</p>
          </div>
          <div className="chart-box"><PlotlyChart data={categoryChart.data} layout={categoryChart.layout} /></div>
        </div>
        <div className="card card-compact">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div>
              <h2 className="card-title">Low stock quick list</h2>
              <p className="card-subtitle">Items under 14 days estimated cover</p>
            </div>
            {lowStockItems.length > 0 && (
              <button type="button" className="btn-link" style={{ fontSize: 13 }} onClick={() => navigate('/what-to-order')}>
                Order list →
              </button>
            )}
          </div>
          {lowStockItems.length === 0 ? (
            <div className="empty-state"><div className="empty-state-title">No low stock items</div></div>
          ) : (
            <div className="mini-list">
              {lowStockItems.map((p) => (
                <div key={p.product_id} className="mini-list-item">
                  <div>
                    <button
                      type="button"
                      className="product-link"
                      onClick={() => navigate('/future-sales', { state: { productId: p.product_id } })}
                    >
                      {p.product_name}
                    </button>
                    <div className="row-product-cat">{p.currentStock !== null ? `${fmtNum(p.currentStock)} units left` : '—'}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className={`num ${p.statusKey === 'order_now' ? 'text-critical' : 'text-warning'}`} style={{ fontSize: 13, fontWeight: 600 }}>
                      {p.daysLeft !== null ? `${p.daysLeft}d` : '—'}
                    </span>
                    <StatusBadge statusKey={p.statusKey} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </>
  );
}
