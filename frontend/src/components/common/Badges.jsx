import { Icons } from '../Icons.jsx';

/** Original Smartventory status badges */
export function StatusBadge({ statusKey }) {
  if (statusKey === 'order_now')
    return <span className="badge badge-critical">{Icons.alertCircle}Order now</span>;
  if (statusKey === 'order_soon')
    return <span className="badge badge-warning">{Icons.clock}Order soon</span>;
  if (statusKey === 'no_sales')
    return <span className="badge badge-neutral">No recent sales</span>;
  if (statusKey === 'no_inv')
    return <span className="badge badge-neutral">No inventory col</span>;
  return <span className="badge badge-success">{Icons.checkCircle}Enough stock</span>;
}

/** Forecast reliability badge */
export function ReliabilityBadge({ label }) {
  if (label === 'Good') return <span className="badge badge-success">Reliability: Good</span>;
  if (label === 'Low')  return <span className="badge badge-critical">Reliability: Low</span>;
  return <span className="badge badge-warning">Reliability: Moderate</span>;
}
