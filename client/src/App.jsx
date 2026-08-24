import { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Layout/Sidebar';
import Header from './components/Layout/Header';
import StatsCards from './components/Dashboard/StatsCards';
import SimulationControls from './components/Dashboard/SimulationControls';
import GridGraph from './components/Grid/GridGraph';
import CongestionPanel from './components/Grid/CongestionPanel';
import TradeFeed from './components/Trading/TradeFeed';
import PriceChart from './components/Trading/PriceChart';
import { useWebSocket } from './hooks/useWebSocket';
import { getSimulationStatus, getGridState, getTradeStats } from './services/api';
import './App.css';

function App() {
  const { isConnected, lastMessage } = useWebSocket();

  // State
  const [simState, setSimState] = useState({
    is_running: false,
    current_timestep: 0,
    total_timesteps: 96,
  });
  const [gridState, setGridState] = useState(null);
  const [trades, setTrades] = useState([]);
  const [priceHistory, setPriceHistory] = useState([]);
  const [stats, setStats] = useState({
    totalEnergyKwh: 0,
    totalTradesExecuted: 0,
    totalTradesRejected: 0,
    violationsPrevented: 0,
    totalRevenue: 0,
    avgPrice: 0,
    gridHealthy: true,
    voltageViolations: 0,
  });
  const [simulationTime, setSimulationTime] = useState(null);

  // Poll simulation status periodically
  const fetchStatus = useCallback(async () => {
    try {
      const status = await getSimulationStatus();
      setSimState(status);
    } catch {
      // Server not available yet — ignore
    }
  }, []);

  // Fetch initial grid state
  const fetchGridState = useCallback(async () => {
    try {
      const state = await getGridState();
      setGridState(state);
    } catch {
      // Ignore
    }
  }, []);

  // Initial data fetch
  useEffect(() => {
    fetchStatus();
    fetchGridState();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchGridState]);

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage || lastMessage.type !== 'simulation_step') return;

    const data = lastMessage.data;

    // Update simulation time
    setSimulationTime(data.simulation_time);

    // Update grid state
    if (data.grid_state) {
      setGridState(data.grid_state);
    }

    // Update trades
    if (data.trades) {
      setTrades(prev => [...data.trades, ...prev].slice(0, 200));
    }

    // Update price history
    if (data.trades?.length > 0) {
      const executedTrades = data.trades.filter(t =>
        t.status === 'executed' || t.status === 'partial_fill'
      );
      if (executedTrades.length > 0) {
        const prices = executedTrades.map(t => t.price || t.price_per_kwh || 0);
        setPriceHistory(prev => [
          ...prev,
          {
            time: data.simulation_time,
            avgPrice: prices.reduce((a, b) => a + b, 0) / prices.length,
            maxPrice: Math.max(...prices),
            minPrice: Math.min(...prices),
          },
        ].slice(-96)); // Keep last 96 points
      }
    }

    // Update aggregate stats
    setStats({
      totalEnergyKwh: data.total_energy_kwh || 0,
      totalTradesExecuted: data.trades_executed || 0,
      totalTradesRejected: data.trades_rejected || 0,
      violationsPrevented: data.violations_prevented || 0,
      totalRevenue: 0,
      avgPrice: 0,
      gridHealthy: data.grid_healthy ?? true,
      voltageViolations: data.grid_state?.num_voltage_violations || 0,
    });

    // Also update sim state from WS
    setSimState(prev => ({
      ...prev,
      is_running: true,
      current_timestep: (data.timestep || 0) + 1,
    }));
  }, [lastMessage]);

  return (
    <div className="app-layout">
      <Sidebar />

      <div className="app-main">
        <Header
          isConnected={isConnected}
          simulationTime={simulationTime}
          isRunning={simState.is_running}
        />

        <div className="app-content">
          <div className="dashboard-grid">
            {/* Stats Overview */}
            <StatsCards stats={stats} />

            {/* Main content grid */}
            <div className="main-grid">
              {/* Left column */}
              <div className="flex flex-col gap-lg">
                <GridGraph gridState={gridState} />
                <PriceChart priceHistory={priceHistory} />
              </div>

              {/* Right column */}
              <div className="flex flex-col gap-lg">
                <SimulationControls
                  isRunning={simState.is_running}
                  currentTimestep={simState.current_timestep}
                  totalTimesteps={simState.total_timesteps}
                />
                <CongestionPanel gridState={gridState} />
                <TradeFeed trades={trades} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
