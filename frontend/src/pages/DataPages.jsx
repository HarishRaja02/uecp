import { useEffect, useState, useMemo } from 'react';
import {
  Plus,
  RefreshCw,
  Power,
  Lock,
  Unlock,
  AlertTriangle,
  KeyRound,
  ShieldAlert,
  Building2,
  Users as UsersIcon,
  Check,
  Copy,
  ChevronDown,
  ChevronRight,
  Send,
  Calendar,
  Ban,
  Radio,
  FileKey,
  Shield,
  Eye,
  Info,
  CheckCircle2,
  FileCode,
  Layers,
  Sparkles,
  Zap,
  Clock,
  SlidersHorizontal,
} from 'lucide-react';
import { api } from '../lib/api';
import Table from '../components/Table';
import { PageTitle } from './Overview';
import { useToast } from '../components/Toast';

function useData(path) {
  const [data, setData] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    return api(path)
      .then((x) => {
        setData(x.items || []);
        setError('');
      })
      .catch((err) => setError(err.message || 'Unable to load this section'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [path]);

  return { data, error, loading, reload: load };
}

function Modal({ title, onClose, children }) {
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close modal">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);
  const toast = useToast();

  const handleCopy = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button type="button" className="copy-btn" onClick={handleCopy} title="Copy to clipboard">
      {copied ? <Check size={13} className="text-emerald" /> : <Copy size={13} />}
      {label && <span>{copied ? 'Copied' : label}</span>}
    </button>
  );
}

export function TabPurposeCard({ icon: Icon, title, reason, impact }) {
  return (
    <div className="purpose-card">
      <div className="purpose-icon-box">
        <Icon size={20} />
      </div>
      <div className="purpose-content">
        <div className="purpose-header">
          <b>{title}</b>
          <span className="purpose-tag">CONTROL PLANE CORE</span>
        </div>
        <p className="purpose-reason">{reason}</p>
        {impact && (
          <p className="purpose-impact">
            <strong>System Impact:</strong> {impact}
          </p>
        )}
      </div>
    </div>
  );
}

/* =========================================================================
   1. CREDENTIALS & ACCESS GRANTS
   ========================================================================= */
export function Credentials() {
  const { data, reload, loading } = useData('/admin/access-grants');
  const { data: organizations } = useData('/admin/organizations');
  const { data: applications } = useData('/admin/applications');
  const { data: plans } = useData('/admin/plans');
  const [expanded, setExpanded] = useState({});
  const [showProvision, setShowProvision] = useState(false);
  const [secrets, setSecrets] = useState(null);
  const [actionModal, setActionModal] = useState(null);
  const toast = useToast();

  const handleAction = async (e) => {
    e.preventDefault();
    if (!actionModal) return;
    const { id, action } = actionModal;
    const form = new FormData(e.currentTarget);
    const reason = form.get('reason');
    const payload = { action, reason };

    if (action === 'extend') {
      const expiresAt = form.get('expires_at');
      if (!expiresAt) {
        toast.error('Expiration date is required');
        return;
      }
      payload.expires_at = `${expiresAt}T23:59:59Z`;
    }

    try {
      await api(`/admin/credentials/${id}/action`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      toast.success(`Credential ${action} action succeeded`);
      setActionModal(null);
      reload();
    } catch (err) {
      toast.error(err.message || `Failed to ${action} credential`);
    }
  };

  const handleProvision = async (e) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const expiresAt = form.get('expires_at');

    try {
      const result = await api('/admin/access-grants', {
        method: 'POST',
        body: JSON.stringify({
          organization_id: form.get('organization_id'),
          application_id: form.get('application_id'),
          plan_id: form.get('plan_id'),
          expires_at: `${expiresAt}T23:59:59Z`,
          grace_days: Number(form.get('grace_days') || 0),
          permissions: ['*', 'ai.chat', 'documents.read', 'documents.write', 'email.read', 'reports.download'],
        }),
      });
      setShowProvision(false);
      setSecrets(result);
      toast.success('Access grant and root credentials provisioned');
      reload();
    } catch (err) {
      toast.error(err.message || 'Provisioning failed');
    }
  };

  const toggle = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const stats = useMemo(() => {
    let total = 0,
      active = 0,
      frozen = 0;
    data.forEach((g) => {
      g.credentials?.forEach((c) => {
        total++;
        if (c.status === 'ACTIVE' && c.effective_allowed) active++;
        else frozen++;
      });
    });
    return { total, active, frozen };
  }, [data]);

  return (
    <>
      <PageTitle
        title="Credentials & Access Grants"
        text="Manage tenant access grants, hierarchical API keys, and instant freeze/unfreeze controls."
        action={
          <div className="btn-group">
            <button className="secondary small" onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Refresh</span>
            </button>
            <button className="primary small" onClick={() => setShowProvision(true)}>
              <Plus size={16} />
              <span>Provision Access</span>
            </button>
          </div>
        }
      />

      <TabPurposeCard
        icon={KeyRound}
        title="Why this exists: Hierarchical Access Control Engine"
        reason="Grants establish the security contract between customer organizations and client applications. Each grant issues cryptographically verifiable API keys with instant kill-switch capabilities."
        impact="Freezing any credential immediately blocks all authentication and validation checks across client apps (fail-closed security)."
      />

      <div className="credential-stats-banner">
        <div className="stat-pill">
          <span className="stat-num">{stats.total}</span>
          <span className="stat-text">Total Credentials</span>
        </div>
        <div className="stat-pill stat-active">
          <span className="dot-green" />
          <span className="stat-num">{stats.active}</span>
          <span className="stat-text">Active & Authorized</span>
        </div>
        {stats.frozen > 0 && (
          <div className="stat-pill stat-frozen">
            <span className="dot-red" />
            <span className="stat-num">{stats.frozen}</span>
            <span className="stat-text">Frozen / Denied</span>
          </div>
        )}
      </div>

      <div className="grant-list">
        {data.map((g) => (
          <div className="panel grant-card" key={g.id}>
            <div className="panel-head">
              <div>
                <div className="grant-org-title">
                  <h2>{g.organization}</h2>
                  <span className="grant-app-pill">{g.application}</span>
                </div>
                <div className="grant-id-row">
                  <span className="grant-id-label">Grant ID:</span>
                  <code>{g.id}</code>
                  <CopyButton text={g.id} label="" />
                </div>
              </div>
              <span className={`pill ${g.status === 'ACTIVE' ? 'success' : 'danger'}`}>
                ● {g.status}
              </span>
            </div>

            <div className="grant-meta">
              <span>
                <strong>{g.credentials.length}</strong> credentials
              </span>
              <span>
                Expires:{' '}
                <strong>
                  {g.expires_at ? new Date(g.expires_at).toLocaleDateString() : 'No expiry'}
                </strong>
              </span>
              <span>
                Grace period: <strong>{g.grace_days} days</strong>
              </span>
            </div>

            <div className="credential-tree">
              <div className="tree-header">
                <span>CREDENTIAL / NAME</span>
                <span>STATUS</span>
                <span>EXPIRES</span>
                <span>LAST USED</span>
                <span style={{ textAlign: 'right' }}>ACTIONS</span>
              </div>
              {g.credentials
                .filter((c) => !c.parent_id)
                .map((root) => (
                  <CredentialNode
                    key={root.id}
                    credential={root}
                    all={g.credentials}
                    expanded={expanded}
                    toggle={toggle}
                    onAction={(cred, action) =>
                      setActionModal({ id: cred.id, name: cred.name, action })
                    }
                  />
                ))}
            </div>
          </div>
        ))}
      </div>

      {!data.length && !loading && (
        <div className="panel empty-cell">
          <FileKey size={36} className="empty-icon" />
          <p>No access grants found. Click "Provision Access" to grant access to an organization.</p>
        </div>
      )}

      {/* Provision Access Modal */}
      {showProvision && (
        <Modal title="Provision Customer Access" onClose={() => setShowProvision(false)}>
          <form onSubmit={handleProvision} className="modal-form">
            <label>
              Organization (Tenant)
              <select name="organization_id" required defaultValue="">
                <option value="" disabled>
                  Select organization
                </option>
                {organizations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Application
              <select name="application_id" required defaultValue="">
                <option value="" disabled>
                  Select application
                </option>
                {applications.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Subscription Plan
              <select name="plan_id" required defaultValue="">
                <option value="" disabled>
                  Select plan
                </option>
                {plans.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ({item.code})
                  </option>
                ))}
              </select>
            </label>
            <div className="form-row-2">
              <label>
                Expiration Date
                <input
                  name="expires_at"
                  type="date"
                  required
                  defaultValue={
                    new Date(Date.now() + 365 * 86400000).toISOString().split('T')[0]
                  }
                />
              </label>
              <label>
                Grace Days
                <input name="grace_days" type="number" min="0" defaultValue="14" />
              </label>
            </div>
            <div className="form-note">
              This will create 1 access grant and 3 root credentials with full permission entitlements.
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setShowProvision(false)}
              >
                Cancel
              </button>
              <button className="primary">Create Grant & Root Keys</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Action Confirmation Modal (replaces window.prompt) */}
      {actionModal && (
        <Modal
          title={`${actionModal.action.toUpperCase()} Credential`}
          onClose={() => setActionModal(null)}
        >
          <form onSubmit={handleAction} className="modal-form">
            <div className="action-dialog-intro">
              <p>
                Target Credential: <strong>{actionModal.name}</strong>
              </p>
              {actionModal.action === 'freeze' && (
                <div className="alert-warning">
                  <AlertTriangle size={16} />
                  <span>
                    Freezing will immediately deny all API requests using this credential and any of its child credentials.
                  </span>
                </div>
              )}
              {actionModal.action === 'revoke' && (
                <div className="alert-danger">
                  <Ban size={16} />
                  <span>
                    Permanent revocation cannot be undone. All descendants will be permanently revoked.
                  </span>
                </div>
              )}
            </div>

            {actionModal.action === 'extend' && (
              <label>
                New Expiration Date
                <input
                  name="expires_at"
                  type="date"
                  required
                  defaultValue={
                    new Date(Date.now() + 180 * 86400000).toISOString().split('T')[0]
                  }
                />
              </label>
            )}

            <label>
              Reason for this action
              <input
                name="reason"
                placeholder={
                  actionModal.action === 'freeze'
                    ? 'e.g. Non-payment, compromised token, security review'
                    : 'Reason for audit trail'
                }
                required={['freeze', 'revoke'].includes(actionModal.action)}
                autoFocus
              />
            </label>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal(null)}
              >
                Cancel
              </button>
              <button
                className={
                  ['freeze', 'revoke'].includes(actionModal.action)
                    ? 'danger-btn'
                    : 'primary'
                }
              >
                Confirm {actionModal.action}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* One-Time Secrets Modal */}
      {secrets && (
        <Modal title="Store Root Credential Secrets" onClose={() => setSecrets(null)}>
          <div className="secret-dialog">
            <div className="alert-warning">
              <AlertTriangle size={16} />
              <span>
                These secrets are displayed only once. Store them securely before closing this dialog.
              </span>
            </div>
            <div className="secret-list">
              {secrets.roots?.map((root) => (
                <div className="secret-item" key={root.id}>
                  <div className="secret-label">
                    <b>{root.name}</b>
                    <small>ID: {root.id}</small>
                  </div>
                  <div className="secret-input-row">
                    <input readOnly value={root.secret} />
                    <CopyButton text={root.secret} label="Copy Secret" />
                  </div>
                </div>
              ))}
            </div>
            <div className="modal-actions">
              <button className="primary" onClick={() => setSecrets(null)}>
                Done / I have saved these
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

function CredentialNode({ credential, all, expanded, toggle, onAction }) {
  const children = all.filter((c) => c.parent_id === credential.id);
  const isExpanded = !!expanded[credential.id];
  const isAllowed = credential.effective_allowed;

  return (
    <div className="tree-node">
      <div className={`tree-row ${!isAllowed ? 'row-denied' : ''}`}>
        {/* Column 1: Toggle + Name + ID + Copy Button */}
        <div className="tree-cred-cell">
          <button
            className="tree-toggle"
            onClick={() => toggle(credential.id)}
            disabled={!children.length}
          >
            {children.length ? (
              isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />
            ) : (
              <span className="dot-leaf">•</span>
            )}
          </button>

          <div className="tree-label">
            <div className="cred-name-line">
              <b>{credential.name}</b>
              <span className="kind-badge">{credential.kind}</span>
            </div>
            <div className="cred-id-sub">
              <code>{credential.id}</code>
              <CopyButton text={credential.id} label="" />
            </div>
          </div>
        </div>

        {/* Column 2: Status */}
        <div className="tree-status-col">
          <span className={`pill ${isAllowed ? 'success' : 'danger'}`}>
            ● {credential.effective_status}
          </span>
        </div>

        {/* Column 3: Expiry */}
        <div className="tree-expiry-col">
          {credential.expires_at
            ? new Date(credential.expires_at).toLocaleDateString()
            : 'No expiry'}
        </div>

        {/* Column 4: Last Used */}
        <div className="tree-lastused-col">
          {credential.last_used_at ? (
            <span title={new Date(credential.last_used_at).toLocaleString()}>
              {new Date(credential.last_used_at).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          ) : (
            <span className="text-muted">Never</span>
          )}
        </div>

        {/* Column 5: Actions */}
        <div className="tree-actions-col">
          {isAllowed ? (
            <button
              className="action-btn btn-freeze"
              onClick={() => onAction(credential, 'freeze')}
              title="Freeze credential immediately"
            >
              <Lock size={13} />
              <span>Freeze</span>
            </button>
          ) : (
            <button
              className="action-btn btn-unfreeze"
              onClick={() => onAction(credential, 'unfreeze')}
              title="Unfreeze and restore access"
            >
              <Unlock size={13} />
              <span>Unfreeze</span>
            </button>
          )}
          <button
            className="action-btn"
            onClick={() => onAction(credential, 'extend')}
            title="Extend expiration date"
          >
            <Calendar size={13} />
            <span>Extend</span>
          </button>
          <button
            className="action-btn btn-revoke"
            onClick={() => onAction(credential, 'revoke')}
            title="Permanently revoke"
          >
            <Ban size={13} />
          </button>
        </div>
      </div>

      {isExpanded &&
        children.map((child) => (
          <CredentialNode
            key={child.id}
            credential={child}
            all={all}
            expanded={expanded}
            toggle={toggle}
            onAction={onAction}
          />
        ))}
    </div>
  );
}

/* =========================================================================
   2. APPLICATIONS
   ========================================================================= */
export function Applications() {
  const { data, reload, loading } = useData('/admin/applications');
  const [modal, setModal] = useState(false);
  const [permModal, setPermModal] = useState(null);
  const [configModal, setConfigModal] = useState(null);
  const [name, setName] = useState('');
  const [newKeyResult, setNewKeyResult] = useState(null);
  const toast = useToast();

  const handleCreate = async (e) => {
    e.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) return;
    if (data.some((a) => a.name.toLowerCase() === cleanName.toLowerCase())) {
      toast.error(`An application named '${cleanName}' already exists. Duplicate names are not allowed.`);
      return;
    }
    try {
      const result = await api('/admin/applications', {
        method: 'POST',
        body: JSON.stringify({ name: cleanName }),
      });
      setModal(false);
      setName('');
      setNewKeyResult(result);
      toast.success('Application registered successfully');
      reload();
    } catch (err) {
      toast.error(err.message || 'Failed to create application');
    }
  };

  const handleAddPermission = async (e) => {
    e.preventDefault();
    if (!permModal) return;
    const form = new FormData(e.currentTarget);
    try {
      await api(`/admin/applications/${permModal.id}/permissions`, {
        method: 'POST',
        body: JSON.stringify({
          code: form.get('code'),
          description: form.get('description'),
        }),
      });
      toast.success('Permission added to application');
      setPermModal(null);
      reload();
    } catch (err) {
      toast.error(err.message || 'Failed to add permission');
    }
  };

  return (
    <>
      <PageTitle
        title="Applications"
        text="Register client applications and manage server-side permission policies."
        action={
          <div className="btn-group">
            <button className="secondary small" onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Refresh</span>
            </button>
            <button className="primary small" onClick={() => setModal(true)}>
              <Plus size={16} />
              <span>Register Application</span>
            </button>
          </div>
        }
      />

      <TabPurposeCard
        icon={Boxes}
        title="Why this exists: Client Service Registry & Permissions"
        reason="Declares authorized client services (such as Nanvi AI Enterprise Assistant). Generates Application Keys and governs granular capability permissions (ai.chat, documents.read, etc.)."
        impact="Client applications must present a valid Application Key to query the control plane and validate customer access."
      />

      <Table
        searchable
        filterKey="name"
        searchPlaceholder="Search applications by name..."
        columns={[
          {
            key: 'name',
            label: 'Application',
            render: (r) => (
              <div>
                <b>{r.name}</b>
                <div className="cell-id-row">
                  <code>{r.id}</code>
                  <CopyButton text={r.id} label="" />
                </div>
              </div>
            ),
          },
          {
            key: 'status',
            label: 'Status',
            render: (r) => (
              <span className={`pill ${r.status === 'ACTIVE' ? 'success' : 'danger'}`}>
                ● {r.status}
              </span>
            ),
          },
          {
            key: 'application_key_last4',
            label: 'Key Last 4',
            render: (r) => <code>••••{r.application_key_last4}</code>,
          },
          {
            key: 'permissions',
            label: 'Permissions',
            render: (r) => (
              <button
                className="secondary small"
                onClick={() => setPermModal(r)}
                title="Manage application permissions"
              >
                <span>{r.permissions} permissions</span>
                <Plus size={12} />
              </button>
            ),
          },
          {
            key: 'setup',
            label: 'Client Setup',
            render: (r) => (
              <button
                className="secondary small"
                onClick={() => setConfigModal(r)}
                title="View client configuration template"
              >
                <FileCode size={13} />
                <span>Config (.env)</span>
              </button>
            ),
          },
          {
            key: 'created_at',
            label: 'Created',
            render: (r) => new Date(r.created_at).toLocaleDateString(),
          },
        ]}
        rows={data}
      />

      {/* Config Snippet Modal */}
      {configModal && (
        <Modal
          title={`Integration Config for ${configModal.name}`}
          onClose={() => setConfigModal(null)}
        >
          <div className="secret-dialog">
            <p className="hint">
              Copy these environment variables to your client application's <code>.env</code> file:
            </p>
            <div className="code-box">
              <pre>{`UECP_ENABLED=true
UECP_BASE_URL=http://localhost:8001
UECP_APPLICATION_ID=${configModal.id}
UECP_APPLICATION_KEY=your_uecp_application_key
UECP_CREDENTIAL_ID=your_uecp_credential_id
UECP_CREDENTIAL_SECRET=your_uecp_credential_secret
UECP_VALIDATION_TIMEOUT_SECONDS=5
UECP_CACHE_TTL_SECONDS=60
UECP_ALLOW_INSECURE_HTTP=true`}</pre>
            </div>
            <div className="modal-actions">
              <CopyButton
                text={`UECP_ENABLED=true\nUECP_BASE_URL=http://localhost:8001\nUECP_APPLICATION_ID=${configModal.id}\nUECP_APPLICATION_KEY=your_uecp_application_key\nUECP_CREDENTIAL_ID=your_uecp_credential_id\nUECP_CREDENTIAL_SECRET=your_uecp_credential_secret\nUECP_VALIDATION_TIMEOUT_SECONDS=5\nUECP_CACHE_TTL_SECONDS=60\nUECP_ALLOW_INSECURE_HTTP=true`}
                label="Copy Configuration Template"
              />
              <button className="primary" onClick={() => setConfigModal(null)}>
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Register App Modal */}
      {modal && (
        <Modal title="Register Application" onClose={() => setModal(false)}>
          <form onSubmit={handleCreate} className="modal-form">
            <label>
              Application Name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Nanvi AI Enterprise Assistant"
                required
                autoFocus
              />
            </label>
            <p className="hint">
              UECP will generate a cryptographic application secret that will be shown once upon creation.
            </p>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setModal(false)}>
                Cancel
              </button>
              <button className="primary">Create Application</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Application Secret Display Modal */}
      {newKeyResult && (
        <Modal title="Store Application Key" onClose={() => setNewKeyResult(null)}>
          <div className="secret-dialog">
            <div className="alert-warning">
              <AlertTriangle size={16} />
              <span>
                This Application Key is displayed only once. Store it in your client application's environment configuration.
              </span>
            </div>
            <div className="secret-item">
              <div className="secret-label">
                <b>Application: {newKeyResult.name}</b>
                <small>ID: {newKeyResult.id}</small>
              </div>
              <div className="secret-input-row">
                <input readOnly value={newKeyResult.application_key} />
                <CopyButton text={newKeyResult.application_key} label="Copy Key" />
              </div>
            </div>
            <div className="modal-actions">
              <button className="primary" onClick={() => setNewKeyResult(null)}>
                Done / I have saved this key
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Add Permission Modal */}
      {permModal && (
        <Modal
          title={`Add Permission to ${permModal.name}`}
          onClose={() => setPermModal(null)}
        >
          <form onSubmit={handleAddPermission} className="modal-form">
            <label>
              Permission Code
              <input
                name="code"
                placeholder="e.g. ai.chat, documents.read, reports.download"
                required
                autoFocus
              />
            </label>
            <label>
              Description (Optional)
              <input name="description" placeholder="Short description of this entitlement" />
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setPermModal(null)}>
                Cancel
              </button>
              <button className="primary">Add Permission</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

/* =========================================================================
   3. ORGANIZATIONS (TENANTS)
   ========================================================================= */
export function Organizations() {
  const { data, reload, loading } = useData('/admin/organizations');
  const [modal, setModal] = useState(false);
  const [name, setName] = useState('');
  const toast = useToast();

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await api('/admin/organizations', {
        method: 'POST',
        body: JSON.stringify({ name }),
      });
      setModal(false);
      setName('');
      toast.success('Organization created with default free subscription');
      reload();
    } catch (err) {
      toast.error(err.message || 'Failed to create organization');
    }
  };

  const activeTenants = useMemo(
    () => data.filter((o) => o.status === 'ACTIVE').length,
    [data]
  );

  return (
    <>
      <PageTitle
        title="Organizations (Tenants)"
        text="Manage tenant boundaries, member counts, and organization-level subscription access."
        action={
          <div className="btn-group">
            <button className="secondary small" onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Refresh</span>
            </button>
            <button className="primary small" onClick={() => setModal(true)}>
              <Plus size={16} />
              <span>New Organization</span>
            </button>
          </div>
        }
      />

      <TabPurposeCard
        icon={Building2}
        title="Why this exists: Multi-Tenant Boundary Isolation"
        reason="Ensures strict enterprise tenant separation. Data, users, access grants, and subscription tiers are partition-isolated at the organization level."
        impact="Credentials issued to one organization cannot access or validate for another organization."
      />

      <div className="credential-stats-banner">
        <div className="stat-pill">
          <span className="stat-num">{data.length}</span>
          <span className="stat-text">Total Tenants</span>
        </div>
        <div className="stat-pill stat-active">
          <span className="dot-green" />
          <span className="stat-num">{activeTenants}</span>
          <span className="stat-text">Active Tenants</span>
        </div>
      </div>

      <Table
        searchable
        filterKey="name"
        searchPlaceholder="Search organizations..."
        columns={[
          {
            key: 'name',
            label: 'Organization',
            render: (r) => (
              <div>
                <b>{r.name}</b>
                <div className="cell-id-row">
                  <code>{r.id}</code>
                  <CopyButton text={r.id} label="" />
                </div>
              </div>
            ),
          },
          {
            key: 'status',
            label: 'Tenant Status',
            render: (r) => (
              <span className={`pill ${r.status === 'ACTIVE' ? 'success' : 'danger'}`}>
                ● {r.status}
              </span>
            ),
          },
          {
            key: 'members',
            label: 'Members',
            render: (r) => <span>{r.members} users</span>,
          },
          {
            key: 'subscription_active',
            label: 'Access State',
            render: (r) => (
              <span className={`pill ${r.subscription_active ? 'success' : 'danger'}`}>
                {r.subscription_active ? '● Allowed' : '● Denied'}
              </span>
            ),
          },
          {
            key: 'created_at',
            label: 'Created',
            render: (r) => new Date(r.created_at).toLocaleDateString(),
          },
        ]}
        rows={data}
      />

      {modal && (
        <Modal title="Create New Tenant Organization" onClose={() => setModal(false)}>
          <form onSubmit={handleCreate} className="modal-form">
            <label>
              Organization Name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Acme Corporation"
                required
                autoFocus
              />
            </label>
            <p className="hint">
              Organizations act as strict multi-tenant boundaries. A default Free subscription will be assigned automatically.
            </p>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setModal(false)}>
                Cancel
              </button>
              <button className="primary">Create Organization</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

/* =========================================================================
   4. USERS & IDENTITIES
   ========================================================================= */
export function Users() {
  const { data, reload, loading } = useData('/admin/users');
  const { data: organizations } = useData('/admin/organizations');
  const [modal, setModal] = useState(false);
  const toast = useToast();

  const handleStatus = async (id, status) => {
    try {
      await api(`/admin/users/${id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      toast.success(`User status updated to ${status}`);
      reload();
    } catch (err) {
      toast.error(err.message || 'Status update failed');
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await api('/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          email: form.get('email'),
          password: form.get('password'),
          organization_id: form.get('organization_id'),
          role: form.get('role'),
        }),
      });
      setModal(false);
      toast.success('User account created successfully');
      reload();
    } catch (err) {
      toast.error(err.message || 'Failed to create user');
    }
  };

  return (
    <>
      <PageTitle
        title="Users & Identities"
        text="Manage administrator and member identities, credentials, and real-time account locking."
        action={
          <div className="btn-group">
            <button className="secondary small" onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Refresh</span>
            </button>
            <button className="primary small" onClick={() => setModal(true)}>
              <Plus size={16} />
              <span>Create User</span>
            </button>
          </div>
        }
      />

      <TabPurposeCard
        icon={UsersIcon}
        title="Why this exists: Identity & Access Management (IAM)"
        reason="Governs operator access to the UECP control plane itself. Manages platform administrators, tenant admins, and standard members."
        impact="Suspending an account immediately terminates active sessions and denies further authentication."
      />

      <Table
        searchable
        filterKey="email"
        searchPlaceholder="Search users by email..."
        columns={[
          {
            key: 'email',
            label: 'Identity',
            render: (r) => (
              <div>
                <b>{r.email}</b>
                {r.is_platform_admin && <span className="admin-badge">Admin</span>}
                <div className="cell-id-row">
                  <code>{r.id}</code>
                  <CopyButton text={r.id} label="" />
                </div>
              </div>
            ),
          },
          {
            key: 'role',
            label: 'Tenant Role',
            render: (r) => <span className="role-tag">{r.role || 'USER'}</span>,
          },
          {
            key: 'status',
            label: 'Status',
            render: (r) => (
              <span className={`pill ${r.status === 'ACTIVE' ? 'success' : 'danger'}`}>
                ● {r.status}
              </span>
            ),
          },
          {
            key: 'mfa_enabled',
            label: 'MFA',
            render: (r) => (
              <span className={r.mfa_enabled ? 'text-emerald' : 'text-muted'}>
                {r.mfa_enabled ? 'Enabled' : 'Disabled'}
              </span>
            ),
          },
          {
            key: 'actions',
            label: 'Actions',
            render: (r) => (
              <div className="row-actions">
                {r.status === 'ACTIVE' ? (
                  <button
                    className="action-btn btn-freeze"
                    onClick={() => handleStatus(r.id, 'SUSPENDED')}
                    title="Suspend user session"
                  >
                    <Lock size={13} />
                    <span>Suspend</span>
                  </button>
                ) : (
                  <button
                    className="action-btn btn-unfreeze"
                    onClick={() => handleStatus(r.id, 'ACTIVE')}
                    title="Activate user"
                  >
                    <Power size={13} />
                    <span>Activate</span>
                  </button>
                )}
              </div>
            ),
          },
        ]}
        rows={data}
      />

      {modal && (
        <Modal title="Create User Account" onClose={() => setModal(false)}>
          <form onSubmit={handleCreateUser} className="modal-form">
            <label>
              Email Address
              <input
                name="email"
                type="email"
                placeholder="user@organization.local"
                required
                autoFocus
              />
            </label>
            <label>
              Temporary Password (at least 12 characters)
              <input
                name="password"
                type="password"
                placeholder="Must be at least 12 characters"
                required
                minLength={12}
              />
            </label>
            <label>
              Organization
              <select name="organization_id" required defaultValue="">
                <option value="" disabled>
                  Select organization
                </option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Role
              <select name="role" defaultValue="USER">
                <option value="USER">USER (Standard Member)</option>
                <option value="ORGANIZATION_ADMIN">ORGANIZATION_ADMIN (Tenant Admin)</option>
                <option value="SUPER_ADMIN">SUPER_ADMIN (Full Tenant Control)</option>
              </select>
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setModal(false)}>
                Cancel
              </button>
              <button className="primary">Create User</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

/* =========================================================================
   5. CLIENT INTEGRATION HUB & WEBHOOKS
   ========================================================================= */
export function Integrations() {
  const { data: applications } = useData('/admin/applications');
  const [applicationId, setApplicationId] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [cmdStatus, setCmdStatus] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const toast = useToast();

  const [selectedCredIndex, setSelectedCredIndex] = useState(0);

  const nanviCreds = [
    {
      name: 'Primary Credential',
      id: 'b53f18de-4546-4364-9b3c-5ff410dab2d8',
      secret: 'uecp_cred_s-p3EIGFCUpbv8usqcFqQuqWgl2wrJKkKcv2ZUrDyZo',
      role: 'Production API & Chat Routing',
    },
    {
      name: 'Secondary Backup Credential',
      id: '525fd565-8d7c-4648-a4db-2db94cc6d5fa',
      secret: 'uecp_cred_exys1oxszozn-odvZb_waUfV5S7d5ALYP5imumV9hTs',
      role: 'Failover & Redundant Node',
    },
    {
      name: 'Worker Agent Credential',
      id: 'd3d0dece-5080-4c0d-a081-204139059739',
      secret: 'uecp_cred_THCN54mOjCpXuFBUxHpvoYNs6XX348d6-i1-PTcR6rw',
      role: 'Background Ingestion & Async RAG',
    },
  ];

  const currentCred = nanviCreds[selectedCredIndex];

  const handleTestValidation = async (targetCred = currentCred) => {
    setTesting(true);
    setTestResult(null);
    try {
      const resp = await fetch('http://localhost:8001/api/v1/credentials/validate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Application-Key': 'uecp_KJ2cFJ4N6shuAY1xq2-BrLHw56q49Rv9I75guGVOsf8',
          'X-Credential-ID': targetCred.id,
        },
        body: JSON.stringify({
          credential_secret: targetCred.secret,
          action: 'ai.chat',
        }),
      });
      const json = await resp.json();
      setTestResult({
        status: resp.status,
        credName: targetCred.name,
        data: json,
      });
      if (resp.ok && json.allowed) {
        toast.success(`${targetCred.name} test passed! Access ALLOWED.`);
      } else {
        toast.error(`Validation rejected: ${json.reason || 'Denied'}`);
      }
    } catch (err) {
      setTestResult({
        status: 'Error',
        credName: targetCred.name,
        data: { error: err.message },
      });
      toast.error('Test validation request failed');
    } finally {
      setTesting(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setCmdStatus('');
    try {
      const response = await api(`/admin/applications/${applicationId}/webhook`, {
        method: 'POST',
        body: JSON.stringify({ endpoint }),
      });
      setResult(response);
      toast.success('Webhook endpoint registered');
    } catch (err) {
      setError(err.message || 'Webhook registration failed');
      toast.error(err.message || 'Webhook registration failed');
    }
  };

  const handleCommand = async (e) => {
    e.preventDefault();
    if (!result) return;
    setCmdStatus('');
    setError('');
    const form = new FormData(e.currentTarget);

    try {
      await api(`/admin/webhooks/${result.id}/commands`, {
        method: 'POST',
        body: JSON.stringify({
          command: form.get('command'),
          target_user_id: form.get('target_user_id'),
          reason: form.get('reason'),
        }),
      });
      setCmdStatus('✓ Signed command delivered successfully to external endpoint');
      toast.success('Command dispatched successfully');
    } catch (err) {
      setError(err.message || 'Command delivery failed');
      toast.error(err.message || 'Command delivery failed');
    }
  };

  return (
    <>
      <PageTitle
        title="Client Integration & Webhooks"
        text="Your developer connection hub. Verify client API credentials live or configure outbound HMAC-signed event webhooks."
      />

      <TabPurposeCard
        icon={SlidersHorizontal}
        title="Why this exists: Client Connection Hub & Webhooks"
        reason="Central hub for connecting client applications (like Nanvi AI Assistant) to this control plane, testing credential validation live, or configuring outbound HMAC-signed lifecycle webhooks."
        impact="Client applications authenticate via the Credentials API. Outbound webhooks push signed event notifications to remote microservices."
      />

      {/* Connected Client Guide: Nanvi AI Enterprise Assistant */}
      <div className="panel integration-card highlight-card">
        <div className="panel-head">
          <div>
            <div className="card-badge-row">
              <Sparkles size={16} className="text-orange" />
              <span className="badge-featured">CONNECTED APPLICATION • 3 ACTIVE CREDENTIALS</span>
            </div>
            <h2>Nanvi AI Enterprise Assistant Integration</h2>
            <p>Each application is provisioned with 3 distinct credentials (Primary, Backup, and Worker Agent).</p>
          </div>
          <button
            className="secondary small"
            onClick={() => handleTestValidation(currentCred)}
            disabled={testing}
          >
            <Zap size={14} className={testing ? 'spin' : 'text-emerald'} />
            <span>{testing ? 'Testing…' : `Test ${currentCred.name}`}</span>
          </button>
        </div>

        {/* 3 Credentials Selector Tabs */}
        <div className="cred-selector-tabs">
          {nanviCreds.map((c, idx) => (
            <button
              key={c.id}
              className={`cred-tab-btn ${selectedCredIndex === idx ? 'active' : ''}`}
              onClick={() => setSelectedCredIndex(idx)}
            >
              <b>{idx + 1}. {c.name}</b>
              <small>{c.role}</small>
            </button>
          ))}
        </div>

        <div className="code-box">
          <pre>{`# Universal Enterprise Control Plane (UECP) Integration
# Credential Selected: ${currentCred.name} (${currentCred.role})
UECP_ENABLED=true
UECP_BASE_URL=http://localhost:8001
UECP_APPLICATION_ID=515c0c0f-56ef-4db9-a11a-3ca265d272a7
UECP_APPLICATION_KEY=uecp_KJ2cFJ4N6shuAY1xq2-BrLHw56q49Rv9I75guGVOsf8
UECP_CREDENTIAL_ID=${currentCred.id}
UECP_CREDENTIAL_SECRET=${currentCred.secret}
UECP_VALIDATION_TIMEOUT_SECONDS=5
UECP_CACHE_TTL_SECONDS=60
UECP_ALLOW_INSECURE_HTTP=true`}</pre>
        </div>

        <div className="config-actions">
          <CopyButton
            text={`UECP_ENABLED=true\nUECP_BASE_URL=http://localhost:8001\nUECP_APPLICATION_ID=515c0c0f-56ef-4db9-a11a-3ca265d272a7\nUECP_APPLICATION_KEY=uecp_KJ2cFJ4N6shuAY1xq2-BrLHw56q49Rv9I75guGVOsf8\nUECP_CREDENTIAL_ID=${currentCred.id}\nUECP_CREDENTIAL_SECRET=${currentCred.secret}\nUECP_VALIDATION_TIMEOUT_SECONDS=5\nUECP_CACHE_TTL_SECONDS=60\nUECP_ALLOW_INSECURE_HTTP=true`}
            label={`Copy ${currentCred.name} .env`}
          />
        </div>

        {testResult && (
          <div className="test-result-box">
            <div className="test-result-header">
              <b>Live Test ({testResult.credName} - HTTP {testResult.status}):</b>
              <span
                className={`pill ${
                  testResult.data?.allowed ? 'success' : 'danger'
                }`}
              >
                {testResult.data?.allowed ? '● ALLOWED' : '● DENIED'}
              </span>
            </div>
            <pre className="json-viewer">
              {JSON.stringify(testResult.data, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Outbound Webhook Registration */}
      <div className="panel integration-card">
        <h2>Outbound Lifecycle Webhook Receivers</h2>
        <p>
          Configure remote server URLs that should receive HMAC-SHA256 signed POST events when credentials freeze, renew, or require action.
        </p>

        <form onSubmit={handleRegister} className="modal-form">
          <label>
            Target Client Application
            <select
              value={applicationId}
              onChange={(e) => setApplicationId(e.target.value)}
              required
            >
              <option value="">Select application</option>
              {applications.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            External Webhook Destination URL
            <input
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder="https://api.yourdomain.com/webhooks/uecp"
              required
            />
          </label>

          <div className="modal-actions">
            <button className="primary">Register Webhook Endpoint</button>
          </div>
        </form>

        {error && <div className="error">{error}</div>}
        {cmdStatus && <div className="success-banner">{cmdStatus}</div>}

        {result && (
          <div className="secret-list" style={{ marginTop: 20 }}>
            <div className="success-banner">
              ✓ Active Webhook registered for endpoint: <strong>{result.endpoint}</strong>
            </div>
            <p className="hint">
              Store this signing secret now. It is used to verify HMAC signatures on incoming requests.
            </p>
            <label>
              Signing Secret
              <div className="secret-input-row">
                <input readOnly value={result.signing_secret} />
                <CopyButton text={result.signing_secret} label="Copy Secret" />
              </div>
            </label>

            <h3 style={{ marginTop: 20 }}>Send Signed Test Command</h3>
            <form onSubmit={handleCommand} className="modal-form">
              <label>
                Command Action
                <select name="command" defaultValue="ACCESS_FREEZE">
                  <option value="ACCESS_FREEZE">ACCESS_FREEZE</option>
                  <option value="ACCESS_RENEWED">ACCESS_RENEWED</option>
                  <option value="PASSWORD_RESET_REQUIRED">PASSWORD_RESET_REQUIRED</option>
                </select>
              </label>
              <label>
                Reason
                <input name="reason" placeholder="e.g. Operator test" required />
              </label>
              <div className="modal-actions">
                <button className="secondary">Send Signed Command</button>
              </div>
            </form>
          </div>
        )}
      </div>
    </>
  );
}

/* =========================================================================
   6. SUBSCRIPTIONS & TIERS
   ========================================================================= */
export function Subscriptions() {
  const { data, reload, loading } = useData('/admin/subscriptions');

  const plans = [
    { name: 'Free', code: 'FREE', grace: '14 days', grants: '1 Grant', desc: 'Basic evaluation access' },
    { name: 'Pro', code: 'PRO', grace: '14 days', grants: '5 Grants', desc: 'Growing production apps' },
    { name: 'Business', code: 'BUSINESS', grace: '30 days', grants: '20 Grants', desc: 'Multi-team workloads' },
    { name: 'Enterprise', code: 'ENTERPRISE', grace: '60 days', grants: 'Unlimited', desc: 'Full high-availability & support' },
  ];

  return (
    <>
      <PageTitle
        title="Subscriptions & Tiers"
        text="Plan tiers, quota limits, and automatic effective-access expiration enforcement."
        action={
          <button className="secondary small" onClick={reload} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        }
      />

      <TabPurposeCard
        icon={CreditCard}
        title="Why this exists: Tenant Tier Quotas & Entitlement Policies"
        reason="Binds organizations to plan tiers (Free, Pro, Business, Enterprise) and enforces grace-period expirations."
        impact="When a subscription lapses, the control plane automatically flips effective authorization to Denied, locking the client application until renewed."
      />

      <div className="plan-tiers-grid">
        {plans.map((p) => (
          <div className="plan-card" key={p.code}>
            <div className="plan-card-top">
              <b>{p.name}</b>
              <span className="kind-badge">{p.code}</span>
            </div>
            <p className="plan-desc">{p.desc}</p>
            <div className="plan-specs">
              <span>Limit: <strong>{p.grants}</strong></span>
              <span>Grace: <strong>{p.grace}</strong></span>
            </div>
          </div>
        ))}
      </div>

      <Table
        searchable
        filterKey="organization"
        searchPlaceholder="Filter subscriptions..."
        columns={[
          {
            key: 'organization',
            label: 'Organization',
            render: (r) => <b>{r.organization}</b>,
          },
          {
            key: 'plan',
            label: 'Plan Tier',
            render: (r) => <span className="role-tag">{r.plan}</span>,
          },
          {
            key: 'status',
            label: 'Status',
            render: (r) => (
              <span className={`pill ${r.status === 'ACTIVE' ? 'success' : 'danger'}`}>
                ● {r.status}
              </span>
            ),
          },
          {
            key: 'active',
            label: 'Effective Access',
            render: (r) => (
              <span className={`pill ${r.active ? 'success' : 'danger'}`}>
                {r.active ? '● Allowed' : '● Denied'}
              </span>
            ),
          },
          {
            key: 'expires_at',
            label: 'Expiration',
            render: (r) =>
              r.expires_at ? new Date(r.expires_at).toLocaleDateString() : 'Continuous (No expiry)',
          },
        ]}
        rows={data}
      />
    </>
  );
}

/* =========================================================================
   7. SECURITY CENTER
   ========================================================================= */
export function SecurityCenter() {
  const { data, reload, loading } = useData('/admin/security-events');
  const [processing, setProcessing] = useState(false);
  const toast = useToast();

  const handleExpiryPass = async () => {
    setProcessing(true);
    try {
      await api('/admin/expiry/process', { method: 'POST' });
      toast.success('Automated expiry sweep pass completed successfully');
      reload();
    } catch (err) {
      toast.error(err.message || 'Failed to process expiry sweep');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <>
      <PageTitle
        title="Security Center"
        text="Real-time security signals, failed logins, anomaly flags, and mitigation state."
        action={
          <div className="btn-group">
            <button className="secondary small" onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Refresh</span>
            </button>
            <button
              className="primary small"
              onClick={handleExpiryPass}
              disabled={processing}
            >
              <RefreshCw size={14} className={processing ? 'spin' : ''} />
              <span>Run Expiry Sweep</span>
            </button>
          </div>
        }
      />

      <TabPurposeCard
        icon={ShieldAlert}
        title="Why this exists: Real-Time Threat Intelligence & Expiry Enforcement"
        reason="Aggregates security signals, failed logins, anomaly flags, and executes automated expiration sweep passes."
        impact="Operates on a strict fail-closed model: any anomalous or unverified request is rejected by default."
      />

      <div className="posture-grid" style={{ marginBottom: 20 }}>
        <div className="posture-item">
          <div className="posture-header">
            <CheckCircle2 size={16} className="text-emerald" />
            <b>Fail-Closed Enforcement Active</b>
          </div>
          <p>If any service outage, credential freeze, or DB lapse occurs, authorization returns Denied.</p>
        </div>
        <div className="posture-item">
          <div className="posture-header">
            <CheckCircle2 size={16} className="text-emerald" />
            <b>Automated Expiry Sweeps</b>
          </div>
          <p>Scheduled background passes evaluate credentials reaching grace periods and push alerts.</p>
        </div>
      </div>

      <Table
        searchable
        filterKey="event_type"
        searchPlaceholder="Search security events..."
        columns={[
          {
            key: 'severity',
            label: 'Severity',
            render: (r) => (
              <span
                className={`pill ${
                  ['HIGH', 'CRITICAL'].includes(r.severity)
                    ? 'danger'
                    : r.severity === 'MEDIUM'
                    ? 'warning'
                    : 'info'
                }`}
              >
                ● {r.severity}
              </span>
            ),
          },
          {
            key: 'event_type',
            label: 'Event Type',
            render: (r) => <b>{r.event_type}</b>,
          },
          {
            key: 'timestamp',
            label: 'Logged At',
            render: (r) => new Date(r.timestamp).toLocaleString(),
          },
          {
            key: 'ip',
            label: 'Source IP',
            render: (r) => <code>{r.ip || '—'}</code>,
          },
          {
            key: 'resolved',
            label: 'Status',
            render: (r) => (
              <span className={`pill ${r.resolved ? 'success' : 'danger'}`}>
                {r.resolved ? '● Resolved' : '● Open Signal'}
              </span>
            ),
          },
        ]}
        rows={data}
        empty="No security alerts currently active."
      />
    </>
  );
}

/* =========================================================================
   8. AUDIT LOGS (IMMUTABLE TIMELINE)
   ========================================================================= */
export function Audit() {
  const { data, reload, loading } = useData('/admin/audit?limit=200');
  const [selectedMeta, setSelectedMeta] = useState(null);
  const [actionFilter, setActionFilter] = useState('ALL');

  const actionsList = useMemo(() => {
    const set = new Set();
    data.forEach((d) => d.action && set.add(d.action));
    return Array.from(set);
  }, [data]);

  const filteredData = useMemo(() => {
    if (actionFilter === 'ALL') return data;
    return data.filter((d) => d.action === actionFilter);
  }, [data, actionFilter]);

  return (
    <>
      <PageTitle
        title="Audit Logs"
        text="Immutable event timeline of administrative changes, credential validations, and security decisions."
        action={
          <button className="secondary small" onClick={reload} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        }
      />

      <TabPurposeCard
        icon={Eye}
        title="Why this exists: Immutable Forensic Timeline & Compliance"
        reason="Provides an immutable, tamper-resistant record of every credential validation, administrative toggle, policy mutation, and user authentication for SOC-2 / ISO-27001 compliance."
        impact="Every event captures exact actor identity, target resource, outcome, client IP address, and cryptographic payload."
      />

      <div className="filter-toolbar">
        <label>
          Filter by Event Action:
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
          >
            <option value="ALL">All Actions ({data.length})</option>
            {actionsList.map((act) => (
              <option key={act} value={act}>
                {act} ({data.filter((d) => d.action === act).length})
              </option>
            ))}
          </select>
        </label>
      </div>

      <Table
        searchable
        filterKey="resource"
        searchPlaceholder="Filter audit records..."
        columns={[
          {
            key: 'timestamp',
            label: 'Timestamp',
            render: (r) => (
              <span className="timestamp-cell">
                {new Date(r.timestamp).toLocaleString()}
              </span>
            ),
          },
          {
            key: 'action',
            label: 'Action',
            render: (r) => (
              <span className="action-tag">
                <b>{r.action}</b>
              </span>
            ),
          },
          {
            key: 'resource',
            label: 'Target Resource',
            render: (r) => (
              <div>
                <span>{r.resource}</span>
                {r.resource_id && (
                  <small className="cell-sub">{r.resource_id}</small>
                )}
              </div>
            ),
          },
          {
            key: 'result',
            label: 'Outcome',
            render: (r) => (
              <span className={`pill ${r.result === 'SUCCESS' ? 'success' : 'danger'}`}>
                ● {r.result}
              </span>
            ),
          },
          {
            key: 'ip',
            label: 'Source IP',
            render: (r) => <code>{r.ip || '—'}</code>,
          },
          {
            key: 'details',
            label: 'Metadata',
            render: (r) =>
              r.metadata_json && Object.keys(r.metadata_json).length > 0 ? (
                <button
                  className="secondary small"
                  onClick={() => setSelectedMeta(r)}
                  title="View full event payload"
                >
                  <Eye size={12} />
                  <span>Payload</span>
                </button>
              ) : (
                <span className="text-muted">—</span>
              ),
          },
        ]}
        rows={filteredData}
      />

      {/* Metadata JSON Modal */}
      {selectedMeta && (
        <Modal
          title={`Event Details: ${selectedMeta.action}`}
          onClose={() => setSelectedMeta(null)}
        >
          <div className="json-dialog">
            <div className="json-meta-row">
              <span>Time: {new Date(selectedMeta.timestamp).toLocaleString()}</span>
              <span>Target: {selectedMeta.resource}</span>
            </div>
            <pre className="json-viewer">
              {JSON.stringify(selectedMeta.metadata_json || {}, null, 2)}
            </pre>
            <div className="modal-actions">
              <button className="primary" onClick={() => setSelectedMeta(null)}>
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

/* =========================================================================
   9. NOTIFICATIONS & EXPIRATION LOGS
   ========================================================================= */
export function Notifications() {
  const { data, reload, loading } = useData('/admin/notifications');
  const [processing, setProcessing] = useState(false);
  const toast = useToast();

  const handleProcess = async () => {
    setProcessing(true);
    try {
      await api('/admin/expiry/process', { method: 'POST' });
      toast.success('Expiry check and reminder processing completed');
      reload();
    } catch (err) {
      toast.error(err.message || 'Failed to process notifications');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <>
      <PageTitle
        title="Notifications & Expiration Rules"
        text="Automated reminder passes, grace-period transitions, and SMTP delivery status."
        action={
          <div className="btn-group">
            <button className="secondary small" onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Refresh</span>
            </button>
            <button
              className="primary small"
              onClick={handleProcess}
              disabled={processing}
            >
              <RefreshCw size={14} className={processing ? 'spin' : ''} />
              <span>Run Expiry Pass</span>
            </button>
          </div>
        }
      />

      <TabPurposeCard
        icon={Clock}
        title="Why this exists: Automated Expiration Rules & Notifications"
        reason="Logs automated email delivery and expiration alerts dispatched to tenant administrators when subscriptions or credentials near expiration."
        impact="Runs periodic background evaluations to ensure operators and tenants are alerted before access cuts off."
      />

      <Table
        searchable
        filterKey="recipient"
        searchPlaceholder="Search notifications by recipient..."
        columns={[
          {
            key: 'event_type',
            label: 'Event Type',
            render: (r) => <b>{r.event_type}</b>,
          },
          {
            key: 'recipient',
            label: 'Recipient',
            render: (r) => <span>{r.recipient}</span>,
          },
          {
            key: 'status',
            label: 'Delivery Status',
            render: (r) => (
              <span
                className={`pill ${
                  r.status === 'SENT'
                    ? 'success'
                    : r.status === 'FAILED'
                    ? 'danger'
                    : 'warning'
                }`}
              >
                ● {r.status}
              </span>
            ),
          },
          {
            key: 'attempts',
            label: 'Attempts',
          },
          {
            key: 'created_at',
            label: 'Logged At',
            render: (r) => new Date(r.created_at).toLocaleString(),
          },
        ]}
        rows={data}
        empty="No expiration notifications currently logged."
      />
    </>
  );
}
