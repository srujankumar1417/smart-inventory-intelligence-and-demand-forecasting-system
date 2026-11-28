import { useState, useMemo, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout.jsx';
import { FileUpload } from './components/upload/FileUpload.jsx';
import Home from './pages/Home.jsx';
import FutureSales from './pages/FutureSales.jsx';
import MyStock from './pages/MyStock.jsx';
import WhatToOrder from './pages/WhatToOrder.jsx';
import Settings from './pages/Settings.jsx';
import { uploadCSV, loadDemo, fetchRecommendations } from './services/api.js';
import { computeDashboardAnalytics, fmtNum } from './utils/format.js';

function AppRoutes() {
  const navigate = useNavigate();
  const [dataset, setDataset] = useState(null);
  const [isDemo, setIsDemo] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadLoading, setUploadLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState('');
  const [leadTimeWeeks, setLeadTimeWeeks] = useState(1.0);
  const [safetyStockWeeks, setSafetyStockWeeks] = useState(0.5);
  const [toastMsg, setToastMsg] = useState('');
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const toastTimerRef = useRef(null);

  const showToast = useCallback((msg) => {
    setToastMsg(msg);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToastMsg(''), 3200);
  }, []);

  const metrics = useMemo(
    () => (dataset ? computeDashboardAnalytics(dataset) : null),
    [dataset]
  );

  async function handleUpload(file) {
    setUploadLoading(true);
    setLoadingLabel(`Uploading & running pipeline for ${file.name}...`);
    setUploadError('');
    try {
      const data = await uploadCSV(file);
      setDataset(data);
      setIsDemo(false);
      setLeadTimeWeeks(data.meta?.policy?.lead_time_weeks ?? 1.0);
      setSafetyStockWeeks(data.meta?.policy?.safety_stock_weeks ?? 0.5);
      navigate('/home', { replace: true });
      showToast(`Processed ${file.name} (${fmtNum(data.meta?.total_rows)} rows)`);
    } catch (err) {
      setUploadError(err.message || 'Failed to upload and analyze CSV.');
    } finally {
      setUploadLoading(false);
      setLoadingLabel('');
    }
  }

  async function handleDemo() {
    setUploadLoading(true);
    setLoadingLabel('Running Random Forest & inventory pipeline on sales_data.csv...');
    setUploadError('');
    try {
      const data = await loadDemo();
      setDataset(data);
      setIsDemo(true);
      setLeadTimeWeeks(data.meta?.policy?.lead_time_weeks ?? 1.0);
      setSafetyStockWeeks(data.meta?.policy?.safety_stock_weeks ?? 0.5);
      navigate('/home', { replace: true });
      showToast(`Loaded server demo dataset (${data.meta?.file_name || 'sales_data.csv'})`);
    } catch (err) {
      setUploadError(err.message || 'Could not load server demo data.');
    } finally {
      setUploadLoading(false);
      setLoadingLabel('');
    }
  }

  function handleReplaceDataset() {
    setDataset(null);
    setIsDemo(false);
    setUploadError('');
    navigate('/', { replace: true });
  }

  function handleConfirmReset() {
    setResetDialogOpen(false);
    handleReplaceDataset();
    showToast('Dashboard reset');
  }

  const datasetId = dataset?.dataset_id;
  const handleUpdatePolicy = useCallback(
    async (lt, ss) => {
      if (!datasetId) return;
      const updated = await fetchRecommendations(datasetId, lt, ss);
      setLeadTimeWeeks(lt);
      setSafetyStockWeeks(ss);
      setDataset((prev) => ({
        ...prev,
        recommendations: updated.recommendations ?? prev.recommendations,
        meta: {
          ...prev.meta,
          policy: { ...prev.meta?.policy, lead_time_weeks: lt, safety_stock_weeks: ss },
        },
      }));
    },
    [datasetId]
  );

  if (!dataset) {
    return (
      <Routes>
        <Route
          path="*"
          element={
            <FileUpload
              onUpload={handleUpload}
              onDemo={handleDemo}
              isLoading={uploadLoading}
              loadingLabel={loadingLabel}
              error={uploadError}
            />
          }
        />
      </Routes>
    );
  }

  const pageProps = {
    dataset,
    metrics,
    isDemo,
    leadTimeWeeks,
    safetyStockWeeks,
    onReplaceDataset: handleReplaceDataset,
    onToast: showToast,
  };

  return (
    <Routes>
      <Route
        element={
          <AppLayout
            metrics={metrics}
            toastMsg={toastMsg}
            resetDialogOpen={resetDialogOpen}
            onCancelReset={() => setResetDialogOpen(false)}
            onConfirmReset={handleConfirmReset}
          />
        }
      >
        <Route index element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<Home {...pageProps} />} />
        <Route path="/future-sales" element={<FutureSales {...pageProps} />} />
        <Route path="/my-stock" element={<MyStock {...pageProps} />} />
        <Route path="/what-to-order" element={<WhatToOrder {...pageProps} />} />
        <Route
          path="/settings"
          element={
            <Settings
              {...pageProps}
              onUpdatePolicy={handleUpdatePolicy}
              onOpenResetDialog={() => setResetDialogOpen(true)}
            />
          }
        />
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
