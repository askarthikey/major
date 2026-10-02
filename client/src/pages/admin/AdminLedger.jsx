import { useState } from 'react';
import { verifyChain } from '../../services/api';

export default function AdminLedger() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleVerify = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await verifyChain();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">🔗 Ledger Integrity Verification</span>
      </div>

      <p className="text-sm text-muted mb-md">
        Verify the SHA-256 hash chain integrity of the trade ledger.
        Each record's hash is computed from its content + the previous record's hash.
        Any modification to a historical record will break the chain.
      </p>

      <button
        className="btn btn-primary"
        onClick={handleVerify}
        disabled={loading}
        style={{ marginBottom: 16 }}
      >
        {loading ? (
          <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Verifying...</>
        ) : 'Run Verification'}
      </button>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div className={`ledger-result ${result.valid ? 'valid' : 'invalid'}`}>
          <div className="ledger-result-header">
            <span className="ledger-result-icon">
              {result.valid ? '✅' : '❌'}
            </span>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                {result.valid
                  ? 'Ledger Verified: No Tampering Detected'
                  : 'Integrity Violation Detected!'}
              </h3>
              <p className="text-sm text-muted">
                {result.records_checked} of {result.total_records} records checked
              </p>
            </div>
          </div>

          {!result.valid && result.errors?.length > 0 && (
            <div className="ledger-errors">
              <h4 className="text-sm" style={{ marginBottom: 8, color: 'var(--accent-red)' }}>
                Chain broken at record #{result.first_broken_at}:
              </h4>
              {result.errors.map((err, i) => (
                <p key={i} className="text-xs text-mono" style={{ marginBottom: 4, color: 'var(--accent-red)' }}>
                  {err}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
