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
} from "lucide-react";

import {
  createRoot,
} from "react-dom/client";

import "./style.css";


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
      ]);

      setStatus(statusData);

      setPredictions(
        predictionData.predictions,
      );

      setDashboard(
        dashboardData,
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
    latest[0]?.regime ||
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
            title="Portfolio"
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
                      Model frozen
                    </strong>

                    <span>
                      {
                        status
                          ?.modelVersion
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
                Outcomes cannot rewrite
                the frozen champion.
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
                Champion remains frozen
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


        <footer>
          <span>
            Adaptive Engine V0.6
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
