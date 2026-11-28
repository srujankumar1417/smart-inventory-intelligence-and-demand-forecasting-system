/** Empty state for pages with no data */
export function EmptyState({ title = 'Nothing here yet', message = '' }) {
  return (
    <div className="empty-state">
      <p className="empty-state-title">{title}</p>
      {message && <p style={{ fontSize: 14 }}>{message}</p>}
    </div>
  );
}

/** Centred spinner for async loading */
export function LoadingState({ message = 'Loading…' }) {
  return (
    <div className="loading-state" aria-live="polite">
      <div className="spinner spinner-dark" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

/** Inline error message */
export function ErrorMessage({ message }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      style={{
        padding: '12px 14px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid color-mix(in srgb, var(--critical) 20%, transparent)',
        borderLeft: '3px solid var(--critical)',
        backgroundColor: 'color-mix(in srgb, var(--critical) 7%, #FFF)',
        fontSize: 13,
        color: '#991B1B',
        marginBottom: 16,
      }}
    >
      {message}
    </div>
  );
}
