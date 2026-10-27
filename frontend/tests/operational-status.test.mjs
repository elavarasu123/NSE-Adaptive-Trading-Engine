import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
let server, Card;
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  Card = (await server.ssrLoadModule('/src/OperationalStatus.tsx')).default;
});
after(async () => { await server?.close(); });
const render = operations => renderToStaticMarkup(React.createElement(Card, {
  operations, dataStatus: 'FRESH', integrityStatus: 'OK',
}));
const operations = {
  checkedAt: '2026-10-27T04:15:00Z',
  execution: { status: 'OVERDUE', lastSuccessfulAt: '2026-10-26T10:38:58Z',
    expectedCycleAt: '2026-10-27T03:50:00Z', nextExpectedAt: '2026-10-27T04:50:00Z' },
  scheduler: { status: 'UNVERIFIED', lastRunEvent: 'workflow_dispatch', detail: 'Manual runs do not prove schedule delivery.' },
  monitoring: { status: 'UNCONFIGURED' },
};
test('fresh prices and healthy account cannot conceal overdue execution', () => {
  const html = render(operations);
  assert.match(html, /OVERDUE/); assert.match(html, /role="alert"/);
  assert.match(html, /Settled data: FRESH/); assert.match(html, /Integrity: OK/);
  assert.match(html, /Healthy saved data does not mean the engine ran on schedule/);
  assert.match(html, /9:20 am IST/i);
});
test('manual current execution never becomes confirmed automatic scheduling', () => {
  const html = render({ ...operations, execution: { ...operations.execution, status: 'CURRENT' } });
  assert.doesNotMatch(html, /role="alert"/); assert.match(html, /UNVERIFIED/);
  assert.match(html, /workflow_dispatch/); assert.match(html, /UNCONFIGURED/);
});
test('unknown operational evidence is explicitly unavailable', () => {
  assert.match(render(undefined), /UNKNOWN/);
  assert.match(render(undefined), /current successful execution is not confirmed/);
});
