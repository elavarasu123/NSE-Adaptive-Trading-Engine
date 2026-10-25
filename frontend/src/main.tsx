import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  BrainCircuit,
  Crosshair,
  Gauge,
  History,
  Play,
  RefreshCw,
  ShieldCheck,
  Target,
  TrendingUp,
  Wallet,
} from "lucide-react";
import "./style.css";

const API = "";

type Candidate = {
  symbol: string;
  price: number;
  score: number;
  decision: string;
  rawDecision?: string;
  up: number;
  sideways: number;
  down: number;
  rsi14?: number;
  relativeStrength3m?: number;
  relativeStrength6m?: number;
  volumeRatio?: number;
  regime?: string;
  regimeGate?: string;
};

type Dashboard = {
  portfolio?: {
    initialCapital: number;
    cash: number;
    invested: number;
    value: number;
    realizedPnl: number;
    unrealizedPnl: number;
    totalPnl: number;
  };
  engine?: {
    status: string;
    strategy: string;
    regime: string;
    mode: string;
  };
  positions?: any[];
};

type Regime = {
  name: string;
  score: number;
  confidence: number;
  exposure_multiplier?: number;
  exposureMultiplier?: number;
  buy_threshold?: number;
  buyThreshold?: number;
  reasons?: string[];
};

type Risk = {
  open_positions: number;
  market_value: number;
  exposure_pct: number;
  capital_at_risk: number;
  risk_pct: number;
  remaining_risk: number;
  remaining_exposure: number;
};

type Accuracy = {
  totalMatured: number;
  byHorizon: Record<
    string,
    {
      matured: number;
      accuracy: number | null;
      avgBrier: number | null;
      avgForwardReturn: number | null;
      evidence: string;
    }
  >;
};

const money = (v?: number) =>
  `₹${Number(v || 0).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;

const pct = (v?: number | null, scale = 1) =>
  v == null ? "—" : `${(v * scale).toFixed(2)}%`;

function App() {
  const [tab, setTab] = useState("overview");
  const [dashboard, setDashboard] = useState<Dashboard>({});
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [regime, setRegime] = useState<Regime | null>(null);
  const [risk, setRisk] = useState<Risk | null>(null);
  const [accuracy, setAccuracy] = useState<Accuracy | null>(null);
  const [predictions, setPredictions] = useState<any[]>([]);
  const [outcomes, setOutcomes] = useState<any[]>([]);
  const [activity, setActivity] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function get(path: string) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  }

  async function post(path: string) {
    const r = await fetch(API + path, { method: "POST" });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `${path}: ${r.status}`);
    return body;
  }

  async function refresh() {
    setBusy(true);
    setMessage("");

    try {
      const [
        dash,
        scan,
        reg,
        riskData,
        acc,
        preds,
        outs,
        acts,
        tradeData,
      ] = await Promise.all([
        get("/api/dashboard"),
        get("/api/scanner/report"),
        get("/api/regime"),
        get("/api/risk"),
        get("/api/accuracy"),
        get("/api/predictions"),
        get("/api/outcomes"),
        get("/api/activity"),
        get("/api/trades"),
      ]);

      setDashboard(dash);
      setCandidates(scan.results || []);
      setRegime(reg);
      setRisk(riskData);
      setAccuracy(acc);
      setPredictions(preds || []);
      setOutcomes(outs || []);
      setActivity(acts || []);
      setTrades(tradeData || []);
    } catch (e: any) {
      setMessage(e.message || "Backend unavailable");
    } finally {
      setBusy(false);
    }
  }

  async function runEngine() {
    setBusy(true);
    try {
      const result = await post("/api/engine/run");
      setMessage(
        `Frozen ${result.predictionsFrozen} predictions / ${result.checkpointsCreated} checkpoints`
      );
      await refresh();
    } catch (e: any) {
      setMessage(e.message);
      setBusy(false);
    }
  }

  async function buy(symbol: string) {
    if (!confirm(`Paper BUY ${symbol}? No real order will be placed.`)) return;

    setBusy(true);
    try {
      await post(`/api/paper/buy/${symbol}`);
      setMessage(`${symbol} paper position opened`);
      await refresh();
    } catch (e: any) {
      setMessage(e.message);
      setBusy(false);
    }
  }

  async function sell(symbol: string) {
    if (!confirm(`Close paper position in ${symbol}?`)) return;

    setBusy(true);
    try {
      await post(`/api/paper/sell/${symbol}`);
      setMessage(`${symbol} paper position closed`);
      await refresh();
    } catch (e: any) {
      setMessage(e.message);
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const portfolio = dashboard.portfolio || ({} as any);
  const positions = dashboard.positions || [];

  const nav = [
    ["overview", Gauge, "Overview"],
    ["scanner", Crosshair, "Scanner"],
    ["positions", Wallet, "Positions"],
    ["predictions", BrainCircuit, "Predictions"],
    ["performance", BarChart3, "Performance"],
    ["activity", History, "Activity"],
  ] as const;

  return (
    <div className="app">
      <aside>
        <div className="brand">
          <div className="brandIcon"><TrendingUp size={21} /></div>
          <div>
            <strong>Adaptive Engine</strong>
            <span>NSE Research Lab</span>
          </div>
        </div>

        <nav>
          {nav.map(([id, Icon, label]) => (
            <button
              key={id}
              className={tab === id ? "active" : ""}
              onClick={() => setTab(id)}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>

        <div className="paperBadge">
          <ShieldCheck size={18} />
          <div>
            <strong>PAPER ONLY</strong>
            <span>No real orders</span>
          </div>
        </div>
      </aside>

      <main>
        <header>
          <div>
            <h1>
              {nav.find(([id]) => id === tab)?.[2]}
            </h1>
            <p>
              Champion v0.2 · Research environment · Yahoo data
            </p>
          </div>

          <div className="actions">
            <button className="secondary" onClick={refresh}>
              <RefreshCw size={17} className={busy ? "spin" : ""} />
              Refresh
            </button>
            <button className="primary" onClick={runEngine}>
              <Play size={17} />
              Run Engine
            </button>
          </div>
        </header>

        {message && <div className="notice">{message}</div>}

        {tab === "overview" && (
          <>
            <section className="cards">
              <Card
                title="Portfolio"
                value={money(portfolio.value)}
                sub={`Initial ${money(portfolio.initialCapital)}`}
                icon={<Wallet />}
              />
              <Card
                title="Cash"
                value={money(portfolio.cash)}
                sub={`${money(portfolio.invested)} invested`}
                icon={<Activity />}
              />
              <Card
                title="Total P&L"
                value={money(portfolio.totalPnl)}
                sub={`Realized ${money(portfolio.realizedPnl)}`}
                icon={<TrendingUp />}
              />
              <Card
                title="Market Regime"
                value={regime?.name || "—"}
                sub={`Confidence ${
                  regime ? Math.round(regime.confidence * 100) : 0
                }%`}
                icon={<Gauge />}
              />
            </section>

            <section className="twoCol">
              <Panel title="Opportunity Radar">
                <CandidateTable
                  rows={candidates.slice(0, 5)}
                  onBuy={buy}
                />
              </Panel>

              <Panel title="Risk Brain">
                <div className="riskGrid">
                  <Metric
                    label="Open positions"
                    value={`${risk?.open_positions || 0} / 6`}
                  />
                  <Metric
                    label="Portfolio risk"
                    value={`${risk?.risk_pct || 0}% / 4%`}
                  />
                  <Metric
                    label="Exposure"
                    value={`${risk?.exposure_pct || 0}% / 70%`}
                  />
                  <Metric
                    label="Risk remaining"
                    value={money(risk?.remaining_risk)}
                  />
                </div>

                <div className="ruleList">
                  <span>≤ 1% risk per trade</span>
                  <span>≤ 15% nominal position</span>
                  <span>ATR + structure stop</span>
                  <span>Regime-aware sizing</span>
                  <span>No leverage / F&O / shorts</span>
                </div>
              </Panel>
            </section>

            <Panel title="Open Positions">
              <PositionTable rows={positions} onSell={sell} />
            </Panel>
          </>
        )}

        {tab === "scanner" && (
          <Panel title="NSE Opportunity Scanner">
            <div className="regimeStrip">
              <div>
                <small>REGIME</small>
                <strong>{regime?.name || "—"}</strong>
              </div>
              <div>
                <small>REGIME SCORE</small>
                <strong>{regime?.score ?? "—"}</strong>
              </div>
              <div>
                <small>EXPOSURE MULTIPLIER</small>
                <strong>
                  {regime
                    ? regime.exposureMultiplier ??
                      regime.exposure_multiplier ??
                      "—"
                    : "—"}
                </strong>
              </div>
            </div>

            <CandidateTable rows={candidates} onBuy={buy} />
          </Panel>
        )}

        {tab === "positions" && (
          <>
            <section className="cards">
              <Card
                title="Market Value"
                value={money(risk?.market_value)}
                sub={`${risk?.exposure_pct || 0}% exposure`}
                icon={<Wallet />}
              />
              <Card
                title="Capital at Risk"
                value={money(risk?.capital_at_risk)}
                sub={`${risk?.risk_pct || 0}% of capital`}
                icon={<ShieldCheck />}
              />
              <Card
                title="Open Positions"
                value={`${risk?.open_positions || 0}`}
                sub="Maximum 6"
                icon={<Target />}
              />
            </section>

            <Panel title="Paper Portfolio">
              <PositionTable rows={positions} onSell={sell} />
            </Panel>
          </>
        )}

        {tab === "predictions" && (
          <>
            <section className="cards">
              {["5D", "10D", "20D", "30D"].map((h) => {
                const a = accuracy?.byHorizon?.[h];
                return (
                  <Card
                    key={h}
                    title={`${h} Accuracy`}
                    value={
                      a?.accuracy == null
                        ? "Pending"
                        : pct(a.accuracy, 100)
                    }
                    sub={`${a?.matured || 0} matured · ${
                      a?.evidence || "INSUFFICIENT"
                    }`}
                    icon={<BrainCircuit />}
                  />
                );
              })}
            </section>

            <Panel title="Frozen Predictions">
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Decision</th>
                      <th>UP</th>
                      <th>Sideways</th>
                      <th>DOWN</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {predictions.slice(0, 100).map((p) => (
                      <tr key={p.id}>
                        <td><b>{p.symbol}</b></td>
                        <td>{p.decision}</td>
                        <td>{pct(p.up, 100)}</td>
                        <td>{pct(p.sideways, 100)}</td>
                        <td>{pct(p.down, 100)}</td>
                        <td><Badge value={p.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel title="Outcome Checkpoints">
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Horizon</th>
                      <th>Predicted</th>
                      <th>Actual</th>
                      <th>Return</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outcomes.slice(0, 100).map((o) => (
                      <tr key={o.id}>
                        <td><b>{o.symbol}</b></td>
                        <td>{o.horizonDays}D</td>
                        <td>{o.predicted}</td>
                        <td>{o.actual || "—"}</td>
                        <td>
                          {o.forwardReturn == null
                            ? "—"
                            : pct(o.forwardReturn, 100)}
                        </td>
                        <td><Badge value={o.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </>
        )}

        {tab === "performance" && (
          <>
            <section className="cards">
              <Card
                title="Matured Predictions"
                value={`${accuracy?.totalMatured || 0}`}
                sub="No early grading"
                icon={<BrainCircuit />}
              />
              <Card
                title="Realized P&L"
                value={money(portfolio.realizedPnl)}
                sub="Paper trades"
                icon={<TrendingUp />}
              />
              <Card
                title="Trade Count"
                value={`${trades.length}`}
                sub="BUY + SELL events"
                icon={<Activity />}
              />
            </section>

            <Panel title="Horizon Evaluation">
              <div className="accuracyGrid">
                {["5D", "10D", "20D", "30D"].map((h) => {
                  const a = accuracy?.byHorizon?.[h];

                  return (
                    <div className="accuracyCard" key={h}>
                      <span>{h}</span>
                      <strong>
                        {a?.accuracy == null
                          ? "Not matured"
                          : pct(a.accuracy, 100)}
                      </strong>
                      <small>
                        Brier: {a?.avgBrier ?? "—"}
                      </small>
                      <small>
                        Avg return:{" "}
                        {a?.avgForwardReturn == null
                          ? "—"
                          : pct(a.avgForwardReturn, 100)}
                      </small>
                      <Badge value={a?.evidence || "INSUFFICIENT"} />
                    </div>
                  );
                })}
              </div>
            </Panel>

            <div className="warningBox">
              Performance remains experimental until enough independent
              predictions mature across different market regimes.
            </div>
          </>
        )}

        {tab === "activity" && (
          <Panel title="Engine Journal">
            <div className="timeline">
              {activity.map((item) => (
                <div className="event" key={item.id}>
                  <div className="dot" />
                  <div>
                    <b>{item.kind}</b>
                    <p>{item.message}</p>
                    <small>
                      {item.createdAt
                        ? new Date(item.createdAt).toLocaleString()
                        : ""}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        )}

        <footer>
          PAPER TRADING · RESEARCH ONLY · NOT INVESTMENT ADVICE · NO REAL ORDERS
        </footer>
      </main>
    </div>
  );
}

function Card({ title, value, sub, icon }: any) {
  return (
    <div className="card">
      <div className="cardTop">
        <span>{title}</span>
        <div className="iconBox">{icon}</div>
      </div>
      <strong className="big">{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

function Panel({ title, children }: any) {
  return (
    <section className="panel">
      <div className="panelTitle">
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value }: any) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Badge({ value }: { value: string }) {
  const text = value || "UNKNOWN";
  return (
    <span className={`badge ${text.toLowerCase()}`}>
      {text}
    </span>
  );
}

function CandidateTable({
  rows,
  onBuy,
}: {
  rows: Candidate[];
  onBuy: (s: string) => void;
}) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Stock</th>
            <th>Score</th>
            <th>Price</th>
            <th>RS 3M</th>
            <th>RS 6M</th>
            <th>UP / SIDE / DOWN</th>
            <th>Decision</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((x) => (
            <tr key={x.symbol}>
              <td>
                <b>{x.symbol}</b>
                <small className="subline">
                  RSI {x.rsi14?.toFixed?.(1) ?? "—"}
                </small>
              </td>
              <td>
                <div className="score">
                  <strong>{x.score}</strong>
                  <div>
                    <i style={{ width: `${x.score}%` }} />
                  </div>
                </div>
              </td>
              <td>{money(x.price)}</td>
              <td>
                {x.relativeStrength3m == null
                  ? "—"
                  : pct(x.relativeStrength3m, 100)}
              </td>
              <td>
                {x.relativeStrength6m == null
                  ? "—"
                  : pct(x.relativeStrength6m, 100)}
              </td>
              <td>
                <div className="prob">
                  <span>↑ {x.up}%</span>
                  <span>→ {x.sideways}%</span>
                  <span>↓ {x.down}%</span>
                </div>
              </td>
              <td>
                <Badge value={x.decision} />
              </td>
              <td>
                {x.decision === "BUY" && (
                  <button
                    className="mini"
                    onClick={() => onBuy(x.symbol)}
                  >
                    Paper Buy
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PositionTable({
  rows,
  onSell,
}: {
  rows: any[];
  onSell: (s: string) => void;
}) {
  if (!rows.length) {
    return (
      <div className="empty">
        No open paper positions.
      </div>
    );
  }

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Qty</th>
            <th>Entry</th>
            <th>Current</th>
            <th>Stop</th>
            <th>Target</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id || p.symbol}>
              <td><b>{p.symbol}</b></td>
              <td>{p.quantity}</td>
              <td>{money(p.avgPrice ?? p.avg_price)}</td>
              <td>{money(p.currentPrice ?? p.current_price)}</td>
              <td>{money(p.stopPrice ?? p.stop_price)}</td>
              <td>{money(p.targetPrice ?? p.target_price)}</td>
              <td>
                <button
                  className="mini danger"
                  onClick={() => onSell(p.symbol)}
                >
                  Paper Sell
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
