import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  AlertTriangle,
  BrainCircuit,
  ChevronDown,
  Clock3,
  Database,
  GitBranch,
  Monitor,
  Search,
  ShieldCheck,
  X,
  Zap,
} from "lucide-react";

import "./interactive.css";
import PaperActivity, { OrderList, PositionList, TradeList, TradingState } from "./PaperActivity";

const API =
  import.meta.env.VITE_API_URL || "";

type Panel =
  | "capital"
  | "predictions"
  | "market"
  | "learning"
  | "portfolio"
  | "orders"
  | "trades"
  | "runtime"
  | "reliability"
  | "activity"
  | "architecture"
  | "safety";

async function read(path: string) {
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

function money(value: unknown) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    },
  ).format(number);
}

export default function InteractiveInspector() {
  const [panel, setPanel] =
    useState<Panel | null>(null);

  const [symbol, setSymbol] =
    useState<string | null>(null);

  const [query, setQuery] =
    useState("");
  const [refreshing, setRefreshing] = useState(true);
  const drawer = useRef<HTMLElement>(null);
  const latestRequest = useRef(0);

  const [data, setData] =
    useState<any>({
      forward: null,
      predictions: [],
      dashboard: null,
      runtime: null,
      reliability: null,
      execution: null,
      architecture: null,
      trades: null,
      tradingErrors: { trades: null, orders: null, positions: null },
    });

  async function load() {
    const request = ++latestRequest.current;
    setRefreshing(true);
    const tradingRead = (path: string, message: string, valid: (value: any) => boolean) => read(path)
      .then(value => {
        if (!valid(value)) throw new Error("Unexpected paper-account response");
        return { value, error: null };
      })
      .catch(() => ({ value: null, error: message }));
    const [
      forward,
      predictions,
      dashboard,
      runtime,
      reliability,
      execution,
      architecture,
      trades,
    ] = await Promise.all([
      read("/api/forward/status")
        .catch(() => null),

      read("/api/forward/predictions")
        .catch(() => ({
          predictions: [],
        })),

      tradingRead("/api/dashboard", "Open positions could not be loaded.", value => Array.isArray(value?.positions)),

      read("/api/runtime/status")
        .catch(() => null),

      read("/api/reliability/status")
        .catch(() => null),

      tradingRead("/api/execution/status", "Order decisions could not be loaded.", value => Array.isArray(value?.orders)),

      read("/api/system/architecture")
        .catch(() => null),
      tradingRead("/api/trades", "Trade history could not be loaded.", Array.isArray),
    ]);

    if (request !== latestRequest.current) return;
    setData({
      forward,
      predictions:
        predictions?.predictions ?? [],
      dashboard: dashboard.value,
      runtime,
      reliability,
      execution: execution.value,
      architecture,
      trades: trades.value,
      tradingErrors: { trades: trades.error, orders: execution.error, positions: dashboard.error },
    });
    setRefreshing(false);
  }

  useEffect(() => {
    load();

    const timer =
      window.setInterval(
        load,
        30000,
      );

    return () => {
      window.clearInterval(timer);
      latestRequest.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!panel) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawer.current?.querySelector<HTMLButtonElement>("button")?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") { setPanel(null); setSymbol(null); }
      if (event.key === "Tab") {
        const elements = drawer.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input, summary, a[href], [tabindex="0"]',
        );
        if (!elements?.length) return;
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, [panel]);

  useEffect(() => {
    function openFromClick(
      event: MouseEvent,
    ) {
      const target =
        event.target as HTMLElement;

      if (
        target.closest(
          ".v122-drawer",
        ) ||
        target.closest(
          ".v122-architecture",
        ) || target.closest(".paper-trading-section")
      ) {
        return;
      }

      const prediction =
        target.closest(
          ".prediction",
        );

      if (prediction) {
        const name =
          prediction.querySelector(
            "h3",
          )?.textContent?.trim();

        if (name) {
          setSymbol(name);
          setPanel(
            "predictions",
          );
        }

        return;
      }

      const card =
        target.closest(".card");

      if (!card) {
        return;
      }

      const text =
        (
          card.textContent || ""
        ).toLowerCase();

      if (
        text.includes(
          "paper capital",
        ) ||
        text.includes("cash") ||
        text.includes(
          "total p&l",
        ) ||
        text.includes(
          "equity curve",
        )
      ) {
        setPanel("capital");
      } else if (
        text.includes(
          "latest forward predictions",
        )
      ) {
        setPanel(
          "predictions",
        );
      } else if (
        text.includes(
          "market state",
        )
      ) {
        setPanel("market");
      } else if (
        text.includes(
          "forward maturity",
        )
      ) {
        setPanel("learning");
      } else if (
        text.includes(
          "paper account",
        )
      ) {
        setPanel("portfolio");
      } else if (
        text.includes(
          "engine heartbeat",
        )
      ) {
        setPanel("runtime");
      } else if (
        text.includes(
          "research guardrails",
        )
      ) {
        setPanel("safety");
      } else if (
        text.includes(
          "runtime activity",
        )
      ) {
        setPanel("activity");
      }
    }

    document.addEventListener(
      "click",
      openFromClick,
    );

    return () =>
      document.removeEventListener(
        "click",
        openFromClick,
      );
  }, []);

  const predictions =
    useMemo(() => {
      const q =
        query
          .trim()
          .toLowerCase();

      return (
        data.predictions || []
      ).filter((item: any) =>
        !q ||
        String(item.symbol)
          .toLowerCase()
          .includes(q) ||
        String(item.sector)
          .toLowerCase()
          .includes(q),
      );
    }, [
      data.predictions,
      query,
    ]);

  const selected =
    symbol
      ? predictions.find(
          (item: any) =>
            item.symbol === symbol,
        )
      : null;

  const portfolio =
    data.dashboard?.portfolio ?? {};

  const orders =
    data.execution?.orders ?? [];

  const schedule =
    data.architecture
      ?.scheduler?.times ?? [
      "09:20",
      "10:20",
      "11:20",
      "12:20",
      "13:20",
      "14:20",
      "15:20",
      "16:05",
    ];

  function close() {
    setPanel(null);
    setSymbol(null);
  }

  return (
    <>
      <PaperActivity
        trades={data.trades}
        orders={data.execution?.orders ?? null}
        positions={data.dashboard?.positions ?? null}
        errors={data.tradingErrors}
        refreshing={refreshing}
        onOpen={setPanel}
        onRefresh={load}
      />
      <section className="card v122-architecture">
        <div className="v122-title">
          <div>
            <span>
              V1.2.2 OPERATING MODEL
            </span>
            <h2>
              Automated Architecture
            </h2>
          </div>

          <button
            type="button"
            onClick={() =>
              setPanel(
                "architecture",
              )
            }
          >
            Explore
            <ChevronDown
              size={16}
            />
          </button>
        </div>

        <div className="v122-flow">
          <button
            type="button"
            onClick={() =>
              setPanel("runtime")
            }
          >
            <GitBranch />
            <span>
              GitHub Actions
            </span>
            <strong>
              EXECUTE
            </strong>
          </button>

          <i>→</i>

          <button
            type="button"
            onClick={() =>
              setPanel("capital")
            }
          >
            <Database />
            <span>
              Neon PostgreSQL
            </span>
            <strong>
              STORE
            </strong>
          </button>

          <i>→</i>

          <button
            type="button"
            onClick={() =>
              setPanel(
                "reliability",
              )
            }
          >
            <Monitor />
            <span>
              Render
            </span>
            <strong>
              DISPLAY
            </strong>
          </button>

          <i>→</i>

          <button
            type="button"
            onClick={() =>
              setPanel("learning")
            }
          >
            <BrainCircuit />
            <span>
              ChatGPT
            </span>
            <strong>
              EXPLAIN / ALERT / TEACH
            </strong>
          </button>
        </div>

        <div className="v122-schedule">
          <Clock3 size={17} />

          {schedule.map(
            (time: string) => (
              <span key={time}>
                {time}
              </span>
            ),
          )}

          <small>
            IST • Weekdays • 16:05
            post-close
          </small>
        </div>
      </section>

      {panel && (
        <div
          className="v122-overlay"
          onMouseDown={(event) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              close();
            }
          }}
        >
          <aside className="v122-drawer" ref={drawer} role="dialog" aria-modal="true" aria-labelledby="inspection-title">
            <header>
              <div>
                <span>
                  INTERACTIVE DETAILS
                </span>
                <h2 id="inspection-title">
                  {panel.toUpperCase()}
                </h2>
              </div>

              <button
                type="button"
                onClick={close}
                aria-label="Close"
              >
                <X />
              </button>
            </header>

            <main>
              {panel ===
                "capital" && (
                <>
                  <div className="v122-hero">
                    <span>
                      Paper equity
                    </span>
                    <strong>
                      {money(
                        portfolio.value ??
                        (
                          Number(
                            portfolio.initialCapital ??
                            100000,
                          ) +
                          Number(
                            portfolio.totalPnl ??
                            0,
                          )
                        ),
                      )}
                    </strong>
                  </div>

                  <div className="v122-grid">
                    <K
                      a="Initial capital"
                      b={money(
                        portfolio.initialCapital,
                      )}
                    />
                    <K
                      a="Cash"
                      b={money(
                        portfolio.cash,
                      )}
                    />
                    <K
                      a="Invested"
                      b={money(
                        portfolio.invested,
                      )}
                    />
                    <K
                      a="Realized P&L"
                      b={money(
                        portfolio.realizedPnl,
                      )}
                    />
                    <K
                      a="Unrealized P&L"
                      b={money(
                        portfolio.unrealizedPnl,
                      )}
                    />
                    <K
                      a="Total P&L"
                      b={money(
                        portfolio.totalPnl,
                      )}
                    />
                  </div>
                </>
              )}

              {panel ===
                "predictions" && (
                <>
                  <label className="v122-search">
                    <Search size={16} />
                    <input
                      value={query}
                      onChange={(e) =>
                        setQuery(
                          e.target.value,
                        )
                      }
                      placeholder="Search symbol or sector"
                    />
                  </label>

                  {selected && (
                    <div className="v122-selected">
                      <h3>
                        {selected.symbol}
                      </h3>
                      <strong>
                        Score{" "}
                        {Number(
                          selected.score,
                        ).toFixed(1)}
                      </strong>
                      <span>
                        Observation price{" "}
                        {money(
                          selected.entryPrice,
                        )}
                      </span>
                      <span>
                        Regime{" "}
                        {selected.regime}
                      </span>
                      <span>
                        {
                          selected.modelVersion
                        }
                      </span>
                    </div>
                  )}

                  <div className="v122-list">
                    {predictions.map(
                      (item: any) => (
                        <button
                          type="button"
                          key={
                            item.predictionId
                          }
                          onClick={() =>
                            setSymbol(
                              item.symbol,
                            )
                          }
                        >
                          <div>
                            <strong>
                              {item.symbol}
                            </strong>
                            <span>
                              {item.sector}
                            </span>
                          </div>

                          <b>
                            {Number(
                              item.score,
                            ).toFixed(0)}
                          </b>
                        </button>
                      ),
                    )}
                  </div>
                </>
              )}

              {panel ===
                "market" && (
                <div className="v122-hero">
                  <span>
                    Latest prediction regime
                  </span>
                  <strong>
                    {
                      data.predictions?.[
                        0
                      ]?.regime ??
                      "UNKNOWN"
                    }
                  </strong>
                  <small>
                    Paper/research only.
                    Score is not probability.
                  </small>
                </div>
              )}

              {panel ===
                "learning" && (
                <div className="v122-grid">
                  {[
                    "5D",
                    "10D",
                    "20D",
                    "30D",
                  ].map(
                    (horizon) => {
                      const metric =
                        data.forward
                          ?.metrics
                          ?.horizons?.[
                            horizon
                          ];

                      return (
                        <K
                          key={
                            horizon
                          }
                          a={`${horizon} matured`}
                          b={String(
                            metric
                              ?.matured ??
                            0,
                          )}
                        />
                      );
                    },
                  )}
                </div>
              )}

              {panel ===
                "portfolio" && (
                <>
                  <button type="button" className="paper-link" onClick={load}>Refresh activity</button>
                  <TradingState error={data.tradingErrors.positions} pending={!data.dashboard}>
                    <PositionList positions={data.dashboard?.positions ?? []} />
                  </TradingState>
                </>
              )}

              {panel ===
                "runtime" && (
                <div className="v122-grid">
                  <K
                    a="Status"
                    b={
                      data.runtime
                        ?.runtime
                        ?.status ??
                      "UNKNOWN"
                    }
                  />
                  <K
                    a="Cycles"
                    b={String(
                      data.runtime
                        ?.runtime
                        ?.cycles ??
                      0,
                    )}
                  />
                  <K
                    a="Source"
                    b={
                      data.runtime
                        ?.runtime
                        ?.source ??
                      "—"
                    }
                  />
                  <K
                    a="Execution scheduler"
                    b="GITHUB ACTIONS"
                  />
                </div>
              )}

              {panel ===
                "reliability" && (
                <div className="v122-grid">
                  <K
                    a="Overall"
                    b={
                      data.reliability
                        ?.status ??
                      "UNKNOWN"
                    }
                  />
                  <K
                    a="Market data"
                    b={
                      data.reliability
                        ?.marketData
                        ?.status ??
                      "UNKNOWN"
                    }
                  />
                  <K
                    a="Ledger"
                    b={
                      data.reliability
                        ?.ledger
                        ?.status ??
                      "UNKNOWN"
                    }
                  />
                  <K
                    a="Checkpoint"
                    b={
                      data.reliability
                        ?.checkpoint
                        ?.status ??
                      "UNKNOWN"
                    }
                  />
                  <K
                    a="Market-data evidence"
                    b={data.reliability?.evidenceSource === "SHARED_CHECKPOINT"
                      ? "Saved execution checkpoint" : "Local history"}
                  />
                  <K
                    a="Checkpoint recorded"
                    b={data.reliability?.checkpointCreatedAt
                      ? new Date(data.reliability.checkpointCreatedAt).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST"
                      : "—"}
                  />
                </div>
              )}

              {panel ===
                "orders" && (
                <>
                  <button type="button" className="paper-link" onClick={load}>Refresh activity</button>
                  <TradingState error={data.tradingErrors.orders} pending={!data.execution}>
                    <OrderList orders={orders} />
                  </TradingState>
                </>
              )}

              {panel === "trades" && (
                <>
                  <button type="button" className="paper-link" onClick={load}>Refresh activity</button>
                  <p className="paper-caption">Up to 200 recent buy/sell fills. Entries and exits are separate records.</p>
                  <TradingState error={data.tradingErrors.trades} pending={data.trades === null}>
                    <TradeList trades={data.trades ?? []} />
                  </TradingState>
                </>
              )}

              {panel ===
                "activity" && (
                <div className="v122-list">
                  {(
                    data.runtime
                      ?.activity ??
                    []
                  ).map(
                    (
                      event: any,
                      index: number,
                    ) => (
                      <div
                        className="v122-event"
                        key={
                          event.eventId ??
                          index
                        }
                      >
                        <strong>
                          {
                            event.eventType
                          }
                        </strong>
                        <span>
                          {
                            event.message
                          }
                        </span>
                      </div>
                    ),
                  )}
                </div>
              )}

              {panel ===
                "architecture" && (
                <>
                  <div className="v122-copy">
                    GitHub is the only
                    execution authority.
                  </div>

                  <div className="v122-stack">
                    <b>
                      GitHub = EXECUTE
                    </b>
                    <span>↓</span>
                    <b>
                      Neon = STORE
                    </b>
                    <span>↓</span>
                    <b>
                      Render = DISPLAY
                    </b>
                    <span>↓</span>
                    <b>
                      ChatGPT = EXPLAIN /
                      ALERT / TEACH
                    </b>
                  </div>
                </>
              )}

              {panel ===
                "safety" && (
                <div className="v122-copy">
                  <ShieldCheck />
                  One-time ₹1,00,000
                  capital. Paper-only.
                  No live broker orders.
                  No automatic model
                  promotion.
                </div>
              )}

            </main>
          </aside>
        </div>
      )}
    </>
  );
}

function K({
  a,
  b,
}: {
  a: string;
  b: string;
}) {
  return (
    <div className="v122-k">
      <span>{a}</span>
      <strong>{b}</strong>
    </div>
  );
}
