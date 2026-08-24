# GNN-Constrained Peer-to-Peer Solar Microgrid Trading System
## Master Project Plan (for Claude Code / autonomous agent execution)

**Owner:** Karthikey (ASKarthikey), final-year CS, VNRVJIET Hyderabad
**Duration:** 12 months
**Type:** Final-year project + IEEE-format research paper
**SDGs covered:** SDG 7 (Affordable & Clean Energy), SDG 9 (Industry, Innovation & Infrastructure), SDG 11 (Sustainable Cities & Communities), SDG 13 (Climate Action)

---

## 0. ONE-PARAGRAPH PROJECT SUMMARY (read this first)

Residential solar owners want to sell surplus power directly to neighbors instead of feeding it back to the utility at a low fixed rate. This is "peer-to-peer (P2P) energy trading." The problem: almost all existing P2P trading research matches buyers/sellers purely on price (like an auction/eBay) and completely ignores whether the local electrical grid can physically handle the resulting power flows — a trade that clears economically can overload a line or push a bus voltage out of safe range. This project builds a P2P energy trading marketplace where every matched trade must pass through a **Graph Neural Network (GNN) feasibility gate** before it executes. The GNN is trained to approximate the output of a physics-based power flow solver (pandapower) but runs orders of magnitude faster, making it viable to check every candidate trade in a live market. The system is entirely simulation-based (no real hardware needed): a standard IEEE test feeder + real household load/solar datasets + pandapower for ground truth + PyTorch Geometric for the GNN + a double-auction market engine + a hash-chained tamper-evident ledger + a live React dashboard.

**The one-line pitch:** "A solar-power trading app for neighbors, with an AI safety layer making sure no trade accidentally overloads the electrical grid."

---

## 1. WHY THIS PROJECT (context for the agent — do not skip)

- Novelty claim: existing P2P energy trading literature optimizes economic matching (auctions/game theory) but treats the grid as infinitely capable. This project embeds a learned, fast, grid-physics-aware feasibility check *inside* the trading loop itself — not as an afterthought.
- The GNN is not decorative — it exists because running a full power-flow solve (pandapower) for every candidate trade in a live market is too slow. The GNN is a fast learned approximation of the solver, validated against the solver's own ground truth.
- All training labels for the GNN come from pandapower (a peer-reviewed, industry-standard, physics-based power flow solver) — this is the answer to "how do you trust your dataset." The grid topology comes from an IEEE standard test feeder (the "MNIST of power systems research"). The load/solar time series come from real, published household energy datasets. Nothing about the ground truth is invented; only the *combinations* (candidate trades) are synthetically generated, which is standard practice in this kind of ML research (same pattern used in robotics/self-driving: physics simulator generates ground truth, ML approximates it for speed).
- Keep this framing intact in all code comments, the README, and the paper — it is the core defensibility argument for viva/interview questions.

---

## 2. SYSTEM ARCHITECTURE (4 layers — build in this order)

```
┌──────────────────────────────────────────────────────────────┐
│ LAYER 4: Dashboard & Ledger (React/Vite + WebSockets + MongoDB) │
│   - Live trade feed, grid visualization, congestion coloring  │
│   - SHA-256 hash-chained tamper-evident trade ledger (MongoDB) │
├──────────────────────────────────────────────────────────────┤
│ LAYER 3: Market Engine (Python / FastAPI)                     │
│   - Double auction: match bids/asks by price                  │
│   - Every matched trade → sent to Layer 2 for a feasibility   │
│     check before it is allowed to execute                     │
├──────────────────────────────────────────────────────────────┤
│ LAYER 2: GNN Feasibility Model + Forecasting (PyTorch)        │
│   - GNN predicts voltage/line-loading impact of a candidate   │
│     trade, trained against pandapower ground truth            │
│   - LSTM forecasts each household's near-term load/solar      │
├──────────────────────────────────────────────────────────────┤
│ LAYER 1: Grid Simulation (pandapower)                         │
│   - IEEE 13-bus or 34-bus test feeder                         │
│   - Real household load + solar profiles attached to buses    │
│   - Ground-truth power flow solver (used to generate all      │
│     GNN training labels and to validate the GNN's accuracy)   │
└──────────────────────────────────────────────────────────────┘
```

Build bottom-up: Layer 1 must be solid before Layer 2 can be trained; Layer 2 must produce a trustworthy feasibility signal before Layer 3 can gate on it; Layer 3 must work before Layer 4 has anything real to visualize.

---

## 3. TECH STACK (pin these versions when scaffolding, adjust only if install fails)

| Purpose | Tool | Notes |
|---|---|---|
| Grid simulation / power flow ground truth | `pandapower` (Python) | Easier to integrate with Python ML stack than OpenDSS |
| GNN | `PyTorch` + `PyTorch Geometric (PyG)` | GraphSAGE or GAT layers |
| Forecasting | `PyTorch` (LSTM) or `statsmodels` (baseline) | Keep a non-ML baseline (naive persistence / moving average) to prove the LSTM adds value |
| Backend / API | `FastAPI` | One language (Python) across ML + backend saves huge time |
| Market engine | Plain Python, event-driven loop | No need for a separate library — implement double auction directly |
| Database / Ledger | `MongoDB Atlas` (async via `Motor`) + SHA-256 hash chain (custom, ~50 lines) | Flexible document schema fits heterogeneous grid/trade data; do NOT use real blockchain — adds infra complexity with zero research value |
| Real-time updates | `WebSockets` (native FastAPI support) | Pushes live trade/grid state to dashboard |
| Frontend | `React` (Vite) + `D3.js` (grid graph viz) + `Recharts` (price/trend charts) | Vite for fast HMR, React 18+ |
| Data processing | `pandas`, `numpy`, `scikit-learn` | |
| Configuration | `pydantic-settings` + `.env` file | Centralized config via environment variables |
| Experiment tracking | `Weights & Biases` (optional but recommended) or plain CSV logging | For GNN training runs, ablations |
| Environment | Python 3.10+, `pip` + `venv`; Node 18+ for frontend | Local dev, MongoDB Atlas cloud |

---

## 4. REPOSITORY STRUCTURE (scaffold this first)

```
solar-p2p-trading/
├── README.md
├── plan.md                              <- this file
├── .env.example                         <- environment variable template
├── .gitignore
│
├── server/                              ← Python backend (FastAPI + ML + Grid Sim)
│   ├── requirements.txt
│   ├── config/
│   │   └── settings.py                  <- Pydantic settings, loads from .env
│   │
│   ├── core/                            <- Layer 1: Grid Simulation
│   │   ├── feeder_setup.py              <- IEEE 13-bus network in pandapower
│   │   ├── attach_profiles.py           <- attach load/solar data to buses
│   │   ├── run_powerflow.py             <- wrapper around pandapower solve
│   │   └── trade_simulator.py           <- generates random candidate trades + ground-truth labels
│   │
│   ├── ml/                              <- Layer 2: GNN + Forecasting
│   │   ├── gnn/
│   │   │   ├── model.py                 <- GraphSAGE/GAT feasibility model
│   │   │   ├── train.py
│   │   │   ├── evaluate.py
│   │   │   ├── inference.py             <- Fast inference wrapper for production
│   │   │   └── baseline_mlp.py          <- non-graph baseline for ablation
│   │   ├── forecasting/
│   │   │   ├── lstm_model.py
│   │   │   ├── train.py
│   │   │   └── baseline_naive.py
│   │   └── utils/
│   │       ├── graph_features.py        <- node/edge feature engineering for PyG
│   │       └── data_loader.py           <- dataset-agnostic loader
│   │
│   ├── market/                          <- Layer 3: Market Engine
│   │   ├── auction_engine.py            <- double auction with heap-based order books
│   │   ├── feasibility_gate.py          <- calls GNN, decides execute/reject/partial-fill
│   │   └── simulation_loop.py           <- orchestrates full trading timesteps
│   │
│   ├── ledger/                          <- MongoDB ledger + hash chain
│   │   ├── database.py                  <- Motor async MongoDB connection
│   │   ├── models.py                    <- Pydantic document schemas
│   │   └── hash_chain.py               <- SHA-256 tamper-evident chain
│   │
│   ├── api/                             <- Layer 4: FastAPI backend
│   │   ├── main.py                      <- FastAPI app entry point
│   │   ├── schemas.py                   <- Request/response schemas
│   │   ├── middleware.py                <- CORS, error handling
│   │   └── routes/
│   │       ├── trades.py                <- Trade CRUD + chain verification
│   │       ├── grid_state.py            <- Grid topology + state
│   │       ├── simulation.py            <- Simulation control
│   │       └── websocket.py             <- WebSocket live feed
│   │
│   ├── data/
│   │   ├── raw/                         <- downloaded datasets (gitignored)
│   │   ├── processed/                   <- cleaned load/solar profiles
│   │   └── synthetic_trades/            <- generated GNN training data
│   │
│   └── tests/
│       ├── test_grid_sim.py
│       ├── test_market.py
│       └── test_ledger.py
│
├── client/                              ← React + Vite frontend dashboard
│   ├── package.json
│   ├── vite.config.js                   <- Dev proxy to FastAPI backend
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                      <- Main dashboard with WebSocket state
│       ├── index.css                    <- Dark-mode design system
│       ├── hooks/
│       │   └── useWebSocket.js          <- WebSocket connection hook
│       ├── services/
│       │   └── api.js                   <- API client
│       ├── utils/
│       │   └── formatters.js            <- Display formatters
│       └── components/
│           ├── Layout/
│           │   ├── Sidebar.jsx
│           │   └── Header.jsx
│           ├── Dashboard/
│           │   ├── StatsCards.jsx        <- Key metrics overview
│           │   └── SimulationControls.jsx
│           ├── Grid/
│           │   ├── GridGraph.jsx         <- D3 force-directed grid visualization
│           │   └── CongestionPanel.jsx   <- Line loading, violations
│           └── Trading/
│               ├── TradeFeed.jsx         <- Live trade feed
│               └── PriceChart.jsx        <- Recharts price history
│
├── evaluation/
│   ├── accuracy_report.py               <- GNN vs pandapower ground truth
│   ├── speed_benchmark.py               <- GNN inference time vs full power flow solve
│   ├── naive_vs_gated_comparison.py     <- THE headline experiment
│   └── figures/
│
└── paper/
    ├── main.tex
    ├── sections/
    └── figures/
```

---

## 5. DATASETS — EXACT SOURCES, ACCESS PLAN, AND FALLBACKS

Do this in **Week 1**, before writing any code, because dataset access approval can take time.

### 5.1 Grid topology (ground truth network structure)
- **Primary:** IEEE 13-Bus Test Feeder (small, fast to iterate on) — built directly into pandapower via `pandapower.networks.case13()` equivalent or manually defined per IEEE spec.
- **Scale-up option (month 5+):** IEEE 34-Bus Test Feeder for a more complex topology once the pipeline works on 13-bus.
- No download needed — pandapower has these as importable standard networks or they can be defined from published IEEE specs (search "IEEE 13 node test feeder data" for the standard line/load parameters).

### 5.2 Household load + solar generation profiles
- **Primary:** Pecan Street Dataport (residential solar + load, 1-minute resolution, widely cited in energy ML research).
  - Action item: apply for academic dataset access at dataport.pecanstreet.org **in Week 1**. Approval can take days to weeks — do not wait to start other work while this is pending.
- **Fallback (use immediately, don't block on Pecan Street approval):** UK-DALE or REFIT datasets — publicly downloadable without approval delay, household-level load data (REFIT also has some solar-relevant sites). Use these to get the pipeline fully working; swap in Pecan Street data later if/when access comes through — document both in the paper regardless (comparing generalization across datasets is a free bonus result).
- **Weather/irradiance data (for solar generation modeling):** NASA POWER API (free, no approval needed, global solar irradiance data) or OpenWeatherMap free tier.

### 5.3 GNN training data (candidate trades + safety labels)
- **This is generated by you, not downloaded.** See Section 7 (Data Generation Pipeline) for exact method. This is expected and standard practice — document it clearly as "synthetically generated via a validated physics simulator," not as a limitation to hide.

### 5.4 Dataset risk mitigation
- Do not let Pecan Street approval block Week 1-2 work. Start immediately with REFIT/UK-DALE, structure the data loader (`ml/utils/data_loader.py`) to be dataset-agnostic (a common schema: `timestamp, household_id, load_kw, solar_kw`) so swapping datasets later is a config change, not a rewrite.

---

## 6. PHASE-BY-PHASE ROADMAP (12 months, with weekly granularity for months 1-2)

### PHASE 0 — Setup (Week 1)
- [ ] Scaffold repo structure exactly as in Section 4.
- [ ] Set up Python virtual environment, install pandapower, PyTorch, PyTorch Geometric, FastAPI.
- [ ] Apply for Pecan Street academic access (don't block on this).
- [ ] Download REFIT or UK-DALE as immediate fallback dataset.
- [ ] Read pandapower documentation quickstart; run the built-in example network to confirm the install works.
- [ ] Begin literature review in parallel (target: 15-20 papers on P2P energy trading + grid-aware trading + GNNs for power systems, to sharpen the exact novelty gap and build the related-work section later). Log each paper's core claim and how this project differs, in `paper/related_work_notes.md`.

### PHASE 1 — Grid Simulation Foundation (Weeks 2-6 / Months 1-2)
- [ ] `grid_sim/feeder_setup.py`: build the IEEE 13-bus network in pandapower — define buses, lines, transformer, line thermal ratings, voltage limits (±5%).
- [ ] `grid_sim/attach_profiles.py`: map cleaned household load/solar time series onto specific buses in the feeder (some buses = houses with solar, some = houses without, per realistic distribution).
- [ ] `grid_sim/run_powerflow.py`: wrapper function `solve_power_flow(net) -> {bus: voltage, line: loading_pct}`. Confirm it runs and converges on realistic load values.
- [ ] Sanity-test: manually construct a few known "obviously unsafe" scenarios (e.g., dump maximum possible load on one bus) and confirm pandapower correctly flags voltage/thermal violations. Write this as `tests/test_grid_sim.py`.
- [ ] Milestone check: can you solve power flow for the 13-bus feeder with real attached household data and get correct voltage/loading numbers in under 1 second per solve? If not, debug before moving on — everything downstream depends on this being correct.

### PHASE 2 — Data Generation Pipeline for GNN Training (Weeks 7-10 / Months 3-4)
See Section 7 for full detail. Deliverable: `data/synthetic_trades/` containing tens of thousands of labeled (grid_state, candidate_trade) → (feasible/infeasible, voltage_deltas, loading_deltas) examples.
- [ ] `grid_sim/trade_simulator.py`: generate random candidate trades (random buyer-seller pairs, random kWh amounts) at random timesteps.
- [ ] For each candidate trade: apply it to the grid state, run `run_powerflow.py`, record whether any bus/line violated limits, and by how much.
- [ ] Generate at minimum ~20,000-50,000 labeled examples across varied times of day, seasons (if data allows), and load conditions — more is better, but don't over-invest here at the expense of Phase 3; this pipeline can keep generating data in the background while you build the model.
- [ ] Save as a structured format (Parquet or a graph-native format compatible with PyG's `Data` objects) in `data/synthetic_trades/`.
- [ ] Milestone check: inspect class balance (feasible vs infeasible) — if wildly imbalanced (e.g., 99% feasible because the feeder is oversized for typical loads), deliberately oversample high-load/high-injection scenarios so the GNN has enough infeasible examples to learn from.

### PHASE 3 — GNN Feasibility Model (Weeks 11-16 / Months 5-6)
See Section 8 for full architecture detail.
- [ ] `ml/utils/graph_features.py`: build node features (voltage, net injection, bus type) and edge features (impedance, thermal rating, current loading) from a grid state.
- [ ] `ml/gnn/model.py`: implement the GNN — start with GraphSAGE (simpler), then try GAT (attention-based, gives interpretable "which neighbor mattered" weights — useful for damage/violation localization explanations).
- [ ] `ml/gnn/baseline_mlp.py`: implement a non-graph MLP baseline with the same inputs flattened — this is REQUIRED for your key ablation ("does the graph structure actually help").
- [ ] `ml/gnn/train.py`: training loop, train/val/test split (split by time period, not randomly, to avoid leakage — e.g., train on months 1-8 of data, validate on month 9, test on months 10-12).
- [ ] `ml/gnn/evaluate.py`: compute precision/recall/F1 on infeasible-trade detection, with special attention to **false negatives** (model says "safe" when it's actually unsafe) — this is the dangerous error type and must be reported separately and minimized (consider a class-weighted loss or a decision threshold biased toward caution).
- [ ] Decide classification vs regression output (Section 8 discusses both — regression, i.e. predicting actual voltage/loading values rather than just a binary flag, is the stronger paper contribution if time allows).
- [ ] Milestone check: GNN should clearly outperform the MLP baseline on infeasible-trade detection. If it doesn't, investigate feature engineering or graph construction before proceeding — this comparison IS your core novelty claim, it cannot be skipped or fudged.

### PHASE 4 — Forecasting + Market Mechanism (Weeks 17-20 / Months 7-8)
- [ ] `ml/forecasting/lstm_model.py`: per-household short-term (15min-1hr ahead) load and solar generation forecast.
- [ ] `ml/forecasting/baseline_naive.py`: naive persistence baseline (tomorrow = today) — required comparison, keep forecasting claims honest and modest, this is NOT your novel contribution, just solid supporting engineering.
- [ ] `market/auction_engine.py`: implement continuous double auction — sellers post asks, buyers post bids, match when bid ≥ ask, clear at midpoint price (document this convention clearly in code comments and paper).
- [ ] `market/feasibility_gate.py`: wraps the trained GNN — takes a matched candidate trade + current grid state, returns feasible / infeasible / partial-fill-amount. Implement the partial-fill option (reduce trade quantity until feasible) — this is a cheap, high-value extra novelty point, don't skip it.
- [ ] `market/simulation_loop.py`: orchestrates a full simulated trading day — for each timestep: get forecasts → households submit bids/asks → auction matches → feasibility gate checks → execute or adjust → log to ledger.
- [ ] Milestone check: run a full simulated day end-to-end and manually inspect the trade log for sanity (are prices reasonable, are rejected trades actually the ones that should be rejected).

### PHASE 5 — Ledger + Backend Integration (Week 21 / Month 9)
- [ ] `server/ledger/database.py`: MongoDB Atlas connection via Motor (async driver), collection initialization with indexes.
- [ ] `server/ledger/models.py`: Pydantic document schemas — `TradeRecord` (trade_id, buyer, seller, amount_kwh, price, timestamp, status, feasibility result, prev_hash, this_hash), `GridSnapshot`, `HouseholdProfile`, `SimulationState`.
- [ ] `server/ledger/hash_chain.py`: SHA-256 of each document's content + previous document's hash, appended on every trade — gives tamper-evidence without real blockchain overhead.
- [ ] `server/api/main.py` + `routes/`: FastAPI endpoints — `GET /api/grid/state`, `GET /api/trades`, `POST /api/simulation/step`, `POST /api/simulation/start`, `WS /ws/live` for WebSocket push of live updates.
- [ ] Milestone check: hit the API endpoints manually (via `curl` or FastAPI's auto-generated `/docs`) and confirm trade data and grid state are being served correctly and the hash chain is verifiably unbroken (`GET /api/trades/verify-chain` walks the chain and confirms no tampering).

### PHASE 6 — Frontend Dashboard (Week 22-24 / Month 10)
- [ ] `client/src/components/Grid/GridGraph.jsx`: D3.js fixed-layout graph of the feeder topology, nodes color-coded by voltage status (green/yellow/red), edges color-coded by line loading %, glow effects on violations.
- [ ] `client/src/components/Trading/TradeFeed.jsx`: live-scrolling feed of executed/rejected/partial-fill trades (via WebSocket).
- [ ] `client/src/components/Trading/PriceChart.jsx`: price-over-time area chart (Recharts) showing market clearing prices with gradient fill.
- [ ] `client/src/components/Grid/CongestionPanel.jsx`: summary panel — line loading progress bars, max voltage deviation, active violation alerts.
- [ ] `client/src/components/Dashboard/SimulationControls.jsx`: start/stop/step/reset controls with progress bar and speed settings.
- [ ] `client/src/components/Dashboard/StatsCards.jsx`: key metrics overview — energy traded, violations prevented, revenue, grid health.
- [ ] Wire up WebSocket connection via `useWebSocket` hook in `App.jsx` for live updates as the simulation loop runs. Dark-mode glassmorphism design with energy-themed color palette.
- [ ] Milestone check: open the dashboard at `http://localhost:5173`, start the simulation loop, and watch trades clear and the grid graph update live — this is your demo centerpiece, make sure it actually looks good, not just functionally correct.

### PHASE 7 — Full Evaluation Suite (Week 25-27 / Month 11)
See Section 9 for full evaluation detail. This is where your paper's actual results come from.
- [ ] `evaluation/accuracy_report.py`: GNN vs pandapower ground truth — precision/recall/F1, with false-negative rate highlighted separately.
- [ ] `evaluation/speed_benchmark.py`: GNN inference time vs. full pandapower solve time, averaged over many trades — report the speedup factor (expect somewhere in the 100-1000x range, but measure honestly, don't assume).
- [ ] `evaluation/naive_vs_gated_comparison.py`: **the headline experiment.** Run the same simulated trading session twice — once with naive economic-only matching (no feasibility gate), once with your GNN-gated version. Count and report: (a) how many line overloads/voltage violations the naive version causes, (b) how many your gated version prevents, (c) the economic efficiency cost (total trade value or number of trades reduced/blocked) of adding the safety gate. This three-part comparison is your single most important figure/table in the paper.
- [ ] Run all comparisons at both 13-bus and (if time allows) 34-bus scale to show the approach generalizes to a larger topology.
- [ ] Milestone check: do you have a clean, defensible number for "the naive approach caused X violations our approach prevented, at an efficiency cost of Y%"? If not, this is the single thing to fix before writing the paper — everything else is secondary to this result.

### PHASE 8 — Paper Writing + Final Polish (Week 28-30+ / Month 12)
- [ ] Write in IEEE conference paper format (reuse existing LaTeX template/muscle memory from prior work).
- [ ] Structure: Abstract → Introduction (the "grid physics is ignored" gap) → Related Work (from `paper/related_work_notes.md`) → System Architecture (Sections 2 here) → GNN Methodology (Section 8) → Market Mechanism → Evaluation (Section 9's three results) → Discussion/Limitations (be explicit: simulation-only, standard test feeder, synthetic trade generation — frame these as scoped, not hidden) → Conclusion.
- [ ] Record a short demo video of the live dashboard for presentation/portfolio use.
- [ ] Final code cleanup, README polish, ensure repo is presentable for interview/GitHub portfolio purposes.

---

## 7. DATA GENERATION PIPELINE — EXACT METHOD (critical section, read carefully)

This is the answer to "how do you trust your dataset" (already field-tested with the supervisor) — implement it exactly this way so the reasoning holds up.

**Step-by-step:**
1. Load the IEEE feeder topology (Section 5.1) with real household load/solar profiles attached (Section 5.2) for a given timestep.
2. Randomly sample a candidate trade: pick a buyer bus and seller bus (constrained to buses that are actually solar-owning for sellers), and a random trade amount (kWh) within a plausible range (e.g., 0 to the seller's current surplus).
3. Apply the trade to the grid state: reduce net injection at the seller bus by the trade amount, increase net draw reduction at the buyer bus by the trade amount (i.e., simulate the actual physical effect of the transaction on power flows).
4. Run `run_powerflow.py` (pandapower) on this modified grid state — this is the **ground truth**, computed from real load-flow physics equations, not guessed.
5. Record the label: feasible (all voltages within ±5%, all lines under thermal rating) or infeasible, plus the actual voltage/loading values at every bus/line (needed if going the regression route).
6. Repeat steps 2-5 thousands of times across many timesteps (different times of day/load conditions) to build the full training set.
7. Explicitly oversample edge-case scenarios (high load + high trade volume) so the model sees enough infeasible examples — natural random sampling on an appropriately-sized feeder will likely skew heavily "feasible," and an imbalanced dataset will produce an over-confident model with poor infeasible-case recall.

**Why this is trustworthy (for viva/interview defense):** every label comes from pandapower's physics solver, which is peer-reviewed, community-validated, and based on the same load-flow equations utilities use in real operations. The only synthetic part is *which combinations* of trades are being tested — the *evaluation* of each combination is 100% real physics, not a guess. This is the same paradigm used in robotics/self-driving ML (physics simulator generates ground truth at scale; ML model learns to approximate it fast) — an accepted, standard approach for exactly this reason: you cannot ethically or practically collect real-world "this trade damaged the grid" examples at scale.

---

## 8. GNN MODEL — ARCHITECTURE DETAIL

**Input representation (per candidate check):**
- Graph = the feeder topology.
- Node features: current voltage (pre-trade), net power injection/draw, bus type (has-solar / no-solar), and the proposed trade's effect at that node (0 if not involved in this trade, ± trade amount if it is buyer/seller).
- Edge features: line impedance, thermal rating, current loading % (pre-trade).

**Architecture (start here, iterate):**
- 2-3 layer GraphSAGE (simpler, faster to get working) → then try GAT (Graph Attention Network) as a second version, since attention weights double as an interpretability tool ("which neighboring bus most influenced this prediction" — nice for both the paper's discussion section and potential violation-localization framing).
- Output head — pick one, note the tradeoff in the paper:
  - **Classification (simpler, safer MVP):** binary feasible/infeasible per candidate trade.
  - **Regression (stronger novelty, do this if time allows):** predict continuous voltage deviation and line loading % increase per node/edge — gives the market engine a *margin* to work with (how much headroom is left), not just a yes/no, enabling smarter partial-fill decisions in Phase 4's `feasibility_gate.py`.

**Loss function:** if classification, use class-weighted binary cross-entropy (weight the infeasible class higher, since false negatives — approving something actually unsafe — are the costly error type). If regression, MSE on voltage/loading values, but ALSO report a derived classification accuracy (threshold the regression output) so you can compute the same precision/recall/false-negative metrics either way.

**Required baseline comparison (do not skip):** a plain MLP with the same features flattened into a single vector (no graph structure). The entire "why GNN" argument rests on beating this baseline on infeasible-trade detection, especially recall. Report this comparison prominently in the paper.

---

## 9. EVALUATION PLAN — THE THREE RESULTS THAT MATTER MOST

1. **Accuracy vs. ground truth:** precision / recall / F1 of the GNN on infeasible-trade detection, on a held-out (time-split) test set, compared against the MLP baseline. Report false-negative rate separately and prominently — this is the safety-critical error type.
2. **Speed:** average inference time of the GNN vs. average time to run a full pandapower power flow solve, for the same candidate trade. Report the speedup factor. This is your practical justification for using ML at all instead of just always running the real solver.
3. **Naive vs. gated market outcome comparison (the headline result):** run identical simulated trading sessions with and without the feasibility gate. Report (a) number of grid violations the naive version causes, (b) number your gated version prevents, (c) the economic efficiency cost (trades blocked/reduced, total trade value lost) of adding the gate. This is the single figure/table that makes the whole paper's motivation concrete and convincing — prioritize getting this result clean over any other polish.

Optional bonus experiments if time allows: scale test (13-bus vs 34-bus), partial-fill vs. hard-reject comparison (does allowing partial fills recover most of the economic value lost to hard rejection), regression vs. classification output head comparison.

---

## 10. RISKS AND MITIGATIONS (check this list at each phase transition)

| Risk | Mitigation |
|---|---|
| Pecan Street access delayed/denied | Start immediately with REFIT/UK-DALE (public, no approval needed); keep data loader dataset-agnostic so switching later is trivial |
| pandapower / power systems learning curve eats into Month 1 | Budget Week 1 explicitly for this; run the library's own tutorial examples before writing custom code; don't skip the sanity-test step in Phase 1 |
| GNN doesn't beat the MLP baseline | Always run the baseline in parallel, never as an afterthought; if it doesn't beat it, that is itself a reportable (if less flashy) finding — investigate feature engineering before assuming the graph structure isn't helping |
| Class imbalance (mostly-feasible trades) makes the model overconfident | Deliberately oversample high-load/high-trade-volume scenarios during data generation (Section 7, step 7); use class-weighted loss |
| Scope creep across 4 subsystems (GNN, forecasting, market, dashboard) | Follow the phase order strictly; timebox each phase; forecasting and dashboard are supporting engineering, not the novelty — do not let them balloon past their allotted weeks at the expense of Phase 3 (GNN) and Phase 7 (evaluation) |
| Reviewer/supervisor asks "isn't this already solved by SCADA/DERMS/net metering" | Prepared answer: those are centralized, utility-controlled systems; this project is about decentralized peer-to-peer trades, which removes the utility's built-in safety oversight — the GNN feasibility gate rebuilds that safety function for a decentralized context |
| "How do you trust your dataset" | Prepared answer: standard IEEE test feeder (community-standard topology) + real household load/solar data (Pecan Street/REFIT) + pandapower (peer-reviewed physics solver) generates all ground-truth labels; only the trade *combinations* are synthetic, which is standard and necessary practice since real-world "damaged the grid" examples cannot ethically be collected at scale |
| Entire project is simulation-only, no real deployment | Be upfront about this as a stated scope limitation in the paper's limitations section, not something to hide — frame the contribution as a validated method + system prototype, not a claimed real-world deployment |

---

## 11. SDG MAPPING (for report/paper framing)

- **SDG 7 (Affordable & Clean Energy):** enables better utilization of existing rooftop solar generation and fairer pricing for both producers and consumers of clean energy.
- **SDG 13 (Climate Action):** every unit of solar used locally instead of wasted, and every incentive that encourages more solar adoption, is a small emissions-reduction contribution.
- **SDG 11 (Sustainable Cities & Communities):** the feasibility-gate system is a piece of smart, resilient local energy infrastructure that improves grid efficiency without requiring physical rebuilding.
- **SDG 9 (Industry, Innovation & Infrastructure):** the GNN-based feasibility system is genuinely novel deployable infrastructure for a problem (grid-aware decentralized energy markets) that doesn't yet have a standard solution.
- (Optional secondary framing: SDG 12, Responsible Consumption and Production, via reduced wasted solar generation and better supply-demand matching — mention only if a 5th SDG is specifically requested, keep the headline pitch to the 4 above.)

---

## 12. PREPARED ANSWERS FOR SUPERVISOR / VIVA QUESTIONS (keep these handy)

**"Don't power systems already manage extra power?"**
Existing systems (net metering, SCADA, DERMS) manage surplus power centrally — the utility decides what happens and sits in the middle of every transaction, usually paying producers a low fixed feed-in rate. This project decentralizes the transaction into direct trades between neighbors at a mutually negotiated price — genuinely new economically. But decentralizing removes the utility's built-in safety oversight, which is exactly the gap the GNN feasibility layer fills: it rebuilds grid-safety checking for a context where trades happen directly between individuals instead of through a centrally-monitored utility.

**"How do you check for safety?"**
Two physical limits matter: bus voltage must stay within ±5% of standard, and line current must stay under thermal rating. Traditionally checked via power flow analysis (solving Kirchhoff's-law-based equations) — accurate but too slow to run for every candidate trade in a live market. The GNN is trained on thousands of pandapower-labeled examples to approximate this check almost instantly, validated against the real solver's output on held-out data, with false negatives (unsafe trades predicted safe) tracked and minimized as the priority error type.

**"How can you be sure of the dataset?"**
Grid topology = standard IEEE test feeder (community-accepted benchmark). Load/solar data = real measured household data from Pecan Street/REFIT. GNN training labels = generated by applying the real pandapower physics solver to thousands of simulated trade combinations — the ground truth itself is never guessed, only which combinations get tested is synthetic, which is standard, necessary practice in this kind of safety-critical ML research (identical in spirit to how self-driving/robotics models are trained on simulator-generated ground truth). Stated limitation: results are validated on this specific standard topology and dataset, not claimed to generalize identically to every real-world grid — this is disclosed explicitly, not hidden.

---

## 13. DEFINITION OF DONE (final checklist before calling the project complete)

- [ ] GNN clearly outperforms MLP baseline on infeasible-trade detection (precision/recall/F1 reported, false-negative rate highlighted)
- [ ] Speed benchmark shows GNN inference is meaningfully faster than full pandapower solve (with an honest measured number, not an assumed one)
- [ ] Naive-vs-gated comparison experiment produces a clean, defensible result (violations prevented vs. economic cost)
- [ ] Full pipeline runs end-to-end: forecasting → bidding → auction matching → GNN feasibility gate → execution/partial-fill/rejection → ledger → live dashboard
- [ ] Ledger hash chain is verifiably tamper-evident (walk-the-chain verification script passes)
- [ ] Dashboard runs live, shows real trades clearing and grid state updating in real time
- [ ] IEEE-format paper draft complete with all evaluation results and an honest limitations section
- [ ] README is complete enough that someone unfamiliar with the project could set it up and run it from scratch
- [ ] Prepared answers (Section 12) are internalized, not just written down

---

*End of plan. Work through phases in order; do not skip the milestone checks — each one exists because a downstream phase silently breaks if the upstream one is wrong.*
