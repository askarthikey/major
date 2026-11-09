# 🔆 GNN-Constrained Peer-to-Peer Solar Microgrid Trading System

> **A solar-power trading app for neighbors, with an AI safety layer making sure no trade accidentally overloads the electrical grid.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://react.dev)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248.svg)](https://mongodb.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-Geometric-EE4C2C.svg)](https://pyg.org)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: Dashboard & Ledger (React + WebSockets + MongoDB)  │
│   - Live trade feed, grid visualization, congestion coloring│
│   - SHA-256 hash-chained tamper-evident trade ledger        │
├─────────────────────────────────────────────────────────────┤
│ LAYER 3: Market Engine (Python / FastAPI)                    │
│   - Double auction: match bids/asks by price                 │
│   - Every matched trade → GNN feasibility gate check         │
├─────────────────────────────────────────────────────────────┤
│ LAYER 2: GNN Feasibility Model + Forecasting (PyTorch)       │
│   - GNN predicts voltage/line-loading impact of trades       │
│   - LSTM forecasts near-term load/solar per household        │
├─────────────────────────────────────────────────────────────┤
│ LAYER 1: Grid Simulation (pandapower)                        │
│   - IEEE 13-bus test feeder with real household profiles      │
│   - Ground-truth power flow solver for GNN training labels   │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
solar-p2p-trading/
├── server/          # Python backend (FastAPI + ML + Grid Sim)
│   ├── config/      # Settings & environment
│   ├── core/        # Layer 1: Grid simulation (pandapower)
│   ├── ml/          # Layer 2: GNN + Forecasting models
│   ├── market/      # Layer 3: Auction engine + feasibility gate
│   ├── ledger/      # MongoDB ledger + hash chain
│   ├── api/         # Layer 4: FastAPI routes + WebSocket
│   ├── data/        # Datasets (gitignored)
│   └── tests/       # Test suite
├── client/          # React + Vite frontend dashboard
├── evaluation/      # Evaluation scripts & benchmarks
└── paper/           # IEEE-format research paper
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11.x (Recommended for stability)
- Node.js 18+
- MongoDB Atlas account (free tier works)

### 1. Clone & Configure
```bash
git clone <repo-url>
cd solar-p2p-trading
cp .env.example .env
# Edit .env with your MongoDB Atlas URI
```

### 2. Backend Setup
```bash
cd server
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd client
npm install
```

### 4. Run Development Servers
```bash
# Terminal 1 — Backend
cd server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd client
npm run dev
```

### 5. Open
- **Dashboard**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs

## 🔬 Core Innovation

Existing P2P energy trading research matches buyers/sellers purely on price, ignoring whether the local grid can physically handle the resulting power flows. This project introduces a **Graph Neural Network (GNN) feasibility gate** that checks every matched trade against grid physics constraints before execution.

The GNN is trained on thousands of pandapower-labeled examples to approximate power flow analysis, running orders of magnitude faster than the full physics solver — making real-time feasibility checking viable in a live trading market.

## 📊 Key Evaluation Metrics
1. **Accuracy**: GNN vs pandapower ground truth (precision/recall/F1, false-negative rate)
2. **Speed**: GNN inference time vs full power flow solve (target: 100-1000x speedup)
3. **Safety**: Naive (no gate) vs GNN-gated market — violations prevented vs economic cost

## 🎯 SDGs
- **SDG 7**: Affordable & Clean Energy
- **SDG 9**: Industry, Innovation & Infrastructure
- **SDG 11**: Sustainable Cities & Communities
- **SDG 13**: Climate Action

---

*Built as a final-year CS project at VNRVJIET Hyderabad.*
