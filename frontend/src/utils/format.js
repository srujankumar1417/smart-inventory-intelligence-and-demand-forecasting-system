/**
 * Shared formatting, CSV export, and analytics derivation utilities.
 * Uses backend outputs as the source of truth without recomputing ML forecasts.
 */

export const MAX_HORIZON_WEEKS = 12;
export const THRESHOLDS = { ORDER_NOW_DAYS: 7, ORDER_SOON_DAYS: 14, EXCESS_DAYS: 45 };

export const fmtNum = (v) =>
  Number.isFinite(v) ? Math.round(v).toLocaleString('en-IN') : '0';

export const fmtCurrency = (v) =>
  Number.isFinite(v) ? '₹' + Math.round(v).toLocaleString('en-IN') : '—';

export const fmtDate = (iso) => {
  if (!iso) return '—';
  const p = String(iso).split('T')[0].split('-');
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : iso;
};

/** Trigger browser download for a CSV file */
export function downloadCSVFile(filename, headers, rows) {
  const esc = (val) =>
    /[",\n\r]/.test(String(val ?? ''))
      ? `"${String(val ?? '').replace(/"/g, '""')}"`
      : String(val ?? '');
  const csv = [headers.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))].join('\r\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Build and download a small valid sample CSV matching backend Part 1/2 schema */
export function downloadSampleCSV() {
  const headers = [
    'Date', 'Store ID', 'Product ID', 'Product Name', 'Category',
    'Inventory Level', 'Units Sold', 'Demand', 'Unit Cost',
  ];
  const weeks = ['2026-11-01', '2026-11-08', '2026-11-15', '2026-11-22'];
  const sampleProducts = [
    { id: 'P0001', name: 'Basmati Rice 5kg', cat: 'Groceries', stock: 23, dem: [39, 40, 41, 40], cost: 480 },
    { id: 'P0002', name: 'Sunflower Oil 1L', cat: 'Groceries', stock: 40, dem: [54, 56, 57, 57], cost: 135 },
    { id: 'P0003', name: 'Amul Butter 500g', cat: 'Dairy', stock: 30, dem: [34, 35, 36, 35], cost: 275 },
    { id: 'P0004', name: 'Toor Dal 1kg', cat: 'Groceries', stock: 54, dem: [41, 42, 43, 42], cost: 158 },
  ];
  const rows = [];
  sampleProducts.forEach((p) => {
    weeks.forEach((wk, i) => {
      rows.push([wk, 'S001', p.id, p.name, p.cat, Math.max(10, p.stock), Math.min(10, p.dem[i]), p.dem[i], p.cost]);
    });
  });
  downloadCSVFile('smartventory_sample.csv', headers, rows);
}

/**
 * Compute full dashboard view-model metrics from the backend /api/analyze response.
 * Mirrors the original dashboard metrics while using backend recommendations directly.
 */
export function computeDashboardAnalytics(dataset) {
  const weeks = dataset?.weeks || [];
  const weekCount = weeks.length;
  const meta = dataset?.meta || {};
  const recMap = new Map((dataset?.recommendations || []).map((r) => [r.product_id, r]));
  const hasInventoryData = meta.has_inventory_data === true;
  const policy = meta.policy || { lead_time_weeks: 1.0, safety_stock_weeks: 0.5 };

  const products = (dataset?.products || []).map((p) => {
    const series = (p.weekly_demand || []).map((v) => Math.max(0, Number(v) || 0));
    const avgWeeklyDemand = Number.isFinite(p.avg_weekly_demand)
      ? p.avg_weekly_demand
      : series.length > 0
      ? series.reduce((a, b) => a + b, 0) / series.length
      : 0;

    const rec = recMap.get(p.product_id);
    const currentStock =
      rec?.available_stock != null
        ? Math.max(0, Math.round(Number(rec.available_stock)))
        : p.current_stock != null
        ? Math.max(0, Math.round(Number(p.current_stock)))
        : null;
    const unitCost = p.unit_cost != null ? Number(p.unit_cost) : null;

    const expectedWeekly =
      rec?.predicted_demand != null
        ? Number(rec.predicted_demand)
        : p.next_week_predicted != null
        ? Number(p.next_week_predicted)
        : avgWeeklyDemand;
    const expectedDaily = expectedWeekly / 7;
    const hasSalesVelocity = expectedDaily > 0;

    const weeksOfStock =
      rec?.estimated_weeks_of_cover != null
        ? Number(rec.estimated_weeks_of_cover)
        : p.estimated_weeks_of_cover != null
        ? Number(p.estimated_weeks_of_cover)
        : currentStock !== null && expectedWeekly > 0
        ? currentStock / expectedWeekly
        : null;

    let daysLeft = null;
    if (currentStock !== null) {
      daysLeft = weeksOfStock !== null ? Math.round(weeksOfStock * 7) : (currentStock > 0 ? null : 0);
    }

    const backendStatus = rec?.stock_status || p.stock_status;
    let healthBucket = 'healthy';
    let statusKey = 'enough';

    if (!hasInventoryData || currentStock === null) {
      healthBucket = 'no_inv';
      statusKey = 'no_inv';
    } else if (!hasSalesVelocity && currentStock > 0) {
      healthBucket = 'no_sales';
      statusKey = 'no_sales';
    } else if (backendStatus === 'High Stockout Risk') {
      healthBucket = 'order_now';
      statusKey = 'order_now';
    } else if (backendStatus === 'Low Stock / Reorder Soon') {
      healthBucket = 'order_soon';
      statusKey = 'order_soon';
    } else if (backendStatus === 'Potential Excess Stock' || (daysLeft !== null && daysLeft > THRESHOLDS.EXCESS_DAYS)) {
      healthBucket = 'excess';
      statusKey = 'enough';
    }

    const suggestedOrderQty =
      rec?.suggested_order_quantity != null
        ? Number(rec.suggested_order_quantity) || 0
        : Number(p.suggested_order_quantity) || 0;

    const estimatedOrderCost = unitCost !== null && suggestedOrderQty > 0 ? suggestedOrderQty * unitCost : null;
    const stockValue = unitCost !== null && currentStock !== null ? currentStock * unitCost : null;

    const plainReason =
      rec?.explanation ||
      p.explanation ||
      (currentStock !== null && daysLeft !== null
        ? `About ${daysLeft} days of stock left based on historical demand.`
        : 'No inventory data available.');

    return {
      ...p,
      currentStock,
      unitCost,
      weeklySeries: series,
      avgWeeklyDemand,
      expectedWeekly,
      dailyDemand: expectedDaily,
      daysLeft,
      hasSalesVelocity,
      healthBucket,
      statusKey,
      suggestedOrderQty,
      estimatedOrderCost,
      stockValue,
      weeksOfStock,
      plainReason,
      assumptions:
        rec?.assumptions ||
        p.assumptions ||
        `Assumes ${policy.lead_time_weeks}-week lead time + ${policy.safety_stock_weeks}-week safety buffer.`,
    };
  });

  const weeklyTotals = weeks.map((wk, idx) => ({
    week: wk,
    label: fmtDate(wk),
    total: products.reduce((sum, p) => sum + (p.weeklySeries[idx] || 0), 0),
  }));

  const latestWeeklyDemand = weeklyTotals.length > 0 ? weeklyTotals[weeklyTotals.length - 1].total : 0;
  const priorWeeklyDemand = weeklyTotals.length > 1 ? weeklyTotals[weeklyTotals.length - 2].total : null;
  const weeklyDeltaPct =
    priorWeeklyDemand !== null && priorWeeklyDemand > 0
      ? ((latestWeeklyDemand - priorWeeklyDemand) / priorWeeklyDemand) * 100
      : null;

  const healthCounts = {
    order_now: products.filter((p) => p.healthBucket === 'order_now').length,
    order_soon: products.filter((p) => p.healthBucket === 'order_soon').length,
    healthy: products.filter((p) => p.healthBucket === 'healthy').length,
    excess: products.filter((p) => p.healthBucket === 'excess').length,
  };

  const categoryMap = new Map();
  products.forEach((p) => {
    const cat = p.category || 'General';
    if (!categoryMap.has(cat)) {
      categoryMap.set(cat, { category: cat, weeklyDemand: 0, currentStock: 0, count: 0 });
    }
    const e = categoryMap.get(cat);
    e.weeklyDemand += Math.round(p.avgWeeklyDemand);
    e.currentStock += p.currentStock ?? 0;
    e.count += 1;
  });
  const categories = Array.from(categoryMap.values()).sort((a, b) => b.weeklyDemand - a.weeklyDemand);

  const needsAttention = products
    .filter((p) => p.suggestedOrderQty > 0 || p.statusKey === 'order_now' || p.statusKey === 'order_soon')
    .sort((a, b) => (a.daysLeft ?? 9999) - (b.daysLeft ?? 9999) || b.suggestedOrderQty - a.suggestedOrderQty);

  const excessProducts = products
    .filter((p) => p.healthBucket === 'excess')
    .sort((a, b) => (b.currentStock ?? 0) - (a.currentStock ?? 0));

  const bestSellers = [...products].sort((a, b) => b.avgWeeklyDemand - a.avgWeeklyDemand);
  const slowMovers = [...products].sort((a, b) => a.avgWeeklyDemand - b.avgWeeklyDemand);

  const hasUnitCost = meta.has_unit_cost === true;
  const totalEstimatedOrderSpend = hasUnitCost
    ? needsAttention.reduce((s, p) => s + (p.estimatedOrderCost || 0), 0)
    : null;
  const totalExcessCapital = hasUnitCost
    ? excessProducts.reduce((s, p) => s + (p.stockValue || 0), 0)
    : null;

  return {
    products,
    weeklyTotals,
    weekCount,
    totalProducts: products.length,
    totalStores: (dataset?.stores || []).length,
    latestWeeklyDemand,
    weeklyDeltaPct,
    healthCounts,
    categories,
    needsAttention,
    excessProducts,
    bestSellers,
    slowMovers,
    totalEstimatedOrderSpend,
    totalExcessCapital,
    hasUnitCost,
    hasInventoryData,
    dateRange: weekCount > 0 ? `${fmtDate(weeks[0])} – ${fmtDate(weeks[weekCount - 1])}` : '—',
  };
}
