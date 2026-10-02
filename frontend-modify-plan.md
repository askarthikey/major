# Frontend Implementation Prompt — P2P Solar Microgrid Trading Platform

**Context for the agent:** This document specifies a **frontend rebuild** plus the **backend additions needed to support it** — role-based auth, a map-based bidding UI for sellers/buyers, and an admin monitoring dashboard. Treat this as the authoritative spec; where it conflicts with earlier planning docs on frontend scope, this document wins.

---

## 0. High-level summary of what you're building

Three logged-in experiences on one React app:
1. **Seller** — sees their house on a grid map, sees their current surplus/deficit, sets an asking price, watches buyer bids come in, accepts/negotiates, and sees the GNN feasibility outcome before a trade is finalized.
2. **Buyer** — sees the same grid map, sees which houses have surplus to sell and at what price, places bids, and sees the GNN feasibility outcome before a trade is finalized.
3. **Admin (substation operator)** — sees a state-of-the-grid map (voltage/loading per bus/line, color-coded), a live/historical feed of every trade between every buyer and seller, and aggregate stats (number of trades, feasibility pass/partial/reject rates, total energy traded, etc.).

---

## 1. Roles and Authentication

### 1.1 Roles
Exactly three roles: `seller`, `buyer`, `admin`. A single user account has exactly one role (do not build multi-role accounts — keep this simple).

### 1.2 Auth requirements
* [ ] Email + password auth (use FastAPI's standard JWT pattern — `python-jose` or `fastapi-users` if you want to move faster, either is fine, pick one and be consistent).
* [ ] Signup form collects: name, email, password, role (`seller`/`buyer` — admin accounts are NOT self-service, see 1.3), and for sellers/buyers a `bus_id` (which bus/house on the grid they represent — must match one of the `bus_mapping.json` entries from Phase 2 of `tasks.md`).
* [ ] Login returns a JWT; store it in an httpOnly cookie or localStorage (httpOnly cookie preferred for security, but localStorage is acceptable to keep scope manageable — pick one and document the choice).
* [ ] Every protected API route checks the JWT and the role. A buyer hitting a seller-only endpoint (or vice versa) gets a 403, not a silent failure.
* [ ] Route guarding on the frontend: unauthenticated users get redirected to `/login`; authenticated users get redirected to their role's home page (`/seller`, `/buyer`, or `/admin`) — a buyer should not be able to navigate to `/seller` even by typing the URL.

### 1.3 Admin account creation
Admins are not self-service. Seed exactly one admin account via a backend script (`scripts/create_admin.py` or similar) that takes email/password as CLI args. Document this command in the README. Do not build an admin-signup UI. use "apoorvaadmin" as username / "apoorvaadmin@email.com" for email/ apoorvaadmin as pass or similar kind of credentials for default access

### 1.4 New backend tables needed
* `users`: `id, name, email, password_hash, role, bus_id (nullable for admin), created_at`
* Extend the existing `trades` ledger table (from Phase 6 of `tasks.md`) with `buyer_user_id` and `seller_user_id` foreign keys, if it doesn't already reference users — trades currently reference bus IDs, and you now need to resolve bus IDs to actual logged-in accounts.

---

## 2. Data model additions (backend)

Beyond what already exists (grid state, GNN model, ledger), add:

### 2.1 `listings` table (a seller's current ask)
`id, seller_user_id, bus_id, amount_kwh_available, asking_price_per_kwh, status (open/partially_filled/closed), created_at, updated_at`

### 2.2 `bids` table (a buyer's offer against a listing)
`id, listing_id, buyer_user_id, bus_id, requested_amount_kwh, offered_price_per_kwh, status (pending/accepted/rejected/feasibility_partial/feasibility_rejected), created_at`

### 2.3 Endpoints to add (extend `backend/routes/`)
* `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`
* `GET /grid/state` — already exists per Phase 2/7 of `tasks.md`; confirm it returns per-bus voltage and per-line loading, and extend it to also flag each bus as `has_deficit` / `has_surplus` based on the latest forecasted or actual load-vs-solar-generation delta for that bus (this is what the seller/buyer map needs to render).
* `GET /listings` — all open listings (for buyers' map view), `POST /listings` (seller creates), `PATCH /listings/{id}` (seller updates price/closes it)
* `POST /bids` — buyer places a bid against a listing
* `POST /bids/{id}/respond` — seller accepts or rejects a bid (accept triggers the feasibility-check + trade-execution flow from Phase 5 of `tasks.md`)
* `GET /trades/mine` — a buyer or seller's own trade history
* `GET /trades/all` — admin only, every trade in the system
* `GET /admin/stats` — admin only: total trades, feasibility pass/partial/reject counts, total energy traded, active listings count, etc.

### 2.4 Wiring the feasibility check into bid acceptance
When a seller accepts a bid (`POST /bids/{id}/respond` with `accept`):
1. Build the candidate trade (seller bus, buyer bus, agreed amount) exactly as `market/feasibility_gate.py` expects (see Phase 5 of `tasks.md`).
2. Run it through the trained GNN.
3. If feasible: execute the trade, append to the ledger (Phase 6), mark the bid `accepted`, mark the listing `closed` or `partially_filled` depending on remaining amount.
4. If infeasible but partial-fill finds a smaller feasible amount: mark the bid `feasibility_partial`, return the reduced amount to the frontend so the seller/buyer can be shown "only X kWh of your Y kWh trade could go through, here's why" — do not silently execute a smaller trade without telling both parties what happened.
5. If fully infeasible: mark the bid `feasibility_rejected`, execute nothing, and surface the reason (which bus/line would be violated) back to the frontend so the rejection isn't a black box.
6. Every one of these three outcomes must produce a ledger entry (Phase 6's hash chain) even for rejections — you want a full audit trail of attempted trades, not just successful ones, since this is exactly what the admin dashboard needs to show.

---

## 3. Frontend architecture

* Routing: `react-router-dom`. Top-level routes: `/login`, `/signup`, `/seller/*`, `/buyer/*`, `/admin/*`.
* State: React Context for auth (current user + JWT), plus local component state / a small data-fetching library (`@tanstack/react-query` recommended — it will save you a lot of manual WebSocket-vs-fetch juggling) for listings/bids/trades.
* Keep the existing `GridGraph.jsx` (D3-based grid visualization from Phase 8) as the base and extend it rather than building a new map component from scratch — the seller, buyer, and admin views all need a similar underlying grid visualization, just with different overlays.
* WebSocket connection (`ws://.../live`, already built in Phase 7) should push: new listings, new bids, bid status changes, and grid-state updates — all three role views should update live without a manual refresh.

---

## 4. Seller experience (`/seller`)

### 4.1 Seller home page — the grid map
* Render the feeder topology (reuse `GridGraph.jsx`) with every house/bus visible.
* The seller's own bus is visually highlighted (e.g., a distinct border or icon).
* Every bus is color-coded or icon-tagged by `has_deficit` / `has_surplus` (from the extended `GET /grid/state` endpoint) — sellers should be able to see at a glance which neighboring houses need power, since that's who they're potentially selling to.
* Clicking the seller's own house opens a side panel showing: current forecasted surplus (kWh available to sell), any existing open listing, and a form to create/update a listing (amount + price).

### 4.2 Managing a listing
* Form: `amount_kwh_available` (pre-filled with current forecasted surplus, editable up to that max), `asking_price_per_kwh`.
* Submitting calls `POST /listings` or `PATCH /listings/{id}` if one already exists.
* Show the listing's current status (open / partially filled / closed) and any pending bids against it.

### 4.3 Handling incoming bids
* A list (not just the map) of pending bids against the seller's listing(s): buyer name/bus, requested amount, offered price, timestamp.
* Each pending bid has Accept / Reject buttons.
* On Accept: show a loading state while the feasibility check runs (this hits the backend flow in 2.4), then show the result clearly:
  - **Full success:** "Trade executed: X kWh to [buyer] at $Y/kWh. Grid check passed."
  - **Partial:** "Only X of Y kWh could be delivered safely — here's why: [reason, e.g., 'Line between bus 4 and 6 would exceed capacity']. Trade executed for the reduced amount." with a clear Accept/Decline on whether to proceed with the reduced amount, OR auto-execute the partial and just inform them — pick one behavior and be consistent, but document the choice in the UI copy so it's not ambiguous to the user which happened.
  - **Rejected:** "Trade blocked: this would overload [line/bus]. No energy was transferred." — with the technical reason shown, not just "failed."

### 4.4 Seller's trade history
* A simple table (not the map) of the seller's own past trades: buyer, amount, price, timestamp, feasibility outcome (full/partial/rejected). Pulls from `GET /trades/mine`.

---

## 5. Buyer experience (`/buyer`)

### 5.1 Buyer home page — the grid map
* Same base `GridGraph.jsx` map, but now overlaid with **open listings**: houses with surplus to sell are shown with their current asking price directly on the map (e.g., a small price tag/badge on the node).
* The buyer's own bus is highlighted, same as the seller view.
* Clicking a seller's house (one with an open listing) opens a side panel: seller's asking price, amount available, and a bid form.

### 5.2 Placing a bid
* Form: `requested_amount_kwh` (capped at the listing's available amount), `offered_price_per_kwh` (pre-filled with the seller's ask, but editable — this is a negotiation, not a fixed-price purchase).
* Submitting calls `POST /bids`.
* Show the bid's status (pending/accepted/rejected/etc.) once submitted, updating live via WebSocket when the seller responds.

### 5.3 Buyer's bid and trade history
* A table of the buyer's own bids (pending and resolved) and completed trades, same level of detail as the seller's history view (4.4), pulling from `GET /trades/mine` and a `GET /bids/mine` endpoint (add this if it doesn't exist).

---

## 6. Admin experience (`/admin`)

### 6.1 Grid state map (the substation operator's main view)
* The full feeder topology, color-coded live by voltage (per bus) and line loading percentage (per line) — this is the existing `GridGraph.jsx` congestion-coloring logic from Phase 8, just given its own dedicated full-page admin view rather than being buried in a seller/buyer panel.
* A legend explaining the color scale (e.g., green = healthy, yellow = approaching limit, red = violation).
* Live-updating via the WebSocket grid-state feed.

### 6.2 All trades view
* A comprehensive, filterable/sortable table of every trade in the system (`GET /trades/all`): buyer, seller, amount, price, timestamp, feasibility outcome, and — critically — **failed/rejected attempts too**, not just successful trades (per 2.4's requirement that every outcome gets a ledger entry).
* Filters: by date range, by outcome (full/partial/rejected), by specific buyer or seller.

### 6.3 Aggregate stats dashboard
Pull from `GET /admin/stats` and display as a set of summary cards/charts:
* Total number of trades (and breakdown: full / partial / rejected)
* Total energy traded (kWh) over time (a simple line chart — reuse the pattern from `PriceChart.jsx` in Phase 8)
* Number of active listings right now
* Number of registered sellers/buyers
* Feasibility rejection rate over time (this is genuinely your headline metric from the whole project — the naive-vs-gated comparison from Phase 5/7 of `tasks.md` — so give it real visual prominence here, e.g., "X trades this week would have caused a grid violation without the feasibility gate")

### 6.4 Ledger integrity check
* A simple admin-only button/page that runs the `verify_chain()` function from Phase 6 of `tasks.md` on demand and displays "Ledger verified: no tampering detected" or flags exactly which entry broke the chain. This doubles as a nice demo moment.

---

## 7. Cross-cutting UI requirements

* [ ] Responsive enough to demo on a laptop screen comfortably — this doesn't need to be mobile-first, but don't build something that breaks below 1280px wide.
* [ ] Every async action (placing a bid, accepting a bid, creating a listing) needs a visible loading state — the feasibility check in particular takes a moment (it's a GNN inference + possible partial-fill search), so don't let the UI look frozen or unresponsive during that call.
* [ ] Errors from the backend (validation errors, 403s, feasibility rejections) must be shown to the user in plain language, not as raw JSON or a silent console error.
* [ ] Use one consistent design system across all three role views — same color palette, same component library (pick one: plain CSS, Tailwind, or a component kit like MUI/shadcn — Tailwind is a reasonable default given the rest of the stack) — the seller/buyer/admin views should feel like one product, not three separate prototypes bolted together.

---

## 8. Suggested build order (do not skip ahead)

1. **Auth first, fully working end-to-end** — signup, login, JWT, route guarding, role-based redirects — before touching any map or bidding UI. If auth is half-built, everything downstream is untestable.
2. **Extend the backend** (Section 2) — new tables, new endpoints, the feasibility-check wiring in bid acceptance — and test every endpoint with `curl`/Swagger UI before writing any frontend code against it.
3. **Seller flow** (Section 4) end to end, including the feasibility-check result display — this is the more complex of the two trading flows since it owns bid acceptance.
4. **Buyer flow** (Section 5) — largely reuses the same map component and a simpler bid-placement form.
5. **Admin flow** (Section 6) — build last, since it depends on real trade data existing to be meaningful to look at; test it using the trades generated while building/testing steps 3 and 4.
6. **Polish pass** (Section 7) — loading states, error handling, consistent styling — once all three flows functionally work.

## 9. Definition of done

* [ ] A seller can sign up, log in, see their house on the map with deficit/surplus context, list surplus for sale, receive a bid, accept it, and see a clear feasibility outcome (full/partial/rejected) with a reason.
* [ ] A buyer can sign up, log in, see open listings on the map, place a bid, and see the outcome once the seller responds.
* [ ] Every trade attempt (successful, partial, or rejected) appears in both parties' trade history and in the admin's all-trades view.
* [ ] The admin can view a live, color-coded grid-state map, a full trade log, and aggregate stats including the feasibility-rejection-rate headline metric.
* [ ] The ledger integrity check runs on demand and correctly reports tampering if a record is manually altered in the database.
* [ ] No role can access another role's routes or data via direct URL navigation or direct API calls (verify this explicitly — attempt it during testing, don't just assume the guard works).