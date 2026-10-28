import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
let server, Card;
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  Card = (await server.ssrLoadModule('/src/MarketAnalysis.tsx')).default;
});
after(async () => { await server?.close(); });
const render = analysis => renderToStaticMarkup(React.createElement(Card, { analysis }));
const analysis = {
  status: 'AVAILABLE', asOf: '2026-10-23', expectedSession: '2026-10-23',
  successful: 74, universeSize: 501, regime: { name: 'PANIC', reasons: ['Nifty below 200DMA'] },
  indicators: { close: 25000 }, benchmarkQuote: { status: 'UNAVAILABLE' },
  adaptivePolicy: { matured20D: 0, regimes: { PANIC: { status: 'BLOCKED', reason: 'PANIC entry protection is never relaxed.' } } },
};
test('missing real analysis never becomes a demo recommendation', () => {
  assert.match(render(null), /Real execution analysis is unavailable/);
  assert.doesNotMatch(render(null), /TCS|BUY|25,000/);
});
test('market dates, actual coverage and insufficient learning are explicit', () => {
  const html = render(analysis);
  assert.match(html, /2026-10-23/); assert.match(html, /74 \/ 501 stocks/);
  assert.match(html, /No validated threshold change/); assert.match(html, /0 eligible matured/);
  assert.match(html, /Nifty below 200DMA/); assert.match(html, /current delayed quote is unavailable/);
});
test('stale analysis cannot be presented as current market evidence', () => {
  const html = render({ ...analysis, status: 'STALE', expectedSession: '2026-10-26' });
  assert.match(html, /role="alert"/); assert.match(html, /2026-10-26/);
  assert.match(html, /Entry signals are unavailable/);
});
test('partial coverage separates stale feeds from limited history and lists exclusions', () => {
  const html = render({ ...analysis,
    coverage: { missing: 1, insufficient: 1, unaligned: 1 },
    dataQuality: { status: 'PARTIAL', exclusions: [
      { symbol: 'SHORT', reason: 'INSUFFICIENT_HISTORY', rows: 150 },
      { symbol: 'OLD', reason: 'STALE', latestSession: '2026-10-22' },
    ] } });
  assert.match(html, /Market coverage is partial/);
  assert.match(html, /150 sessions; 300 required/);
  assert.match(html, /OLD: stale/);
  assert.match(html, /latest 2026-10-22/);
});
test('validated adaptive policy and delayed observation display independently', () => {
  const html = render({ ...analysis, regime: { name: 'RISK_ON' },
    benchmarkQuote: { status: 'AVAILABLE', price: 25100, observedAt: '2026-10-26T08:25:00Z', changeFromSettledClose: .004 },
    adaptivePolicy: { matured20D: 300, regimes: { RISK_ON: { status: 'ACTIVE', effectiveThreshold: 80, baselineThreshold: 75 } } } });
  assert.match(html, /Validated entry threshold: 80/); assert.match(html, /0.40% from settled close/);
  assert.match(html, /IST/); assert.match(html, /Original predictions stay unchanged/);
});
