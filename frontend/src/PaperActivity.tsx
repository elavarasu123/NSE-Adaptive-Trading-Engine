import React from "react";

export type PaperTrade = {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  value: number;
  realizedPnl: number;
  reason: string | null;
  createdAt: string;
};

export type PaperOrder = {
  id: number;
  symbol: string;
  predictionDate: string;
  score: number;
  regime: string;
  status: string;
  quantity: number;
  fillPrice: number | null;
  stop: number | null;
  target: number | null;
  entryFee: number | null;
  exitPrice: number | null;
  exitFee: number | null;
  realizedPnl: number | null;
  reason: string | null;
};

export type PaperPosition = {
  symbol: string;
  quantity: number;
  entry: number;
  current: number;
  stop: number;
  target: number;
};

export type TradingErrors = {
  trades: string | null;
  orders: string | null;
  positions: string | null;
};

export function money(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR", maximumFractionDigits: 2,
  }).format(value);
}

function recordedAt(value: string) {
  // SQLite may serialize naive UTC timestamps; never interpret these as
  // the phone's local timezone before converting to IST.
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (!Number.isFinite(date.getTime())) return "Time unavailable";
  return `${new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short",
  }).format(date)} IST`;
}

function reason(value: string | null) {
  if (value === "PANIC_REGIME_BLOCK") return "Entry blocked by the PANIC regime.";
  if (value === "BATCH_ENTRY_CAP") return "The batch entry limit was reached.";
  if (value === "POSITION_ALREADY_OPEN") return "A position in this stock is already open.";
  if (value === "MODEL_NOT_CHAMPION") return "This prediction is not from the approved champion.";
  if (value?.startsWith("BELOW_ADAPTIVE_THRESHOLD:")) return `Score is below the validated adaptive threshold of ${value.split(":")[1]}.`;
  if (value?.startsWith("BELOW_REGIME_THRESHOLD:")) {
    return `Score is below the regime threshold of ${value.split(":")[1]}.`;
  }
  if (value?.startsWith("RISK_GATE:")) return `Risk check: ${value.slice(10)}`;
  if (value === "AUTO_FROZEN_PREDICTION") return "Automatic paper entry from a frozen prediction.";
  if (value === "STOP_LOSS") return "Stop-loss exit.";
  if (value === "TARGET") return "Target exit.";
  return value || "No reason recorded.";
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

export function TradingState({ error, pending, children }: {
  error: string | null; pending: boolean; children: React.ReactNode;
}) {
  if (error) return <p className="paper-message paper-error" role="alert">{error} Use Refresh to retry.</p>;
  if (pending) return <p className="paper-message" role="status">Loading paper activity…</p>;
  return <>{children}</>;
}

export function TradeList({ trades }: { trades: PaperTrade[] }) {
  if (!trades.length) return (
    <div className="paper-message">
      <strong>No buy or sell fills recorded.</strong>
      <p>Predictions are observations, not executed trades. Rejected orders do not create fills.
        Open Order decisions to see why an entry was blocked.</p>
    </div>
  );
  return <div className="paper-records">{trades.map(trade => (
    <article className="paper-record" key={trade.id}>
      <div className="paper-record-title"><strong>{trade.symbol}</strong>
        <span className="paper-badge">{trade.side}</span></div>
      <time dateTime={trade.createdAt}>{recordedAt(trade.createdAt)}</time>
      <dl className="paper-facts">
        <Fact label="Quantity" value={trade.quantity} />
        <Fact label="Fill price" value={money(trade.price)} />
        <Fact label="Trade value" value={money(trade.value)} />
        <Fact label="Realized P&L" value={trade.side === "SELL" ? money(trade.realizedPnl) : "—"} />
      </dl>
      <p className="paper-reason">{reason(trade.reason)}</p>
    </article>
  ))}</div>;
}

export function OrderList({ orders }: { orders: PaperOrder[] }) {
  if (!orders.length) return <p className="paper-message">No automatic paper-order decisions recorded yet.</p>;
  return <div className="paper-records">{orders.map(order => (
    <article className="paper-record" key={order.id}>
      <div className="paper-record-title"><strong>{order.symbol}</strong>
        <span className={`paper-badge ${order.status === "REJECTED" ? "paper-rejected" : ""}`}>
          {order.status}
        </span></div>
      <p className="paper-reason">{reason(order.reason)}</p>
      <details>
        <summary>View order details</summary>
        <dl className="paper-facts">
          <Fact label="Prediction date" value={order.predictionDate} />
          <Fact label="Score / regime" value={`${order.score} / ${order.regime}`} />
          <Fact label="Quantity" value={order.quantity} />
          <Fact label="Fill price" value={money(order.fillPrice)} />
          <Fact label="Stop" value={money(order.stop)} />
          <Fact label="Target" value={money(order.target)} />
          <Fact label="Entry fee" value={money(order.entryFee)} />
          <Fact label="Exit price" value={money(order.exitPrice)} />
          <Fact label="Exit fee" value={money(order.exitFee)} />
          <Fact label="Realized P&L" value={order.status === "CLOSED" ? money(order.realizedPnl) : "—"} />
        </dl>
        <p className="paper-reason">Recorded reason: {order.reason || "—"}</p>
      </details>
    </article>
  ))}</div>;
}

export function PositionList({ positions }: { positions: PaperPosition[] }) {
  if (!positions.length) return <p className="paper-message">No open paper positions.</p>;
  return <div className="paper-records">{positions.map(position => (
    <article className="paper-record" key={position.symbol}>
      <div className="paper-record-title"><strong>{position.symbol}</strong>
        <span className="paper-badge">OPEN</span></div>
      <dl className="paper-facts">
        <Fact label="Quantity" value={position.quantity} />
        <Fact label="Entry" value={money(position.entry)} />
        <Fact label="Current mark" value={money(position.current)} />
        <Fact label="Unrealized P&L" value={money((position.current - position.entry) * position.quantity)} />
        <Fact label="Stop" value={money(position.stop)} />
        <Fact label="Target" value={money(position.target)} />
      </dl>
    </article>
  ))}</div>;
}

export default function PaperActivity({ trades, orders, positions, errors, refreshing, onOpen, onRefresh }: {
  trades: PaperTrade[] | null;
  orders: PaperOrder[] | null;
  positions: PaperPosition[] | null;
  errors: TradingErrors;
  refreshing: boolean;
  onOpen: (panel: "trades" | "orders" | "portfolio") => void;
  onRefresh: () => void;
}) {
  const counts = [
    { panel: "trades" as const, label: "Recent trade fills", rows: trades, error: errors.trades },
    { panel: "orders" as const, label: "Order decisions", rows: orders, error: errors.orders },
    { panel: "portfolio" as const, label: "Open positions", rows: positions, error: errors.positions },
  ];
  return (
    <section id="paper-trading" className="card paper-trading-section" aria-labelledby="paper-activity-title">
      <div className="v122-title"><div><span>PAPER ACCOUNT</span>
        <h2 id="paper-activity-title">Trades &amp; orders</h2></div>
        <button type="button" disabled={refreshing} onClick={onRefresh}>
          {refreshing ? "Refreshing…" : "Refresh activity"}
        </button></div>
      <div className="paper-counts">{counts.map(item => (
        <button type="button" key={item.panel} onClick={() => onOpen(item.panel)}>
          <span>{item.label}</span><strong>{item.error ? "Unavailable" : item.rows?.length ?? "…"}</strong>
          <small>Tap to inspect →</small>
        </button>
      ))}</div>
      <h3>Latest buy / sell fills</h3>
      <p className="paper-caption">Trade history shows up to 200 recent fills; an entry and exit are separate records.
        Order decisions show up to 100 automatic orders, including rejections.</p>
      <TradingState error={errors.trades} pending={trades === null}>
        <TradeList trades={(trades || []).slice(0, 3)} />
      </TradingState>
      {trades && trades.length > 3 && <button className="paper-link" type="button" onClick={() => onOpen("trades")}>View trade history</button>}
      {orders?.[0] && <p className="paper-message">
        Latest order decision ({orders[0].predictionDate}): <strong>{orders[0].symbol} — {orders[0].status}</strong>
        <br />{reason(orders[0].reason)}
      </p>}
      {errors.orders && <p className="paper-message paper-error" role="alert">{errors.orders}</p>}
      {errors.positions && <p className="paper-message paper-error" role="alert">{errors.positions}</p>}
    </section>
  );
}
