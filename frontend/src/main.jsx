import { Component, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { refresh, logout } from './lib/api';
import Layout from './components/Layout';
import { ToastProvider } from './components/Toast';
import Login from './pages/Login';
import Overview from './pages/Overview';
import {
  Applications,
  Integrations,
  Organizations,
  Users,
  Subscriptions,
  Credentials,
  Notifications,
  Audit,
  SecurityCenter,
} from './pages/DataPages';
import './styles.css';

class PageErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error) {
    console.error('Dashboard section failed to render', error);
  }
  render() {
    if (this.state.error)
      return (
        <div className="panel page-error">
          <h2>This section could not be displayed</h2>
          <p>{this.state.error.message || 'Unexpected dashboard error'}</p>
          <button className="primary small" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      );
    return this.props.children;
  }
}

function Page({ section }) {
  if (section === 'Overview') return <Overview />;
  if (section === 'Applications') return <Applications />;
  if (section === 'Integrations') return <Integrations />;
  if (section === 'Organizations') return <Organizations />;
  if (section === 'Users') return <Users />;
  if (section === 'Subscriptions') return <Subscriptions />;
  if (section === 'Credentials') return <Credentials />;
  if (section === 'Notifications') return <Notifications />;
  if (section === 'Security Center') return <SecurityCenter />;
  return <Audit />;
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [logged, setLogged] = useState(false);
  const [section, setSection] = useState('Overview');

  useEffect(() => {
    refresh()
      .then(() => setLogged(true))
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>Initializing secure control plane session…</p>
      </div>
    );
  }

  if (!logged) {
    return <Login onLogin={() => setLogged(true)} />;
  }

  return (
    <ToastProvider>
      <Layout
        section={section}
        setSection={setSection}
        onLogout={async () => {
          await logout();
          setLogged(false);
        }}
      >
        <PageErrorBoundary key={section}>
          <Page section={section} />
        </PageErrorBoundary>
      </Layout>
    </ToastProvider>
  );
}

createRoot(document.getElementById('root')).render(<App />);
