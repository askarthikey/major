import { useState } from 'react';
import { startSimulation, stopSimulation, stepSimulation, resetSimulation } from '../../services/api';

export default function SimulationControls({ isRunning, currentTimestep, totalTimesteps }) {
  const [speed, setSpeed] = useState(10);
  const [steps, setSteps] = useState(96);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      await startSimulation(steps, speed);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopSimulation();
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  const handleStep = async () => {
    setLoading(true);
    setError(null);
    try {
      await stepSimulation();
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  const handleReset = async () => {
    setLoading(true);
    try {
      await resetSimulation();
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  const progress = totalTimesteps > 0 ? (currentTimestep / totalTimesteps) * 100 : 0;

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">⚙️ Simulation Controls</span>
        {isRunning && (
          <span className="badge executed">
            <div className="pulse-dot" style={{ width: 6, height: 6 }}></div>
            Running
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div style={{
        width: '100%',
        height: 4,
        background: 'var(--bg-tertiary)',
        borderRadius: 'var(--radius-full)',
        marginBottom: 'var(--space-md)',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${progress}%`,
          height: '100%',
          background: 'var(--gradient-primary)',
          borderRadius: 'var(--radius-full)',
          transition: 'width 0.5s ease',
        }} />
      </div>

      <div className="text-xs text-muted mb-md">
        Step {currentTimestep} / {totalTimesteps} ({progress.toFixed(1)}%)
      </div>

      {/* Controls */}
      <div className="flex gap-sm" style={{ flexWrap: 'wrap' }}>
        {!isRunning ? (
          <>
            <button className="btn btn-primary" onClick={handleStart} disabled={loading}>
              ▶ Start
            </button>
            <button className="btn btn-ghost" onClick={handleStep} disabled={loading}>
              ⏭ Step
            </button>
          </>
        ) : (
          <button className="btn btn-danger" onClick={handleStop} disabled={loading}>
            ⏹ Stop
          </button>
        )}
        <button className="btn btn-ghost" onClick={handleReset} disabled={loading || isRunning}>
          🔄 Reset
        </button>
      </div>

      {/* Settings */}
      <div className="flex gap-md mt-md" style={{ flexWrap: 'wrap' }}>
        <div>
          <label className="text-xs text-muted" style={{ display: 'block', marginBottom: 4 }}>
            Timesteps
          </label>
          <input
            type="number"
            value={steps}
            onChange={(e) => setSteps(Number(e.target.value))}
            min={1}
            max={960}
            disabled={isRunning}
            style={{
              width: 80,
              padding: '6px 8px',
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
            }}
          />
        </div>
        <div>
          <label className="text-xs text-muted" style={{ display: 'block', marginBottom: 4 }}>
            Speed (x)
          </label>
          <input
            type="number"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            min={0.1}
            max={100}
            step={0.5}
            disabled={isRunning}
            style={{
              width: 80,
              padding: '6px 8px',
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
            }}
          />
        </div>
      </div>

      {error && (
        <div className="text-xs text-red mt-sm">⚠ {error}</div>
      )}
    </div>
  );
}
