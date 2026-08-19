/* Tests for netlify/functions/_shared/cashfree.mjs — the shared module behind
   the create-order / cashfree-webhook / access Netlify functions. Mirrors the
   Python coverage in tests/test_payments.py.

   Run with the built-in node:test runner and the blobs loader:
     npm test
   (equivalent: node --experimental-loader ./tests/netlify/blobs-loader.mjs
   --test tests/netlify/*.test.mjs). The unquoted glob is expanded by bash in
   CI on any Node, and natively by Node 21+ on Windows cmd.
*/

import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, it } from "node:test";

import {
  accessForOrder,
  handleWebhookEvent,
  verifyWebhookSignature,
} from "../../netlify/functions/_shared/cashfree.mjs";
import { __resetStores } from "./blob-stub.mjs";

const INVITE_LINK = "https://t.me/+testinvite";

// Unique order ids per test so the shared 5s provider-check cache in
// accessForOrder never leaks between tests.
let uid = 0;
const uniqueOrderId = () => "ds_" + (++uid).toString(16).padStart(16, "0");

const paidOrder = (id) => ({
  order_id: id,
  cf_order_id: "1234567890",
  order_status: "PAID",
  order_amount: 2499,
  order_currency: "INR",
  customer_details: { customer_email: "pro@example.com" },
});

const ENV_KEYS = [
  "DEEPSTREAM_BOT_TOKEN",
  "DEEPSTREAM_PRO_CHANNEL_ID",
  "CASHFREE_CLIENT_ID",
  "CASHFREE_CLIENT_SECRET",
  "CASHFREE_ENV",
  "CASHFREE_WEBHOOK_SECRET",
  "CASHFREE_ORDER_AMOUNT",
  "CASHFREE_ORDER_CURRENCY",
];
let savedEnv = {};

beforeEach(() => {
  savedEnv = {};
  for (const key of ENV_KEYS) savedEnv[key] = process.env[key];
  process.env.DEEPSTREAM_BOT_TOKEN = "test-bot-token";
  process.env.DEEPSTREAM_PRO_CHANNEL_ID = "-1001234567890";
  process.env.CASHFREE_CLIENT_ID = "cf-client-id";
  process.env.CASHFREE_CLIENT_SECRET = "cf-client-secret";
  process.env.CASHFREE_ENV = "sandbox";
  process.env.CASHFREE_WEBHOOK_SECRET = "test-webhook-secret";
  process.env.CASHFREE_ORDER_AMOUNT = "2499";
  process.env.CASHFREE_ORDER_CURRENCY = "INR";
  __resetStores();
});

afterEach(() => {
  for (const key of ENV_KEYS) {
    if (savedEnv[key] === undefined) delete process.env[key];
    else process.env[key] = savedEnv[key];
  }
});

/* ------------------------------------------------------------------ */
/* fetch stub: routes Cashfree /pg/orders and Telegram API calls       */
/* ------------------------------------------------------------------ */

function installFetchStub({ orders = new Map(), throwFor = new Set() } = {}) {
  const realFetch = globalThis.fetch;
  const calls = { provider: 0, telegram: 0 };
  globalThis.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/pg/orders/")) {
      calls.provider += 1;
      const id = decodeURIComponent(u.split("/pg/orders/")[1]);
      if (throwFor.has(id)) throw new Error("provider unreachable");
      const body = orders.get(id);
      if (!body) {
        return new Response(
          JSON.stringify({ message: "order not found", code: "order_not_found" }),
          { status: 404 },
        );
      }
      return new Response(JSON.stringify(body), { status: 200 });
    }
    const telegramMethod = u.match(/\/bot[^/]+\/(\w+)/);
    if (telegramMethod) {
      calls.telegram += 1;
      if (telegramMethod[1] === "createChatInviteLink") {
        return new Response(
          JSON.stringify({ ok: true, result: { invite_link: INVITE_LINK } }),
          { status: 200 },
        );
      }
      if (telegramMethod[1] === "revokeChatInviteLink") {
        return new Response(JSON.stringify({ ok: true, result: true }), { status: 200 });
      }
      throw new Error(`unexpected telegram method: ${telegramMethod[1]}`);
    }
    throw new Error(`unexpected fetch url: ${u}`);
  };
  return {
    calls,
    restore() {
      globalThis.fetch = realFetch;
    },
  };
}

/* ------------------------------------------------------------------ */
/* verifyWebhookSignature (pure, mirrors TestSignatureVerification)    */
/* ------------------------------------------------------------------ */

describe("verifyWebhookSignature", () => {
  const secret = "test-webhook-secret";
  const timestamp = "1722400000";
  const rawBody = JSON.stringify({ type: "ORDER_PAID", data: {} });
  const sign = (message) =>
    createHmac("sha256", secret).update(message).digest("base64");
  const withHeaders = (sig, ts) =>
    new Headers({
      "x-webhook-signature": sig,
      ...(ts ? { "x-webhook-timestamp": ts } : {}),
    });

  it("accepts a body-only signature", () => {
    assert.equal(verifyWebhookSignature(rawBody, withHeaders(sign(rawBody))), true);
  });

  it("accepts timestamp+body signatures (both separator variants)", () => {
    assert.equal(
      verifyWebhookSignature(rawBody, withHeaders(sign(timestamp + rawBody), timestamp)),
      true,
    );
    assert.equal(
      verifyWebhookSignature(rawBody, withHeaders(sign(timestamp + "." + rawBody), timestamp)),
      true,
    );
  });

  it("rejects a signature from the wrong secret", () => {
    const bad = createHmac("sha256", "other-secret").update(rawBody).digest("base64");
    assert.equal(verifyWebhookSignature(rawBody, withHeaders(bad)), false);
  });

  it("rejects a tampered body", () => {
    const tampered = rawBody.replace("PAID", "FAILED");
    assert.equal(verifyWebhookSignature(tampered, withHeaders(sign(rawBody))), false);
  });

  it("rejects when the signature header is missing", () => {
    assert.equal(verifyWebhookSignature(rawBody, new Headers()), false);
  });

  it("accepts capitalized header names (Headers lookup is case-insensitive)", () => {
    const headers = new Headers({ "X-Webhook-Signature": sign(rawBody) });
    assert.equal(verifyWebhookSignature(rawBody, headers), true);
  });

  it("rejects when the webhook secret is not configured", () => {
    delete process.env.CASHFREE_WEBHOOK_SECRET;
    assert.equal(verifyWebhookSignature(rawBody, withHeaders(sign(rawBody))), false);
  });
});

/* ------------------------------------------------------------------ */
/* accessForOrder (provider fallback, mirrors TestSubscriptionStore)   */
/* ------------------------------------------------------------------ */

describe("accessForOrder", () => {
  it("returns pending when the provider cannot be reached yet", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({ throwFor: new Set([id]) });
    try {
      const result = await accessForOrder(id);
      assert.equal(result.status, "pending");
      assert.equal(stub.calls.provider, 1);
    } finally {
      stub.restore();
    }
  });

  it("grants directly when the provider says PAID and the webhook has not arrived", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({ orders: new Map([[id, paidOrder(id)]]) });
    try {
      const result = await accessForOrder(id);
      assert.equal(result.status, "granted");
      assert.equal(result.invite_link, INVITE_LINK);
      assert.equal(stub.calls.telegram, 1);

      // A second poll reuses the persisted grant — no duplicate invite minted.
      const again = await accessForOrder(id);
      assert.equal(again.status, "granted");
      assert.equal(stub.calls.telegram, 1);
    } finally {
      stub.restore();
    }
  });

  it("does not grant when the provider says PAID with a mismatched amount", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({
      orders: new Map([[id, { ...paidOrder(id), order_amount: 1 }]]),
    });
    try {
      const result = await accessForOrder(id);
      assert.equal(result.status, "pending");
      assert.equal(stub.calls.telegram, 0);
    } finally {
      stub.restore();
    }
  });

  it("does not grant when the provider says PAID with a mismatched currency", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({
      orders: new Map([[id, { ...paidOrder(id), order_currency: "USD" }]]),
    });
    try {
      const result = await accessForOrder(id);
      assert.equal(result.status, "pending");
      assert.equal(stub.calls.telegram, 0);
    } finally {
      stub.restore();
    }
  });

  it("returns pending when the provider says the order does not exist (404)", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({}); // no canned order → the stub answers 404
    try {
      const result = await accessForOrder(id);
      assert.equal(result.status, "pending");
      assert.equal(stub.calls.provider, 1);
    } finally {
      stub.restore();
    }
  });

  it("returns revoked for CANCELLED and EXPIRED orders", async () => {
    for (const order_status of ["CANCELLED", "EXPIRED"]) {
      const id = uniqueOrderId();
      const stub = installFetchStub({
        orders: new Map([
          [id, { order_id: id, order_status, order_amount: 2499, order_currency: "INR" }],
        ]),
      });
      try {
        assert.equal((await accessForOrder(id)).status, "revoked");
      } finally {
        stub.restore();
      }
    }
  });

  it("stays pending without minting an invite when Telegram is not configured", async () => {
    const id = uniqueOrderId();
    delete process.env.DEEPSTREAM_BOT_TOKEN;
    delete process.env.DEEPSTREAM_PRO_CHANNEL_ID;
    const stub = installFetchStub({ orders: new Map([[id, paidOrder(id)]]) });
    try {
      const result = await accessForOrder(id);
      assert.equal(result.status, "pending");
      assert.equal(stub.calls.telegram, 0);
    } finally {
      stub.restore();
    }
  });

  it("returns revoked when the provider says the order FAILED", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({
      orders: new Map([
        [id, { order_id: id, order_status: "FAILED", order_amount: 2499, order_currency: "INR" }],
      ]),
    });
    try {
      assert.equal((await accessForOrder(id)).status, "revoked");
      // State now records the failure — a second poll stays revoked.
      assert.equal((await accessForOrder(id)).status, "revoked");
    } finally {
      stub.restore();
    }
  });

  it("stays pending while the provider shows ACTIVE and throttles provider calls", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({
      orders: new Map([
        [id, { order_id: id, order_status: "ACTIVE", order_amount: 2499, order_currency: "INR" }],
      ]),
    });
    try {
      const result = await accessForOrder(id);
      assert.equal(result.status, "pending");
      // Provider polls are throttled (5s cache): an immediate second call
      // must not re-query Cashfree.
      const again = await accessForOrder(id);
      assert.equal(again.status, "pending");
      assert.equal(stub.calls.provider, 1);
    } finally {
      stub.restore();
    }
  });

  it("serves an already-processed grant from state without re-querying the provider", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({ orders: new Map([[id, paidOrder(id)]]) });
    try {
      const summary = await handleWebhookEvent({
        type: "ORDER_PAID",
        event_time: "2026-07-31T12:00:00Z",
        data: {
          order: { order_id: id },
          customer_details: { customer_email: "pro@example.com" },
        },
      });
      assert.match(summary, /processed/);
      const providerCallsBefore = stub.calls.provider;
      const result = await accessForOrder(id);
      assert.equal(result.status, "granted");
      assert.equal(stub.calls.provider, providerCallsBefore);
    } finally {
      stub.restore();
    }
  });
});

/* ------------------------------------------------------------------ */
/* handleWebhookEvent (mirrors the webhook grant/reject paths)         */
/* ------------------------------------------------------------------ */

describe("handleWebhookEvent", () => {
  const paidEvent = (id) => ({
    type: "ORDER_PAID",
    event_time: "2026-07-31T12:00:00Z",
    data: {
      order: { order_id: id },
      customer_details: { customer_email: "pro@example.com" },
    },
  });

  it("grants on a verified ORDER_PAID webhook", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({ orders: new Map([[id, paidOrder(id)]]) });
    try {
      const summary = await handleWebhookEvent(paidEvent(id));
      assert.match(summary, /processed/);
      assert.equal(stub.calls.telegram, 1);
      assert.equal((await accessForOrder(id)).status, "granted");
    } finally {
      stub.restore();
    }
  });

  it("rejects ORDER_PAID when the provider amount mismatches", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({
      orders: new Map([[id, { ...paidOrder(id), order_amount: 1 }]]),
    });
    try {
      const summary = await handleWebhookEvent(paidEvent(id));
      assert.match(summary, /rejected/);
      assert.equal(stub.calls.telegram, 0);
      assert.equal((await accessForOrder(id)).status, "pending");
    } finally {
      stub.restore();
    }
  });

  it("processes a duplicate ORDER_PAID webhook only once", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({ orders: new Map([[id, paidOrder(id)]]) });
    try {
      const event = paidEvent(id);
      await handleWebhookEvent(event);
      const summary = await handleWebhookEvent(event);
      assert.match(summary, /duplicate/);
      assert.equal(stub.calls.telegram, 1);
    } finally {
      stub.restore();
    }
  });

  it("marks the order failed on ORDER_FAILED", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({});
    try {
      const summary = await handleWebhookEvent({
        type: "ORDER_FAILED",
        event_time: "2026-07-31T13:00:00Z",
        data: { order: { order_id: id, order_status: "FAILED" } },
      });
      assert.match(summary, /processed/);
      assert.equal((await accessForOrder(id)).status, "revoked");
    } finally {
      stub.restore();
    }
  });

  it("revokes the invite link on a successful refund", async () => {
    const id = uniqueOrderId();
    const stub = installFetchStub({ orders: new Map([[id, paidOrder(id)]]) });
    try {
      // Grant first — mints the invite via createChatInviteLink.
      await handleWebhookEvent(paidEvent(id));
      assert.equal(stub.calls.telegram, 1);

      const summary = await handleWebhookEvent({
        type: "REFUND_STATUS",
        event_time: "2026-08-01T12:00:00Z",
        data: {
          order: { order_id: id },
          refund: { refund_status: "SUCCESS" },
        },
      });
      assert.match(summary, /processed/);
      // createChatInviteLink + revokeChatInviteLink = 2 Telegram calls.
      assert.equal(stub.calls.telegram, 2);
      assert.equal((await accessForOrder(id)).status, "revoked");
    } finally {
      stub.restore();
    }
  });
});
