import { useEffect, useState } from 'react';
import {
  Users,
  Building2,
  Boxes,
  Activity,
  AlertTriangle,
  KeyRound,
  ShieldCheck,
  RefreshCw,
  CheckCircle2,
  Lock,
  ArrowUpRight,
  ShieldAlert,
  Clock,
  Sparkles,
  Zap,
} from 'lucide-react';
import { api, getCached } from '../lib/api';
import { useToast } from '../components/Toast';

export function PageTitle({ title, text, action }) {
  return (
    <div className="page-title">
      <div>
        <div className="eyebrow">ADMINISTRATION CONTROL</div>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      {action && <div className="page-actions">{action}</div>}
    </div>
  );
}

export default function Overview() {
  const cachedOverview = getCached('/admin/overview');
  const cachedAudit = getCached('/admin/audit?limit=6');
  const [data, setData] = useState(() => cachedOverview || null);
  const [recentAudit, setRecentAudit] = useState(() => cachedAudit?.items || []);
  const [loading, setLoading] = useState(() => !cachedOverview);
  const toast = useToast();

  const loadData = (forceFresh = false) => {
    if (!cachedOverview || forceFresh) {
      setLoading(true);
    }
    Promise.all([
      api('/admin/overview', { fresh: forceFresh }).catch(() => null),
      api('/admin/audit?limit=6', { fresh: forceFresh }).catch(() => ({ items: [] })),
    ])
      .then(([overviewData, auditData]) => {
        if (overviewData) setData(overviewData);
        if (auditData?.items) setRecentAudit(auditData.items);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData(false);
  }, []);

  const handleRefresh = () => {
    loadData(true);
    toast.info('Metrics refreshed from control plane');
  };

  const cards = [
    {
      key: 'active_applications',
      label: 'Client Applications',
      desc: 'Active connected clients',
      icon: Boxes,
      color: 'blue',
      value: data?.active_applications ?? 0,
    },
    {
      key: 'organizations',
      label: 'Tenant Organizations',
      desc: 'Isolated scopes',
      icon: Building2,
      color: 'lime',
      value: data?.organizations ?? 0,
    },
    {
      key: 'active_users',
      label: 'Identities / Users',
      desc: `${data?.suspended_users ?? 0} suspended`,
      icon: Users,
      color: 'emerald',
      value: data?.active_users ?? 0,
    },
    {
      key: 'active_sessions',
      label: 'Active Sessions',
      desc: 'Live authenticated sessions',
      icon: Activity,
      color: 'cyan',
      value: data?.active_sessions ?? 0,
    },
    {
      key: 'security_alerts',
      label: 'Security Alerts',
      desc: data?.security_alerts ? 'Action required' : 'All systems normal',
      icon: data?.security_alerts ? AlertTriangle : ShieldCheck,
      color: data?.security_alerts ? 'amber' : 'green',
      value: data?.security_alerts ?? 0,
    },
    {
      key: 'subscription_issues',
      label: 'Subscription Issues',
      desc: data?.subscription_issues ? 'Attention needed' : 'All active',
      icon: Lock,
      color: data?.subscription_issues ? 'rose' : 'gray',
      value: data?.subscription_issues ?? 0,
    },
  ];

  return (
    <div className="overview-container">
      {/* Hero Banner with Logo & System Posture */}
      <div className="overview-hero">
        <div className="hero-content">
          <div className="hero-logo-badge">
            <img src="/logo.png" alt="Nanvi Logo" className="hero-logo-img" />
          </div>
          <div className="hero-text">
            <div className="hero-tag">
              <span className="hero-pulse" />
              <span>UNIVERSAL CONTROL PLANE • ZERO-TRUST ARCHITECTURE</span>
            </div>
            <h2>Enterprise Identity & Authorization Fabric</h2>
            <p>
              Unified administrative oversight across tenant boundaries, API credentials, real-time threat detection, and subscription tiers.
            </p>
          </div>
        </div>
        <div className="hero-actions">
          <button className="primary small hero-btn" onClick={handleRefresh} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>{loading ? 'Syncing…' : 'Sync Metrics'}</span>
          </button>
        </div>
      </div>

      <PageTitle
        title="Telemetry & Resources"
        text="Real-time control plane health metrics and active tenant allocation."
      />

      <div className="metric-grid">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <div className={`metric-card card-${c.color}`} key={c.key}>
              <div className="metric-top">
                <span className="metric-label">{c.label}</span>
                <div className={`metric-icon-box bg-${c.color}`}>
                  <Icon size={18} />
                </div>
              </div>
              <div className="metric-value">
                <strong>{loading && !data ? '…' : c.value}</strong>
              </div>
              <div className="metric-footer">
                <span className="metric-desc">{c.desc}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="overview-split">
        <div className="panel posture-panel">
          <div className="panel-head">
            <div>
              <h2>Control Plane Policy Enforcement</h2>
              <p>Active cryptographic and operational controls</p>
            </div>
            <span className="pill success">
              <span className="dot-green" /> Enforced
            </span>
          </div>

          <div className="posture-grid">
            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-lime" />
                <b>Cryptographic Auth Tokens</b>
              </div>
              <p>RS256 asymmetric signatures with rotating HttpOnly credentials & fast session cache.</p>
            </div>

            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-lime" />
                <b>Hierarchical Credential Engine</b>
              </div>
              <p>Root and scoped child keys with instantaneous subtree freeze and parent revocation.</p>
            </div>

            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-lime" />
                <b>Multi-Tenant Boundaries</b>
              </div>
              <p>Strict cryptographic isolation verified on every control plane dispatch.</p>
            </div>

            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-lime" />
                <b>Fail-Closed Security Posture</b>
              </div>
              <p>Deny-by-default on credential anomalies, lapsed tiers, or unauthorized gateways.</p>
            </div>
          </div>
        </div>

        <div className="panel activity-panel">
          <div className="panel-head">
            <div>
              <h2>Recent Audit Events</h2>
              <p>Real-time stream of security decisions</p>
            </div>
            <Clock size={16} className="text-muted" />
          </div>

          <div className="recent-activity-list">
            {recentAudit.length ? (
              recentAudit.map((evt) => (
                <div className="activity-item" key={evt.id}>
                  <div className="activity-indicator">
                    <span
                      className={`status-dot ${
                        evt.result === 'SUCCESS' ? 'dot-success' : 'dot-danger'
                      }`}
                    />
                  </div>
                  <div className="activity-content">
                    <div className="activity-action">
                      <b>{evt.action}</b>
                      <span className="activity-time">
                        {new Date(evt.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </span>
                    </div>
                    <div className="activity-meta">
                      <span className="activity-resource">{evt.resource}</span>
                      {evt.ip && <span className="activity-ip">{evt.ip}</span>}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-activity">
                <p>No recent activity recorded</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
