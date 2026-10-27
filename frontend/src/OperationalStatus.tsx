import React from 'react';

export type OperationalStatus = {
  checkedAt: string;
  execution: { status: string; lastSuccessfulAt: string | null; expectedCycleAt: string | null; nextExpectedAt: string | null };
  scheduler: { status: string; lastRunEvent: string; detail: string };
  monitoring: { status: string; detail: string };
};
const time = (value?: string | null) => {
  if (!value || Number.isNaN(new Date(value).getTime())) return 'Unavailable';
  return new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) + ' IST';
};

export default function OperationalStatusCard({ operations, dataStatus, integrityStatus }: {
  operations?: OperationalStatus; dataStatus?: string; integrityStatus?: string;
}) {
  const execution = operations?.execution;
  const blocked = !execution || ['OVERDUE', 'ERROR', 'DEGRADED', 'STALLED', 'NEVER_RUN', 'UNKNOWN'].includes(execution.status);
  return <section className="card market-analysis" aria-label="Operational health">
    <div className="section-head"><div><span className="section-kicker">OPERATIONAL HEALTH</span>
      <h2>Is the engine running on time?</h2></div><span className="paper-badge">{execution?.status ?? 'UNKNOWN'}</span></div>
    {blocked && <p className="paper-message paper-error" role="alert">A current successful execution is not confirmed. Healthy saved data does not mean the engine ran on schedule.</p>}
    <div className="market-analysis-grid">
      <div><h3>Execution: {execution?.status ?? 'UNKNOWN'}</h3>
        <p>Last success: {time(execution?.lastSuccessfulAt)}</p>
        <p>Expected cycle: {time(execution?.expectedCycleAt)}</p>
        <p>Next slot: {time(execution?.nextExpectedAt)}</p></div>
      <div><h3>Data & account checks</h3><p>Settled data: {dataStatus ?? 'UNKNOWN'}</p>
        <p>Integrity: {integrityStatus ?? 'UNKNOWN'}</p>
        <p>These checks are independent of execution timing.</p></div>
      <div><h3>Schedule: {operations?.scheduler.status ?? 'UNVERIFIED'}</h3>
        <p>Last event: {operations?.scheduler.lastRunEvent ?? 'UNKNOWN'}</p>
        <p>{operations?.scheduler.detail ?? 'No schedule evidence is available.'}</p>
        <p>Independent alerts: {operations?.monitoring.status ?? 'UNCONFIGURED'}. No external notification service is connected.</p></div>
    </div>
  </section>;
}
