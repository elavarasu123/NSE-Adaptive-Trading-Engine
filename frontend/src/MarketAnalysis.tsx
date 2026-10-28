import React from "react";
const indexValue = (value?: number) => value == null || !Number.isFinite(value)
  ? "—" : new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);

export type MarketAnalysis = {
  status: string; asOf: string | null; expectedSession?: string;
  source?: string; successful?: number; universeSize?: number;
  coverage?: { missing: number; insufficient: number; unaligned: number };
  dataQuality?: { status: string; exclusions: Array<{symbol: string; reason: string; rows?: number; latestSession?: string}> };
  regime: { name: string; buyThreshold?: number; reasons?: string[] };
  indicators?: { close: number; rsi14: number; vol20: number; mom1m: number; mom3m: number };
  benchmarkQuote?: { status: string; price?: number; observedAt?: string; changeFromSettledClose?: number };
  adaptivePolicy?: { status: string; revision: string; matured20D: number;
    regimes: Record<string, { status: string; baselineThreshold: number; effectiveThreshold: number;
      trainingDates: number; validationDates: number; reason: string }> };
};

function observedAt(value?: string) {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time unavailable";
  return new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }).format(date) + " IST";
}

export default function MarketAnalysisCard({ analysis }: { analysis: MarketAnalysis | null }) {
  if (!analysis || analysis.status === "UNAVAILABLE") return (
    <section className="card market-analysis" aria-label="Market analysis">
      <h2>Market analysis & learning</h2>
      <p>Real execution analysis is unavailable. The next successful engine cycle will record it.</p>
      <p>No demo stock recommendations are shown.</p>
    </section>
  );
  const quote = analysis.benchmarkQuote;
  const policy = analysis.adaptivePolicy;
  const current = policy?.regimes?.[analysis.regime.name];
  return <section className="card market-analysis" aria-label="Market analysis">
    <div className="section-head"><div><span className="section-kicker">MARKET & LEARNING</span>
      <h2>Market analysis & learning</h2></div><span className="paper-badge">{analysis.status}</span></div>
    <p>Settled daily analysis: <strong>{analysis.asOf}</strong>. Regime: <strong>{analysis.regime.name}</strong>.</p>
    {analysis.dataQuality?.status === "PARTIAL" && <p className="paper-message paper-error" role="alert">
      Market coverage is partial. Missing or stale stocks are excluded from signals.
    </p>}
    {analysis.status !== "AVAILABLE" && <p className="paper-message paper-error" role="alert">
      This analysis is out of date. Expected session: {analysis.expectedSession}. Entry signals are unavailable.
    </p>}
    <div className="market-analysis-grid">
      <div><h3>Nifty context</h3><p>Settled close: <strong>{indexValue(analysis.indicators?.close)}</strong></p>
        {quote?.status === "AVAILABLE" ? <p>Delayed observation: <strong>{indexValue(quote.price)}</strong>
          {quote.changeFromSettledClose != null && <> ({(quote.changeFromSettledClose * 100).toFixed(2)}% from settled close)</>}
          <br />{observedAt(quote.observedAt)}</p> : <p>A current delayed quote is unavailable.</p>}
        <p>{analysis.successful ?? "—"} / {analysis.universeSize ?? "—"} stocks have aligned, sufficient daily history.</p>
        {analysis.coverage && <p>Missing data: {analysis.coverage.missing}. Stale sessions: {analysis.coverage.unaligned}.
          Insufficient history or features: {analysis.coverage.insufficient}.</p>}
      </div>
      <div><h3>Why this regime</h3><ul>{analysis.regime.reasons?.map(reason => <li key={reason}>{reason}</li>)}</ul></div>
      <div><h3>Automatic paper adaptation</h3>
        <p>{policy?.matured20D ?? 0} eligible matured 20-session outcomes.</p>
        <p>{current?.status === "ACTIVE"
          ? `Validated entry threshold: ${current.effectiveThreshold} (baseline ${current.baselineThreshold}).`
          : "No validated threshold change is active for this regime."}</p>
        <p>{current?.reason ?? "Waiting for an execution-side learning report."}</p>
        <p>Changes update future paper entries after validation. Original predictions stay unchanged for comparison.</p>
      </div>
    </div>
    {!!analysis.dataQuality?.exclusions.length && <details><summary>Excluded stocks and reasons ({analysis.dataQuality.exclusions.length})</summary>
      <ul>{analysis.dataQuality.exclusions.map(item => <li key={item.symbol}>{item.symbol}: {item.reason.split("_").join(" ").toLowerCase()}
        {item.rows != null ? ` (${item.rows} sessions; 300 required)` : ""}
        {item.latestSession ? ` (latest ${item.latestSession})` : ""}</li>)}</ul>
    </details>}
    <p className="paper-message">Daily signals and delayed price observations have different timestamps. Scores are rankings, not win probabilities.</p>
  </section>;
}
