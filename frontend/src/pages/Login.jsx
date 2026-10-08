import { useState } from 'react';
import { LockKeyhole, Mail, ShieldAlert, Sparkles, ArrowRight } from 'lucide-react';
import { login } from '../lib/api';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('admin@uecp.local');
  const [password, setPassword] = useState('ChangeThisAdminPassword!2026');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const x = await login(email, password);
      onLogin(x);
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-backdrop-glow login-glow-1" />
      <div className="login-backdrop-glow login-glow-2" />

      <div className="login-card-container">
        <div className="login-header">
          <div className="login-logo-wrapper">
            <img src="/logo.png" alt="Nanvi AI Logo" className="login-logo-img" />
            <div className="login-logo-glow" />
          </div>
          <div className="login-brand-meta">
            <span className="brand-badge">ENTERPRISE SYSTEM</span>
            <h1 className="login-title">
              NANVI <span className="gradient-text">CONTROL PLANE</span>
            </h1>
            <p className="login-subtitle">
              Universal Identity, Governance, Application Gateways & Security Telemetry
            </p>
          </div>
        </div>

        <form className="login-form" onSubmit={submit}>
          {error && (
            <div className="login-error-alert">
              <ShieldAlert size={18} className="alert-icon" />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="login-email">Administrative Email</label>
            <div className="input-with-icon">
              <Mail size={16} className="input-icon" />
              <input
                id="login-email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                type="email"
                placeholder="admin@uecp.local"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <div className="label-row">
              <label htmlFor="login-password">Master Password</label>
              <span className="hint-pill">RS256 Protected</span>
            </div>
            <div className="input-with-icon">
              <LockKeyhole size={16} className="input-icon" />
              <input
                id="login-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                type="password"
                placeholder="••••••••••••••••"
                required
              />
            </div>
          </div>

          <button className="login-submit-btn" disabled={busy} type="submit">
            {busy ? (
              <span className="btn-loading">
                <span className="btn-spinner" />
                <span>Authenticating with Control Plane…</span>
              </span>
            ) : (
              <span className="btn-content">
                <span>Sign in to Control Plane</span>
                <ArrowRight size={16} />
              </span>
            )}
          </button>
        </form>

        <div className="login-footer">
          <div className="security-tag">
            <span className="security-dot" />
            <span>Encrypted Session • Deny-by-Default Architecture</span>
          </div>
        </div>
      </div>
    </div>
  );
}
