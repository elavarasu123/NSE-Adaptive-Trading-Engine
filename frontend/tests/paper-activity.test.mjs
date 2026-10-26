import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server, components;
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: "custom" });
  components = await server.ssrLoadModule("/src/PaperActivity.tsx");
});
after(async () => { await server?.close(); });

const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const errors = { trades: null, orders: null, positions: null };

test("empty trade history explains the distinction from rejected predictions", () => {
  const html = render(components.default, {
    trades: [], orders: [], positions: [], errors, refreshing: false,
    onOpen() {}, onRefresh() {},
  });
  assert.match(html, /No buy or sell fills recorded/);
  assert.match(html, /Rejected orders do not create fills/);
  assert.match(html, /Recent trade fills/);
  assert.match(html, /Order decisions/);
  assert.match(html, /Open positions/);
});

test("API failure is unavailable evidence, not an empty account", () => {
  const html = render(components.default, {
    trades: null, orders: null, positions: null,
    errors: { trades: "Trade history could not be loaded.", orders: "Order decisions could not be loaded.", positions: "Open positions could not be loaded." },
    refreshing: false, onOpen() {}, onRefresh() {},
  });
  assert.match(html, /role="alert"/);
  assert.match(html, /Unavailable/);
  assert.match(html, /Trade history could not be loaded/);
  assert.doesNotMatch(html, /No buy or sell fills recorded/);
});

test("initial pending data does not claim zero trades", () => {
  const html = render(components.default, {
    trades: null, orders: null, positions: null, errors, refreshing: true,
    onOpen() {}, onRefresh() {},
  });
  assert.match(html, /Loading paper activity/);
  assert.doesNotMatch(html, /No buy or sell fills recorded/);
});

test("buy and sell fills show quantities, prices and correct realized P&L semantics", () => {
  const html = render(components.TradeList, { trades: [
    { id: 1, symbol: "TCS", side: "BUY", quantity: 3, price: 1000, value: 3000, realizedPnl: 0, reason: "AUTO_FROZEN_PREDICTION", createdAt: "2026-10-26T04:30:00" },
    { id: 2, symbol: "TCS", side: "SELL", quantity: 3, price: 900, value: 2700, realizedPnl: -300, reason: "STOP_LOSS", createdAt: "2026-10-26T05:30:00Z" },
  ] });
  assert.match(html, /BUY/); assert.match(html, /SELL/);
  assert.match(html, /₹1,000/); assert.match(html, /-₹300/);
  assert.match(html, /10:00 am IST/i); // naive backend UTC converted explicitly
  assert.match(html, /Realized P&amp;L<\/dt><dd>—/);
});

test("PANIC rejection remains inspectable and missing fill price is not zero", () => {
  const html = render(components.OrderList, { orders: [
    { id: 1, symbol: "TCS", predictionDate: "2026-10-23", score: 99, regime: "PANIC", status: "REJECTED", quantity: 0, fillPrice: null, stop: null, target: null, entryFee: 0, exitPrice: null, exitFee: 0, realizedPnl: 0, reason: "PANIC_REGIME_BLOCK" },
  ] });
  assert.match(html, /Entry blocked by the PANIC regime/);
  assert.match(html, /View order details/);
  assert.match(html, /Fill price<\/dt><dd>—/);
  assert.match(html, /PANIC_REGIME_BLOCK/);
});

test("open positions show stops, targets and unrealized P&L", () => {
  const html = render(components.PositionList, { positions: [
    { symbol: "TCS", quantity: 3, entry: 1000, current: 1100, stop: 950, target: 1100 },
  ] });
  assert.match(html, /Stop/); assert.match(html, /Target/);
  assert.match(html, /Unrealized P&amp;L<\/dt><dd>₹300/);
});
