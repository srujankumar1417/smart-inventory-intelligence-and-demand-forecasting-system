import { Link, NavLink } from 'react-router-dom';
import { Icons } from '../Icons.jsx';

const NAV_ITEMS = [
  { to: '/home', label: 'Home', icon: Icons.home },
  { to: '/future-sales', label: 'Future Sales', icon: Icons.forecast },
  { to: '/my-stock', label: 'My Stock', icon: Icons.stock },
  { to: '/what-to-order', label: 'What to Order', icon: Icons.orders },
];

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span style={{ width: 16, height: 16, color: '#FFF', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        {Icons.barChart}
      </span>
    </span>
  );
}

export function Sidebar({ orderNowCount = 0 }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="sidebar-brand">
        <Link to="/home" className="brand">
          <BrandMark />
          <span className="brand-name">Smartventory</span>
        </Link>
      </div>

      <nav aria-label="Main sections" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <ul className="nav-list" role="list">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <li key={to}>
              <NavLink to={to} className={({ isActive }) => `nav-btn${isActive ? ' is-active' : ''}`}>
                {icon}
                <span>{label}</span>
                {label === 'What to Order' && orderNowCount > 0 && (
                  <span className="nav-count" aria-label={`${orderNowCount} urgent items`}>
                    {orderNowCount}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="nav-bottom">
          <ul className="nav-list" role="list">
            <li>
              <NavLink to="/settings" className={({ isActive }) => `nav-btn${isActive ? ' is-active' : ''}`}>
                {Icons.settings}
                <span>Settings</span>
              </NavLink>
            </li>
          </ul>
        </div>
      </nav>
    </aside>
  );
}

export function MobileHeader({ orderNowCount = 0, drawerOpen, onToggle }) {
  return (
    <header className="mobile-header">
      <div className="mobile-bar">
        <Link to="/home" className="brand">
          <BrandMark />
          <span className="brand-name">Smartventory</span>
        </Link>
        <button
          type="button"
          className="mobile-menu-btn"
          aria-expanded={drawerOpen}
          aria-controls="mobileDrawer"
          aria-label="Toggle navigation menu"
          onClick={onToggle}
        >
          {Icons.menu}
        </button>
      </div>

      <nav id="mobileDrawer" className={`mobile-drawer${drawerOpen ? ' is-open' : ''}`} aria-label="Mobile navigation">
        <ul className="nav-list" role="list">
          {[...NAV_ITEMS, { to: '/settings', label: 'Settings', icon: Icons.settings }].map(({ to, label, icon }) => (
            <li key={to}>
              <NavLink to={to} className={({ isActive }) => `nav-btn${isActive ? ' is-active' : ''}`} onClick={onToggle}>
                {icon}
                <span>{label}</span>
                {label === 'What to Order' && orderNowCount > 0 && (
                  <span className="nav-count" aria-label={`${orderNowCount} urgent items`}>
                    {orderNowCount}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
