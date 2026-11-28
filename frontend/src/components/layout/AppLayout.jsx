import { useState, useEffect, useRef } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar, MobileHeader } from './Sidebar.jsx';

export function AppLayout({ metrics, toastMsg, resetDialogOpen, onCancelReset, onConfirmReset }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const dialogRef = useRef(null);

  const orderNowCount = metrics?.healthCounts?.order_now ?? 0;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (resetDialogOpen && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal();
    } else if (!resetDialogOpen && dialog.open) {
      dialog.close();
    }
  }, [resetDialogOpen]);

  return (
    <div className="app-shell">
      <MobileHeader
        orderNowCount={orderNowCount}
        drawerOpen={drawerOpen}
        onToggle={() => setDrawerOpen((v) => !v)}
      />
      <Sidebar orderNowCount={orderNowCount} />
      <div className="main-wrap">
        <main className="main-content" id="mainContent" tabIndex={-1}>
          <Outlet />
        </main>
      </div>

      {/* Native Reset Confirmation Dialog */}
      <dialog
        ref={dialogRef}
        className="confirm-dialog"
        aria-labelledby="resetDialogTitle"
        onCancel={(e) => {
          e.preventDefault();
          onCancelReset();
        }}
      >
        <h1 id="resetDialogTitle" className="dialog-title">Reset Smartventory dashboard?</h1>
        <p className="dialog-body">
          This will clear the currently loaded inventory dataset and return you to the upload screen. You can load demo data or upload a CSV again at any time.
        </p>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancelReset}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            style={{ backgroundColor: 'var(--critical)' }}
            onClick={onConfirmReset}
          >
            Reset dashboard
          </button>
        </div>
      </dialog>

      {/* Toast Notification */}
      {toastMsg && (
        <div className="toast" role="status" aria-live="polite">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{toastMsg}</span>
        </div>
      )}
    </div>
  );
}
