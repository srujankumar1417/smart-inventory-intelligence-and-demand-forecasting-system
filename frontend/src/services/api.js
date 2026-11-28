/**
 * Smartventory API service layer.
 * All HTTP calls to the Flask backend are centralised here.
 * Components never call fetch directly.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Parse a fetch Response safely.
 * Returns the JSON body on 2xx, or throws an Error with a user-readable message.
 */
async function parseResponse(res) {
  let body;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    body = await res.json();
  } else {
    const text = await res.text();
    body = { error: text || `HTTP ${res.status}` };
  }

  if (!res.ok) {
    const msg = body?.error || body?.message || `Server error (${res.status})`;
    throw new Error(msg);
  }
  return body;
}

/**
 * Upload a CSV file for analysis.
 * @param {File} file — the CSV file from a file input or drag-and-drop
 * @returns {Promise<object>} — backend /api/analyze response
 */
export async function uploadCSV(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/api/analyze`, {
    method: 'POST',
    body: form,
    // Do NOT set Content-Type; browser sets the multipart boundary automatically
  });
  return parseResponse(res);
}

/**
 * Load the built-in demo dataset (no file upload required).
 * @returns {Promise<object>} — backend /api/analyze response
 */
export async function loadDemo() {
  const res = await fetch(`${BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_demo: true }),
  });
  return parseResponse(res);
}

/**
 * Request a forecast for a product and horizon.
 * @param {string} datasetId — session identifier returned by /api/analyze
 * @param {string} productId — product_id string
 * @param {number} horizonWeeks — number of weeks (1-12)
 * @returns {Promise<object>} — backend /api/forecast response
 */
export async function fetchForecast(datasetId, productId, horizonWeeks) {
  const res = await fetch(`${BASE_URL}/api/forecast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: datasetId,
      product_id: productId,
      horizon_weeks: horizonWeeks,
    }),
  });
  return parseResponse(res);
}

/**
 * Recalculate order recommendations with updated lead-time / safety-stock settings.
 * @param {string} datasetId — session identifier
 * @param {number} leadTimeWeeks
 * @param {number} safetyStockWeeks
 * @returns {Promise<object>} — backend /api/recommendations response
 */
export async function fetchRecommendations(datasetId, leadTimeWeeks, safetyStockWeeks) {
  const res = await fetch(`${BASE_URL}/api/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: datasetId,
      lead_time_weeks: leadTimeWeeks,
      safety_stock_weeks: safetyStockWeeks,
    }),
  });
  return parseResponse(res);
}

/** Health check — returns true if Flask is reachable */
export async function checkHealth() {
  try {
    const res = await fetch(`${BASE_URL}/api/health`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}
