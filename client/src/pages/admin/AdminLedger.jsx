import React, { useState } from 'react';
import { useVerifyChain } from '../../hooks/api';
import { Card, Button, PageIntro } from '../../components/ui';

export default function AdminLedger() {
  const { mutate: verifyChain, isPending: loading } = useVerifyChain();
  const [result, setResult] = useState(null);
  const [localError, setLocalError] = useState('');

  const handleVerify = async () => {
    setLocalError('');
    setResult(null);
    try {
      const data = await verifyChain();
      setResult(data);
    } catch (err) {
      setLocalError(err.message);
    }
  };

  return (
    <div className="dashboard-grid">
      <PageIntro
        eyebrow="Trust layer"
        title="Ledger integrity"
        description="Verify that the tamper-evident trade chain is complete and consistent."
      />
      <Card title="Ledger Integrity Verification">
        <p className="text-sm text-muted mb-lg">
          Verify the SHA-256 hash chain integrity of the trade ledger.
          Each record's hash is computed from its content and the previous record's hash,
          making the ledger immutable and tamper-evident.
        </p>

        <Button
          variant="primary"
          onClick={handleVerify}
          disabled={loading}
          className="mb-lg"
        >
          {loading ? (
            <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Verifying...</>
          ) : 'Run Verification'}
        </Button>

        {localError && (
          <div className="alert alert-error mb-lg">
            {localError}
            <button className="alert-close" onClick={() => setLocalError('')}>×</button>
          </div>
        )}

        {result && (
          <div className={`ledger-result ${result.valid ? 'valid' : 'invalid'}`}>
            <div className="ledger-result-header">
              <span className="ledger-result-icon">
                {result.valid ? '✅' : '❌'}
              </span>
              <div className="flex flex-col">
                <h3 className="text-sm font-bold">
                  {result.valid
                    ? 'Ledger Verified: No Tampering Detected'
                    : 'Integrity Violation Detected!'}
                </h3>
                <p className="text-xs text-muted">
                  {result.records_checked} of {result.total_records} records validated
                </p>
              </div>
            </div>

            {!result.valid && result.errors?.length > 0 && (
              <div className="ledger-errors">
                <h4 className="text-xs font-bold text-red mb-sm">
                  Chain broken at record #{result.first_broken_at}:
                </h4>
                <div className="flex flex-col gap-xs">
                  {result.errors.map((err, i) => (
                    <p key={i} className="text-xs text-mono text-red">
                      {err}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
