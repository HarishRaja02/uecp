import { useState } from 'react';
import { API_BASE } from '../lib/api';
import {
  Shield,
  LayoutDashboard,
  Boxes,
  Building2,
  Users,
  ScrollText,
  ShieldAlert,
  CreditCard,
  KeyRound,
  SlidersHorizontal,
  LogOut,
  Menu,
  X,
  ExternalLink,
  Radio,
} from 'lucide-react';

const items = [
  ['Overview', LayoutDashboard, 'Dashboard & system posture'],
  ['Applications', Boxes, 'Registered client applications'],
  ['Credentials', KeyRound, 'Access grants & key trees (Freeze/Unfreeze)'],
  ['Organizations', Building2, 'Multi-tenant boundaries & isolation'],
  ['Users', Users, 'Identity & admin privileges'],
  ['Integrations', SlidersHorizontal, 'Client connection setup & webhooks'],
  ['Subscriptions', CreditCard, 'Tier enforcement & limits'],
  ['Security Center', ShieldAlert, 'Real-time threat signals & expiry sweeps'],
  ['Audit Logs', ScrollText, 'Immutable compliance timeline'],
];

export default function Layout({ section, setSection, onLogout, children }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="shell">
      <aside className={open ? 'open' : ''}>
        <div className="brand">
          <div className="brand-logo">
            <Shield size={22} />
          </div>
          <div className="brand-text">
            <b>UECP</b>
            <small>CONTROL PLANE</small>
          </div>
          <button className="mobile-close" onClick={() => setOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <div className="env-pill">
          <span className="live-dot" />
          <span>DEVELOPMENT • STANDALONE</span>
        </div>

        <nav>
          {items.map(([name, Icon, tooltip]) => {
            const isActive = section === name;
            return (
              <button
                key={name}
                className={isActive ? 'active' : ''}
                title={tooltip}
                onClick={() => {
                  setSection(name);
                  setOpen(false);
                }}
              >
                <Icon size={17} className="nav-icon" />
                <span className="nav-label">{name}</span>
                {isActive && <span className="active-indicator" />}
              </button>
            );
          })}
        </nav>

        <div className="side-foot">
          <div className="user-profile">
            <div className="avatar">A</div>
            <div className="user-meta">
              <span className="user-email">admin@uecp.local</span>
              <span className="user-role">Platform Administrator</span>
            </div>
          </div>
          <div className="side-actions">
            <a
              href={`${API_BASE}/health`}
              target="_blank"
              rel="noreferrer"
              className="side-link"
              title="API Health check"
            >
              <Radio size={14} className="health-dot" />
              <span>API Health</span>
              <ExternalLink size={12} />
            </a>
            <button className="signout-btn" onClick={onLogout}>
              <LogOut size={16} />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </aside>

      <div className="mobile-bar">
        <button className="mobile-toggle" onClick={() => setOpen(true)}>
          <Menu size={20} />
        </button>
        <div className="mobile-brand">
          <Shield size={18} />
          <span>UECP Admin</span>
        </div>
      </div>

      <main>
        <div className="top-banner">
          <div className="breadcrumbs">
            <span>Control Plane</span>
            <span className="sep">/</span>
            <span className="current">{section}</span>
          </div>
          <div className="top-stats">
            <span className="server-status">
              <span className="status-indicator-green" /> Core Engine Active
            </span>
          </div>
        </div>
        {children}
      </main>
    </div>
  );
}
