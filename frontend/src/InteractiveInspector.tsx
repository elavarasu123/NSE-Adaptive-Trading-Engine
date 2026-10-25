import React, {
  useEffect,
  useMemo,
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

const API =
  import.meta.env.VITE_API_URL || "";

type Panel =
  | "capital"
  | "predictions"
  | "market"
  | "learning"
  | "portfolio"
  | "orders"
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

  const [data, setData] =
    useState<any>({
      forward: null,
      predictions: [],
      dashboard: null,
      runtime: null,
      reliability: null,
      execution: null,
      architecture: null,
    });

  async function load() {
    const [
      forward,
      predictions,
      dashboard,
      runtime,
      reliability,
      execution,
      architecture,
    ] = await Promise.all([
      read("/api/forward/status")
        .catch(() => null),

      read("/api/forward/predictions")
        .catch(() => ({
          predictions: [],
        })),

      read("/api/dashboard")
        .catch(() => null),

      read("/api/runtime/status")
        .catch(() => null),

      read("/api/reliability/status")
        .catch(() => null),

      read("/api/execution/status")
        .catch(() => null),

      read("/api/system/architecture")
        .catch(() => null),
    ]);

    setData({
      forward,
      predictions:
        predictions?.predictions ?? [],
      dashboard,
      runtime,
      reliability,
      execution,
      architecture,
    });
  }

  useEffect(() => {
    load();

    const timer =
      window.setInterval(
        load,
        30000,
      );

    return () =>
      window.clearInterval(timer);
  }, []);

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
        )
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
      "09:15",
      "10:15",
      "11:15",
      "12:15",
      "13:15",
      "14:15",
      "15:15",
      "16:05",
    ];

  function close() {
    setPanel(null);
    setSymbol(null);
  }

  return (
    <>
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
          <aside className="v122-drawer">
            <header>
              <div>
                <span>
                  INTERACTIVE DETAILS
                </span>
                <h2>
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
                    Current regime
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
                <div className="v122-copy">
                  Open positions:{" "}
                  {
                    data.dashboard
                      ?.positions
                      ?.length ??
                    0
                  }
                </div>
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
                </div>
              )}

              {panel ===
                "orders" && (
                <OrderList
                  orders={orders}
                />
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

              {panel ===
                "orders" &&
                !orders.length && (
                  <div className="v122-copy">
                    No paper orders yet.
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

function OrderList({
  orders,
}: {
  orders: any[];
}) {
  return (
    <div className="v122-list">
      {orders.map(
        (order: any) => (
          <div
            className="v122-order"
            key={order.id}
          >
            <div>
              <strong>
                {order.symbol}
              </strong>
              <span>
                Score {order.score}
              </span>
            </div>

            <div>
              <b>
                {order.status}
              </b>
              <small>
                {
                  order.reason ??
                  "—"
                }
              </small>
            </div>
          </div>
        ),
      )}
    </div>
  );
}
