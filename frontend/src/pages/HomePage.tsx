import { useEffect, useState } from 'react';
import { fetchHealth } from '../api/client';

function HomePage() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Checking backend status...');

  const requestHealth = async () => {
    try {
      const data = await fetchHealth();
      setStatus('success');
      setMessage(JSON.stringify(data, null, 2));
    } catch (error) {
      setStatus('error');
      setMessage(
        error instanceof Error ? error.message : 'Unable to reach the backend health endpoint.',
      );
    }
  };

  const checkHealth = () => {
    setStatus('loading');
    setMessage('Checking backend status...');
    requestHealth();
  };

  useEffect(() => {
    const runInitialCheck = async () => {
      await requestHealth();
    };

    runInitialCheck();
  }, []);

  return (
    <main className="page">
      <h1>API health check</h1>
      <p>
        This frontend reads the backend URL from <strong>import.meta.env.VITE_API_URL</strong>.
      </p>

      <button type="button" disabled={status === 'loading'} onClick={checkHealth}>
        {status === 'loading' ? 'Checking...' : 'Check backend'}
      </button>

      <div
        className={`status ${status === 'error' ? 'error' : status === 'success' ? 'success' : ''}`}
      >
        {status === 'idle' ? 'Waiting for validation...' : message}
      </div>
    </main>
  );
}

export default HomePage;
