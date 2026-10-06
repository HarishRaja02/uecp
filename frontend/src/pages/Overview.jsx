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
} from 'lucide-react';
import { api } from '../lib/api';
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
  const [data, setData] = useState(null);
  const [recentAudit, setRecentAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api('/admin/overview').catch(() => null),
      api('/admin/audit?limit=5').catch(() => ({ items: [] })),
    ])
      .then(([overviewData, auditData]) => {
        if (overviewData) setData(overviewData);
        if (auditData?.items) setRecentAudit(auditData.items);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    loadData();
    toast.info('Dashboard metrics updated');
  };

  const cards = [
    {
      key: 'active_applications',
      label: 'Client Applications',
      desc: 'Registered services',
      icon: Boxes,
      color: 'blue',
      value: data?.active_applications ?? 0,
    },
    {
      key: 'organizations',
      label: 'Tenant Organizations',
      desc: 'Active isolated scopes',
      icon: Building2,
      color: 'indigo',
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
      desc: 'Live refresh cookies',
      icon: Activity,
      color: 'purple',
      value: data?.active_sessions ?? 0,
    },
    {
      key: 'security_alerts',
      label: 'Security Alerts',
      desc: data?.security_alerts ? 'Action required' : 'All clear',
      icon: data?.security_alerts ? AlertTriangle : ShieldCheck,
      color: data?.security_alerts ? 'amber' : 'gray',
      value: data?.security_alerts ?? 0,
    },
    {
      key: 'subscription_issues',
      label: 'Subscription Issues',
      desc: data?.subscription_issues ? 'Past due / expired' : 'In good standing',
      icon: Lock,
      color: data?.subscription_issues ? 'rose' : 'gray',
      value: data?.subscription_issues ?? 0,
    },
  ];

  return (
    <div className="overview-container">
      <PageTitle
        title="Overview"
        text="Real-time control-plane posture, tenant status, and system activity."
        action={
          <button className="secondary small" onClick={handleRefresh} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        }
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
                <strong>{loading ? '—' : c.value}</strong>
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
              <h2>Control Plane Enforcement</h2>
              <p>Active security layers protecting client applications</p>
            </div>
            <span className="pill success">
              <span className="dot-green" /> Operational
            </span>
          </div>

          <div className="posture-grid">
            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-emerald" />
                <b>Authentication & Identity</b>
              </div>
              <p>RS256 short-lived access tokens with rotating HttpOnly SameSite refresh sessions.</p>
            </div>

            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-emerald" />
                <b>Hierarchical Credential Engine</b>
              </div>
              <p>Root and scoped child credentials with recursive ancestor denial propagation.</p>
            </div>

            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-emerald" />
                <b>Multi-Tenant Isolation</b>
              </div>
              <p>Strict organization scopes validated server-side on every API decision.</p>
            </div>

            <div className="posture-item">
              <div className="posture-header">
                <CheckCircle2 size={16} className="text-emerald" />
                <b>Fail-Closed Authorization</b>
              </div>
              <p>Deny-by-default on credential freeze, subscription lapse, or service outage.</p>
            </div>
          </div>
        </div>

        <div className="panel activity-panel">
          <div className="panel-head">
            <div>
              <h2>Recent Audit Activity</h2>
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
