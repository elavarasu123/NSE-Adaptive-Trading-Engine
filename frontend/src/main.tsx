import React, {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  Activity,
  BrainCircuit,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  Database,
  FlaskConical,
  Gauge,
  LineChart,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  WalletCards,
  Zap,
  Radio,
  History,
} from "lucide-react";

import {
  createRoot,
} from "react-dom/client";

import "./style.css";
import InteractiveInspector from "./InteractiveInspector";
import MarketAnalysisCard, { type MarketAnalysis } from "./MarketAnalysis";


type Outcome = {
  horizon: number;
  stockReturn: number;
  niftyReturn: number;
  excessReturn: number;
};

type Prediction = {
  predictionId: string;
  predictionDate: string;
  symbol: string;
  sector: string;
  score: number;
  entryPrice: number;
  regime: string;
  modelVersion: string;
  maturityDates: Record<
    string,
    string | null
  >;
  outcomes: Record<
    string,
    Outcome
  >;
};

type HorizonMetrics = {
  matured: number;
  meanReturn: number | null;
  meanExcess: number | null;
  winRate: number | null;
  excessWinRate: number | null;
  ic: number | null;
};

type ForwardStatus = {
  engine: string;
  modelVersion: string;
  modelFrozen: boolean;
  researchOnly: boolean;
  liveTradingAllowed: boolean;
  totalPredictions: number;
  matured: Record<string, number>;
  pending: Record<string, number>;
  metrics: {
    horizons:
      Record<string, HorizonMetrics>;
  };
};


type RuntimeActivity = {
  eventId?: string;
  eventType: string;
  level: string;
  message: string;
  recordedAt: string;
  data?: Record<string, unknown>;
};

type EquityPoint = {
  timestamp: string;
  initialCapital: number;
  cash: number;
  marketValue: number;
  equity: number;
  realizedPnl: number;
  unrealizedPnl: number;
  totalPnl: number;
  openPositions: number;
};

type RuntimeStatus = {
  runtime: {
    version: string;
    status: string;
    lastStartedAt: string | null;
    lastCompletedAt: string | null;
    lastSuccessfulAt: string | null;
    lastRunId: string | null;
    lastError: string | null;
    cycles: number;
    source?: string;
  };
  latestEquity: EquityPoint | null;
  equityHistory: EquityPoint[];
  activity: RuntimeActivity[];
  safety: {
    paperOnly: boolean;
    liveBrokerOrders: boolean;
    capitalResetsDaily: boolean;
    automaticModelPromotion: boolean;
  };
};

type ReliabilityStatus = {
  status: string;
  allowRuntime: boolean;
  runtimeSource: string;
  marketData: {
    status: string;
    latestSession: string | null;
    expectedSession: string;
    sessionsBehind: number | null;
  };
  portfolio: {
    status: string;
  };
  ledger: {
    status: string;
  };
  checkpoint: {
    status: string;
  };
};

type Dashboard = {
  portfolio?: {
    initialCapital?: number;
    cash?: number;
    realizedPnl?: number;
    unrealizedPnl?: number;
    totalPnl?: number;
  };
  positions?: unknown[];
};

const API =
  import.meta.env.VITE_API_URL || "";


async function getJson<T>(
  path: string,
): Promise<T> {
  const response = await fetch(
    `${API}${path}`,
  );

  if (!response.ok) {
    throw new Error(
      `${path}: ${response.status}`,
    );
  }

  return response.json();
}


function money(
  value?: number | null,
) {
  if (
    value === null ||
    value === undefined
  ) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    },
  ).format(value);
}


function percent(
  value?: number | null,
) {
  if (
    value === null ||
    value === undefined
  ) {
    return "—";
  }

  return `${(
    value * 100
  ).toFixed(2)}%`;
}


function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`card ${className}`}
    >
      {children}
    </section>
  );
}


function Metric({
  icon,
  label,
  value,
  detail,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <Card className="metric-card">
      <div className="metric-top">
        <span className="icon-box">
          {icon}
        </span>
        <span className="metric-label">
          {label}
        </span>
      </div>

      <strong className="metric-value">
        {value}
      </strong>

      <span className="metric-detail">
        {detail}
      </span>
    </Card>
  );
}


function ScoreRing({
  score,
}: {
  score: number;
}) {
  const bounded = Math.min(
    Math.max(score, 0),
    100,
  );

  return (
    <div
      className="score-ring"
      style={{
        background:
          `conic-gradient(
            var(--accent)
            ${bounded * 3.6}deg,
            var(--track) 0deg
          )`,
      }}
    >
      <div className="score-core">
        <strong>
          {score.toFixed(0)}
        </strong>
        <span>
          score
        </span>
      </div>
    </div>
  );
}


function Maturity({
  prediction,
}: {
  prediction: Prediction;
}) {
  return (
    <div className="maturity">
      {[
        "5D",
        "10D",
        "20D",
        "30D",
      ].map((horizon) => {
        const matured =
          Boolean(
            prediction
              .outcomes[horizon],
          );

        return (
          <span
            key={horizon}
            className={
              matured
                ? "maturity-pill done"
                : "maturity-pill"
            }
          >
            {matured
              ? "✓ "
              : ""}
            {horizon}
          </span>
        );
      })}
    </div>
  );
}


function App() {
  const [analysis, setAnalysis] = useState<MarketAnalysis | null>(null);
  const [
    status,
    setStatus,
  ] = useState<
    ForwardStatus | null
  >(null);

  const [
    predictions,
    setPredictions,
  ] = useState<Prediction[]>([]);

  const [
    dashboard,
    setDashboard,
  ] = useState<Dashboard | null>(
    null,
  );

  const [
    runtime,
    setRuntime,
  ] = useState<RuntimeStatus | null>(
    null,
  );

  const [
    reliability,
    setReliability,
  ] = useState<ReliabilityStatus | null>(
    null,
  );


  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );


  async function load() {
    setLoading(true);

    try {
      const [
        statusData,
        predictionData,
        dashboardData,
        runtimeData,
        reliabilityData,
        analysisData,
      ] = await Promise.all([
        getJson<ForwardStatus>(
          "/api/forward/status",
        ),

        getJson<{
          predictions: Prediction[];
        }>(
          "/api/forward/predictions",
        ),

        getJson<Dashboard>(
          "/api/dashboard",
        ).catch(
          () => null,
        ),

        getJson<RuntimeStatus>(
          "/api/runtime/status",
        ).catch(
          () => null,
        ),

        getJson<ReliabilityStatus>(
          "/api/reliability/status",
        ).catch(
          () => null,
        ),
        getJson<MarketAnalysis>("/api/market/analysis").catch(() => null),
      ]);

      setStatus(statusData);
      setAnalysis(analysisData);

      setPredictions(
        predictionData.predictions,
      );

      setDashboard(
        dashboardData,
      );

      setRuntime(
        runtimeData,
      );

      setReliability(
        reliabilityData,
      );

      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load engine.",
      );
    } finally {
      setLoading(false);
    }
  }



  useEffect(() => {
    load();

    const timer = window.setInterval(
      load,
      30000,
    );

    return () =>
      window.clearInterval(timer);
  }, []);


  const latest = useMemo(() => {
    if (!predictions.length) {
      return [];
    }

    const dates =
      predictions
        .map(
          (p) =>
            p.predictionDate,
        )
        .sort();

    const date =
      dates[
        dates.length - 1
      ];

    return predictions
      .filter(
        (p) =>
          p.predictionDate ===
          date,
      )
      .sort(
        (a, b) =>
          b.score - a.score,
      );
  }, [predictions]);


  const regime =
    analysis?.regime.name ||
    "UNKNOWN";

  const capital =
    dashboard
      ?.portfolio
      ?.initialCapital ??
    100000;

  const cash =
    dashboard
      ?.portfolio
      ?.cash ??
    capital;

  const pnl =
    dashboard
      ?.portfolio
      ?.totalPnl ??
    0;

  const positions =
    dashboard
      ?.positions
      ?.length ??
    0;


  const runtimeState =
    runtime?.runtime?.status ??
    "UNKNOWN";

  const equityHistory =
    runtime?.equityHistory ?? [];

  const recentActivity =
    runtime?.activity?.slice(
      0,
      8,
    ) ?? [];

  const latestEquity =
    runtime?.latestEquity;

  const equityMin =
    equityHistory.length
      ? Math.min(
          ...equityHistory.map(
            (point) =>
              point.equity,
          ),
        )
      : capital;

  const equityMax =
    equityHistory.length
      ? Math.max(
          ...equityHistory.map(
            (point) =>
              point.equity,
          ),
        )
      : capital;

  const equityRange =
    Math.max(
      equityMax - equityMin,
      1,
    );

  if (loading && !status) {
    return (
      <div className="loading">
        <BrainCircuit
          size={36}
        />
        <strong>
          Booting adaptive engine…
        </strong>
      </div>
    );
  }


  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-mark">
          <Zap size={22} />
        </div>

        <nav>
          <button
            className="nav active"
            title="Overview"
          >
            <Gauge />
          </button>

          <button
            className="nav"
            title="Scanner"
          >
            <Target />
          </button>

          <button
            className="nav"
            title="Portfolio and trades"
            aria-label="Portfolio and trades"
            onClick={() => document.getElementById("paper-trading")?.scrollIntoView({ block: "start" })}
          >
            <WalletCards />
          </button>

          <button
            className="nav"
            title="Learning"
          >
            <BrainCircuit />
          </button>

          <button
            className="nav"
            title="Research"
          >
            <FlaskConical />
          </button>
        </nav>

        <div className="sidebar-bottom">
          <Database size={18} />
        </div>
      </aside>


      <main>
        <header>
          <div>
            <div className="eyebrow">
              NSE ADAPTIVE ENGINE
            </div>

            <h1>
              Command Center
            </h1>

            <p>
              Forward paper-learning
              environment
            </p>
          </div>

          <div className="header-actions">
            <div
              className={
                `engine-state ${
                  error
                    ? "danger"
                    : "online"
                }`
              }
            >
              <span
                className="pulse-dot"
              />
              {error
                ? "API ERROR"
                : "ENGINE ONLINE"}
            </div>


            <button
              className="refresh"
              onClick={load}
            >
              <RefreshCw
                size={17}
              />
              Refresh
            </button>
          </div>
        </header>


        {error && (
          <div className="error">
            {error}
          </div>
        )}


        <div className="metrics">
          <Metric
            icon={
              <CircleDollarSign />
            }
            label="Paper Capital"
            value={money(capital)}
            detail="One-time capital"
          />

          <Metric
            icon={
              <WalletCards />
            }
            label="Cash"
            value={money(cash)}
            detail={`${positions} open positions`}
          />

          <Metric
            icon={
              <TrendingUp />
            }
            label="Total P&L"
            value={money(pnl)}
            detail="Paper only"
          />

          <Metric
            icon={
              <BrainCircuit />
            }
            label="Predictions"
            value={String(
              status
                ?.totalPredictions ??
              0,
            )}
            detail={
              status
                ?.modelVersion ??
              "—"
            }
          />
        </div>


        <MarketAnalysisCard analysis={analysis} />

        <div className="primary-grid">
          <Card className="pulse-card">
            <div className="section-head">
              <div>
                <span className="section-kicker">
                  ENGINE PULSE
                </span>

                <h2>
                  Market State
                </h2>
              </div>

              <Activity
                className="accent-icon"
              />
            </div>

            <div className="regime-layout">
              <div
                className={
                  `regime-orb ${
                    regime
                      .toLowerCase()
                  }`
                }
              >
                <span>
                  REGIME
                </span>

                <strong>
                  {regime}
                </strong>
              </div>

              <div className="pulse-copy">
                <div className="status-line">
                  <ShieldCheck
                    size={18}
                  />

                  <div>
                    <strong>
                      Research mode
                    </strong>

                    <span>
                      No autonomous
                      live orders
                    </span>
                  </div>
                </div>

                <div className="status-line">
                  <LockKeyhole
                    size={18}
                  />

                  <div>
                    <strong>
                      Adaptive entry policy
                    </strong>

                    <span>
                      {
                        analysis?.adaptivePolicy?.status ?? "Waiting for analysis"
                      }
                    </span>
                  </div>
                </div>

                <div className="status-line">
                  <Clock3
                    size={18}
                  />

                  <div>
                    <strong>
                      Forward evidence
                    </strong>

                    <span>
                      5 / 10 / 20 /
                      30 sessions
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {regime === "PANIC" && (
              <div className="panic-banner">
                <ShieldCheck
                  size={18}
                />

                <span>
                  PANIC regime detected.
                  Predictions remain
                  observations; risk
                  controls block blind
                  score-based execution.
                </span>
              </div>
            )}
          </Card>


          <Card>
            <div className="section-head">
              <div>
                <span className="section-kicker">
                  LEARNING LAB
                </span>

                <h2>
                  Forward Maturity
                </h2>
              </div>

              <Sparkles
                className="accent-icon"
              />
            </div>

            <div className="horizon-grid">
              {[
                "5D",
                "10D",
                "20D",
                "30D",
              ].map((horizon) => {
                const metric =
                  status
                    ?.metrics
                    ?.horizons
                    ?.[horizon];

                return (
                  <div
                    className="horizon"
                    key={horizon}
                  >
                    <strong>
                      {horizon}
                    </strong>

                    <span>
                      {
                        metric
                          ?.matured ??
                        0
                      } matured
                    </span>

                    <div className="horizon-value">
                      {percent(
                        metric
                          ?.meanExcess,
                      )}
                    </div>

                    <small>
                      excess vs Nifty
                    </small>
                  </div>
                );
              })}
            </div>

            <div className="guardrail">
              <LockKeyhole
                size={17}
              />

              <span>
                Validated outcomes can update paper entry thresholds; original predictions remain unchanged.
              </span>
            </div>
          </Card>
        </div>


        <Card className="prediction-section">
          <div className="section-head">
            <div>
              <span className="section-kicker">
                OPPORTUNITY RADAR
              </span>

              <h2>
                Latest Forward Predictions
              </h2>
            </div>

            <div className="latest-date">
              {latest[0]
                ?.predictionDate ??
                "No batch"}
            </div>
          </div>

          <div className="prediction-grid">
            {latest.map(
              (prediction) => (
                <article
                  className="prediction"
                  key={
                    prediction
                      .predictionId
                  }
                >
                  <div className="prediction-top">
                    <div>
                      <h3>
                        {
                          prediction
                            .symbol
                        }
                      </h3>

                      <span>
                        {
                          prediction
                            .sector
                        }
                      </span>
                    </div>

                    <ScoreRing
                      score={
                        prediction
                          .score
                      }
                    />
                  </div>

                  <div className="entry-row">
                    <span>
                      Observation price
                    </span>

                    <strong>
                      {money(
                        prediction
                          .entryPrice,
                      )}
                    </strong>
                  </div>

                  <div className="regime-row">
                    <span>
                      Regime
                    </span>

                    <strong
                      className={
                        `regime-text ${
                          prediction
                            .regime
                            .toLowerCase()
                        }`
                      }
                    >
                      {
                        prediction
                          .regime
                      }
                    </strong>
                  </div>

                  <Maturity
                    prediction={
                      prediction
                    }
                  />

                  <div className="prediction-foot">
                    <span>
                      Score ≠ probability
                    </span>

                    <ChevronRight
                      size={16}
                    />
                  </div>
                </article>
              ),
            )}
          </div>
        </Card>


        <div className="bottom-grid">
          <Card>
            <div className="section-head">
              <div>
                <span className="section-kicker">
                  PORTFOLIO
                </span>

                <h2>
                  Paper Account
                </h2>
              </div>

              <LineChart
                className="accent-icon"
              />
            </div>

            <div className="portfolio-total">
              <span>
                Equity
              </span>

              <strong>
                {money(
                  capital + pnl,
                )}
              </strong>
            </div>

            <div className="allocation-bar">
              <div
                style={{
                  width:
                    `${Math.min(
                      100,
                      Math.max(
                        0,
                        cash /
                          Math.max(
                            capital +
                              pnl,
                            1,
                          ) *
                          100,
                      ),
                    )}%`,
                }}
              />
            </div>

            <div className="allocation-labels">
              <span>
                Cash {money(cash)}
              </span>

              <span>
                {positions} positions
              </span>
            </div>
          </Card>


          <Card>
            <div className="section-head">
              <div>
                <span className="section-kicker">
                  SAFETY
                </span>

                <h2>
                  Research Guardrails
                </h2>
              </div>

              <ShieldCheck
                className="accent-icon"
              />
            </div>

            <div className="rules">
              <div>
                <span className="check">
                  ✓
                </span>
                ₹1L capital never
                resets daily
              </div>

              <div>
                <span className="check">
                  ✓
                </span>
                1D movement does not
                judge predictions
              </div>

              <div>
                <span className="check">
                  ✓
                </span>
                Prediction ledger is
                append-only
              </div>

              <div>
                <span className="check">
                  ✓
                </span>
                Paper policy adapts after validation
              </div>

              <div>
                <span className="check">
                  ✓
                </span>
                Live broker execution
                disabled
              </div>
            </div>
          </Card>
        </div>



        <InteractiveInspector />

        <div className="runtime-grid">
          <Card>
            <div className="section-head">
              <div>
                <span className="section-kicker">
                  RUNTIME
                </span>

                <h2>
                  Engine Heartbeat
                </h2>
              </div>

              <Radio
                className="accent-icon"
              />
            </div>

            <div className="heartbeat">
              <div
                className={
                  `heartbeat-orb ${
                    runtimeState
                      .toLowerCase()
                  }`
                }
              >
                <span />
              </div>

              <div>
                <strong>
                  {runtimeState}
                </strong>

                <p>
                  {
                    runtime
                      ?.runtime
                      ?.cycles ?? 0
                  } completed cycles
                </p>
              </div>
            </div>

            <div className="runtime-details">
              <div>
                <span>
                  Last successful cycle
                </span>

                <strong>
                  {
                    runtime
                      ?.runtime
                      ?.lastSuccessfulAt
                      ? new Date(
                          runtime
                            .runtime
                            .lastSuccessfulAt,
                        ).toLocaleString(
                          "en-IN",
                        )
                      : "Never"
                  }
                </strong>
              </div>

              <div>
                <span>
                  Runtime source
                </span>

                <strong>
                  {
                    runtime
                      ?.runtime
                      ?.source
                    ?? reliability
                      ?.runtimeSource
                    ?? "LOCAL"
                  }
                </strong>
              </div>

              <div>
                <span>
                  Market data
                </span>

                <strong>
                  {
                    reliability
                      ?.marketData
                      ?.status
                    ?? "UNKNOWN"
                  }
                </strong>
              </div>

              <div>
                <span>
                  Integrity
                </span>

                <strong>
                  {
                    reliability
                      ?.checkpoint
                      ?.status
                    ?? "UNKNOWN"
                  }
                </strong>
              </div>

              <div>
                <span>
                  Paper-only
                </span>

                <strong>
                  {
                    runtime
                      ?.safety
                      ?.paperOnly
                      ? "ENFORCED"
                      : "UNKNOWN"
                  }
                </strong>
              </div>

              <div>
                <span>
                  Broker orders
                </span>

                <strong>
                  {
                    runtime
                      ?.safety
                      ?.liveBrokerOrders
                      ? "ENABLED"
                      : "DISABLED"
                  }
                </strong>
              </div>
            </div>
          </Card>


          <Card>
            <div className="section-head">
              <div>
                <span className="section-kicker">
                  EQUITY
                </span>

                <h2>
                  Paper Equity Curve
                </h2>
              </div>

              <TrendingUp
                className="accent-icon"
              />
            </div>

            <div className="equity-number">
              <strong>
                {money(
                  latestEquity
                    ?.equity ??
                  capital + pnl,
                )}
              </strong>

              <span>
                {
                  equityHistory.length
                } snapshots
              </span>
            </div>

            <div className="equity-chart">
              {
                equityHistory.length
                  ? equityHistory.map(
                      (
                        point,
                        index,
                      ) => {
                        const normalized =
                          (
                            point.equity -
                            equityMin
                          ) /
                          equityRange;

                        const height =
                          15 +
                          normalized *
                          85;

                        return (
                          <div
                            key={
                              `${point.timestamp}-${index}`
                            }
                            className="equity-bar"
                            title={
                              `${point.timestamp} • ${money(point.equity)}`
                            }
                            style={{
                              height:
                                `${height}%`,
                            }}
                          />
                        );
                      },
                    )
                  : (
                    <div className="empty-state">
                      Run a paper cycle to
                      create equity history.
                    </div>
                  )
              }
            </div>

            <div className="equity-meta">
              <span>
                Low {money(equityMin)}
              </span>

              <span>
                High {money(equityMax)}
              </span>
            </div>
          </Card>
        </div>


        <Card className="activity-card">
          <div className="section-head">
            <div>
              <span className="section-kicker">
                JOURNAL
              </span>

              <h2>
                Runtime Activity
              </h2>
            </div>

            <History
              className="accent-icon"
            />
          </div>

          <div className="timeline">
            {
              recentActivity.length
                ? recentActivity.map(
                    (
                      event,
                      index,
                    ) => (
                      <div
                        className="timeline-row"
                        key={
                          event.eventId ??
                          `${event.recordedAt}-${index}`
                        }
                      >
                        <div
                          className={
                            `timeline-dot ${
                              event.level
                                .toLowerCase()
                            }`
                          }
                        />

                        <div className="timeline-body">
                          <div className="timeline-head">
                            <strong>
                              {
                                event.eventType
                              }
                            </strong>

                            <span>
                              {
                                new Date(
                                  event.recordedAt,
                                ).toLocaleString(
                                  "en-IN",
                                )
                              }
                            </span>
                          </div>

                          <p>
                            {event.message}
                          </p>
                        </div>
                      </div>
                    ),
                  )
                : (
                  <div className="empty-state">
                    No runtime activity yet.
                  </div>
                )
            }
          </div>
        </Card>


        <footer>
          <span>
            Adaptive Engine V1.2.2
          </span>

          <span>
            Research / Paper Trading
            Only
          </span>
        </footer>
      </main>
    </div>
  );
}


createRoot(
  document.getElementById(
    "root",
  )!,
).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
