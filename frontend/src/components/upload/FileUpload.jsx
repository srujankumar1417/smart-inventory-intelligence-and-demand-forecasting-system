import { useState, useRef } from 'react';
import { Icons } from '../Icons.jsx';
import { downloadSampleCSV } from '../../utils/format.js';

const REQUIRED_COLS = ['Date', 'Product ID', 'Demand'];
const OPTIONAL_COLS = ['Store ID', 'Category', 'Inventory Level', 'Units Sold'];

export function FileUpload({ onUpload, onDemo, isLoading, loadingLabel, error }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [sampleDownloaded, setSampleDownloaded] = useState(false);
  const fileInputRef = useRef(null);

  function handleFile(file) {
    if (!file || isLoading) return;
    onUpload(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    handleFile(file);
  }

  function handleChange(e) {
    handleFile(e.target.files?.[0]);
    e.target.value = '';
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  }

  function handleSampleDownload() {
    downloadSampleCSV();
    setSampleDownloaded(true);
    setTimeout(() => setSampleDownloaded(false), 2500);
  }

  return (
    <section className="upload-shell" aria-label="Upload inventory dataset">
      <div className="upload-header">
        <div className="brand" aria-label="Smartventory">
          <span className="brand-mark" aria-hidden="true">
            <span style={{ width: 16, height: 16, color: '#FFF', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
              {Icons.barChart}
            </span>
          </span>
          <span className="brand-name">Smartventory</span>
        </div>
      </div>

      <div className="card upload-card">
        <h1 className="upload-title">Upload Your Inventory Dataset</h1>
        <p className="upload-desc">
          Import your daily or weekly retail CSV to inspect stock health, Random Forest demand forecasts, calibrated uncertainty ranges, and indicative reorder suggestions.
        </p>

        <div
          className={`dropzone${isDragOver ? ' is-dragover' : ''}`}
          role="button"
          tabIndex={0}
          aria-label="Drag and drop CSV file or browse"
          onDragEnter={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !isLoading && fileInputRef.current?.click()}
          onKeyDown={handleKeyDown}
        >
          <div className="dropzone-icon" aria-hidden="true">
            <span style={{ width: 20, height: 20, display: 'inline-flex' }}>{Icons.upload}</span>
          </div>
          <div className="dropzone-title">Drag and drop your CSV file here</div>
          <div className="dropzone-hint">UTF-8 CSV files up to 16 MB supported</div>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
            disabled={isLoading}
          >
            {isLoading ? <><span className="spinner" aria-hidden="true" /> Processing...</> : 'Browse CSV file'}
          </button>
          <input
            ref={fileInputRef}
            id="csvFileInput"
            type="file"
            accept=".csv,text/csv"
            className="is-hidden"
            onChange={handleChange}
          />
        </div>

        {error && (
          <div className="upload-error" role="alert">
            <span style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }}>{Icons.alertCircle}</span>
            <div>{error}</div>
          </div>
        )}

        {isLoading && (
          <div className="upload-progress" aria-live="polite">
            <div className="progress-meta">
              <span>{loadingLabel || 'Running analysis pipeline...'}</span>
              <span className="num">Working</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: '65%' }} />
            </div>
          </div>
        )}

        <div className="required-cols">
          <div className="required-cols-label">
            <span>Required for forecasting (blue) &amp; recommended for stock alerts</span>
            <button type="button" className="btn-link" style={{ fontSize: 12 }} onClick={handleSampleDownload}>
              {sampleDownloaded ? 'Sample CSV downloaded' : 'Download sample CSV'}
            </button>
          </div>
          <div className="chip-group">
            {REQUIRED_COLS.map((c) => <span key={c} className="col-chip col-chip-req">{c}</span>)}
            {OPTIONAL_COLS.map((c) => <span key={c} className="col-chip">{c}</span>)}
          </div>
        </div>

        <div className="upload-footer">
          <span className="upload-footer-note">Want to explore Smartventory on the sample dataset?</span>
          <button type="button" className="btn btn-secondary" onClick={onDemo} disabled={isLoading}>
            Use demo data
          </button>
        </div>
      </div>
    </section>
  );
}
