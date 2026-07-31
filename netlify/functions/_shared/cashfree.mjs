/* Shared Cashfree + Telegram + storage helpers for Deepstream Netlify Functions.
   Mirrors the logic in deepstream/payments.py so the Python server (local dev)
   and the Netlify Functions (production) behave identically. */

import { getStore } from "@netlify/blobs";
import { createHmac, timingSafeEqual } from "node:crypto";

export const INVITE_TTL_SECONDS = 30 * 24 * 3600; // 30 days

const STORE_NAME = "deepstream-payments";
const STATE_KEY = "state";

export const env = (name, fallback = "") => process.env[name] || fallback;

export const GRANT_STATUSES = new Set(["paid"]);
export const REVOKE_STATUSES = new Set(["failed", "cancelled", "refunded"]);

// Origin we are willing to share data with (from CASHFREE_SITE_URL). When
// unset, cross-origin browser requests are refused entirely.
const allowedOrigin = () => {
  try {
    return new URL(env("CASHFREE_SITE_URL", "")).origin;
  } catch {
    return "";
  }
};

export const json = (body, status = 200, req) => {
  const headers = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  };
  const trusted = allowedOrigin();
  const origin = (req?.headers && req.headers.get("origin")) || "";
  if (trusted && origin && origin.trim().toLowerCase() === trusted) {
    headers["Access-Control-Allow-Origin"] = trusted;
    headers["Vary"] = "Origin";
  }
  return new Response(JSON.stringify(body), { status, headers });
};

// ---------------------------------------------------------------------------
// Input validation (never trust the client alone)
// ---------------------------------------------------------------------------

export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export const ORDER_ID_RE = /^ds_[0-9a-f]{16}$/;

export const validEmail = (value) =>
  typeof value === "string" &&
  value.length > 0 &&
  value.length <= 254 &&
  EMAIL_RE.test(value);

export const validOrderId = (value) =>
  typeof value === "string" && value.length <= 64 && ORDER_ID_RE.test(value);

// ---------------------------------------------------------------------------
// Best-effort in-memory burst limiter (per warm instance). Production should
// add an edge-level (CDN/WAF) rate limit in front of the functions too.
// ---------------------------------------------------------------------------

const hitCounters = new Map();

export function rateLimited(key, max = 20, windowMs = 60_000) {
  const now = Date.now();
  const hit = hitCounters.get(key) || { times: [] };
  hit.times = hit.times.filter((t) => now - t < windowMs);
  if (hit.times.length >= max) {
    hitCounters.set(key, hit);
    return true;
  }
  hit.times.push(now);
  hitCounters.set(key, hit);
  return false;
}

/* ---------------------------------------------------------------------------
   Cashfree API (server-side only)
--------------------------------------------------------------------------- */

export const apiBase = () =>
  env("CASHFREE_ENV", "sandbox").toLowerCase() === "production"
    ? "https://api.cashfree.com"
    : "https://sandbox.cashfree.com";

export const DEFAULT_API_VERSION = "2023-08-01";

export async function cashfreeRequest(method, path, payload) {
  const clientId = env("CASHFREE_CLIENT_ID");
  const clientSecret = env("CASHFREE_CLIENT_SECRET");
  if (!clientId || !clientSecret) {
    throw new Error("Cashfree credentials are not configured");
  }
  const res = await fetch(`${apiBase()}${path}`, {
    method,
    headers: {
      "x-api-version": env("CASHFREE_API_VERSION", DEFAULT_API_VERSION),
      "x-client-id": clientId,
      "x-client-secret": clientSecret,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`Cashfree ${method} ${path} failed: ${res.status}`);
  }
  return body;
}

export async function fetchOrder(orderId) {
  return cashfreeRequest("GET", `/pg/orders/${encodeURIComponent(orderId)}`);
}

export function paymentsConfig() {
  return {
    configured: Boolean(env("CASHFREE_CLIENT_ID") && env("CASHFREE_CLIENT_SECRET")),
    mode: env("CASHFREE_ENV", "sandbox").toLowerCase(),
    amount: Number(env("CASHFREE_ORDER_AMOUNT", "29")),
    currency: env("CASHFREE_ORDER_CURRENCY", "USD"),
  };
}

/* ---------------------------------------------------------------------------
   Webhook signature verification
--------------------------------------------------------------------------- */

export function verifyWebhookSignature(rawBody, headers) {
  const secret = env("CASHFREE_WEBHOOK_SECRET");
  const signature = headers.get("x-webhook-signature") || "";
  const timestamp = headers.get("x-webhook-timestamp") || "";
  if (!secret || !signature) return false;

  // Cashfree has shipped both body-only and timestamp+body signature schemes
  // (some versions insert a separator). Accept the documented variants.
  const candidates = [rawBody];
  if (timestamp) candidates.push(timestamp + rawBody, timestamp + "." + rawBody);
  const received = Buffer.from(signature, "utf8");
  for (const message of candidates) {
    const expected = createHmac("sha256", secret).update(message).digest("base64");
    const computed = Buffer.from(expected, "utf8");
    if (computed.length === received.length && timingSafeEqual(computed, received)) {
      return true;
    }
  }
  return false;
}

/* ---------------------------------------------------------------------------
   Telegram invite link helpers
--------------------------------------------------------------------------- */

async function telegramPost(method, data) {
  const token = env("DEEPSTREAM_BOT_TOKEN");
  if (!token) throw new Error("DEEPSTREAM_BOT_TOKEN is not configured");
  const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(data).toString(),
  });
  const body = await res.json();
  if (!body.ok) throw new Error(`Telegram ${method} failed: ${body.description}`);
  return body;
}

export async function createChannelInvite(chatId) {
  const payload = await telegramPost("createChatInviteLink", {
    chat_id: chatId,
    member_limit: 1,
    expire_date: Math.floor(Date.now() / 1000) + INVITE_TTL_SECONDS,
  });
  return payload.result.invite_link;
}

export async function revokeChannelInvite(chatId, inviteLink) {
  await telegramPost("revokeChatInviteLink", { chat_id: chatId, invite_link: inviteLink });
}

/* ---------------------------------------------------------------------------
   Storage (Netlify Blobs)
--------------------------------------------------------------------------- */

async function loadState() {
  const raw = await getStore({ name: STORE_NAME }).get(STATE_KEY);
  if (!raw) return { orders: {}, processed_events: {} };
  try {
    return JSON.parse(raw);
  } catch {
    return { orders: {}, processed_events: {} };
  }
}

async function saveState(state) {
  await getStore({ name: STORE_NAME }).set(STATE_KEY, JSON.stringify(state));
}

/* ---------------------------------------------------------------------------
   Access lookup
--------------------------------------------------------------------------- */

export async function accessForOrder(orderId) {
  const state = await loadState();
  const order = state.orders[orderId];
  if (!order) return { status: "pending", message: "Order not yet seen." };
  if (GRANT_STATUSES.has(order.status) && order.invite_link) {
    return {
      status: "granted",
      invite_link: order.invite_link,
      expires_at: order.invite_expires_at,
    };
  }
  if (REVOKE_STATUSES.has(order.status)) {
    return { status: "revoked", message: "Payment failed or was refunded." };
  }
  return { status: "pending", message: "Processing payment…" };
}

/* ---------------------------------------------------------------------------
   Webhook event handling
--------------------------------------------------------------------------- */

// Include common legacy/alias names defensively so grants/revocations are not
// silently dropped if Cashfree delivers a differently-named variant.
const GRANT_TYPES = new Set(["ORDER_PAID", "PAYMENT_SUCCESS_WEBHOOK"]);
const REVOKE_TYPES = new Set([
  "REFUND_STATUS", "REFUND_STATUS_CHANGE",
  "REFUND_STATUS_WEBHOOK", "REFUND_SUCCESS",
]);
const FAIL_TYPES = new Set([
  "ORDER_FAILED", "ORDER_CANCELLED", "PAYMENT_FAILED",
  "PAYMENT_FAILED_WEBHOOK",
]);

function orderIdFromEvent(event) {
  const data = event.data || {};
  const order = data.order || {};
  const refund = data.refund || {};
  return String(order.order_id || data.order_id || refund.order_id || "");
}

export async function handleWebhookEvent(event) {
  const state = await loadState();
  const type = event.type || "";
  const data = event.data || {};
  const order = data.order || {};
  const customer = data.customer_details || {};
  const orderId = orderIdFromEvent(event);
  const occurredAt = event.event_time || event.created_at || "";
  const eventId = `${type}:${orderId}`;

  if (!orderId) return `ignored ${type} (no order_id)`;
  if (state.processed_events[eventId]) return `duplicate ${eventId}`;

  if (GRANT_TYPES.has(type)) {
    const fetched = await fetchOrder(orderId); // throws → 500 → Cashfree retries
    if (fetched.order_status !== "PAID") {
      state.processed_events[eventId] = occurredAt;
      await saveState(state);
      return `rejected ${type} (order not PAID)`;
    }
    const expectedAmount = Number(env("CASHFREE_ORDER_AMOUNT", "29"));
    const expectedCurrency = env("CASHFREE_ORDER_CURRENCY", "USD");
    if (Number(fetched.order_amount) !== expectedAmount) {
      state.processed_events[eventId] = occurredAt;
      await saveState(state);
      return `rejected ${type} (amount mismatch)`;
    }
    if (fetched.order_currency !== expectedCurrency) {
      state.processed_events[eventId] = occurredAt;
      await saveState(state);
      return `rejected ${type} (currency mismatch)`;
    }
    await grant(state, orderId, {
      cfOrderId: String(fetched.cf_order_id || order.cf_order_id || ""),
      customerEmail: customer.customer_email || (fetched.customer_details || {}).customer_email,
      amount: fetched.order_amount,
      currency: fetched.order_currency,
      occurredAt,
    });
    state.processed_events[eventId] = occurredAt;
    await saveState(state);
    return `processed ${type} ${orderId}`;
  }

  if (REVOKE_TYPES.has(type)) {
    const refund = data.refund || {};
    if (refund.refund_status && !["SUCCESS", "PENDING"].includes(refund.refund_status)) {
      state.processed_events[eventId] = occurredAt;
      await saveState(state);
      return `ignored ${type} (refund not successful)`;
    }
    await revoke(state, orderId, occurredAt);
    state.processed_events[eventId] = occurredAt;
    await saveState(state);
    return `processed ${type} ${orderId}`;
  }

  if (FAIL_TYPES.has(type)) {
    await markFailed(state, orderId, customer.customer_email, occurredAt);
    state.processed_events[eventId] = occurredAt;
    await saveState(state);
    return `processed ${type} ${orderId}`;
  }

  state.processed_events[eventId] = occurredAt;
  await saveState(state);
  return `ignored ${type}`;
}

async function grant(state, orderId, { cfOrderId, customerEmail, amount, currency, occurredAt }) {
  const existing = state.orders[orderId] || {};
  if (GRANT_STATUSES.has(existing.status) && existing.invite_link) {
    return existing.invite_link;
  }

  const token = env("DEEPSTREAM_BOT_TOKEN");
  const proChannel = env("DEEPSTREAM_PRO_CHANNEL_ID");
  let inviteLink = null;
  let inviteExpiresAt = null;
  if (token && proChannel) {
    inviteLink = await createChannelInvite(proChannel);
    inviteExpiresAt = new Date(Date.now() + INVITE_TTL_SECONDS * 1000).toISOString();
  } else {
    console.warn("Pro channel not configured — cannot mint invite link");
  }

  const now = new Date().toISOString();
  state.orders[orderId] = {
    order_id: orderId,
    cf_order_id: cfOrderId || existing.cf_order_id || "",
    customer_id: existing.customer_id || "",
    customer_email: customerEmail || existing.customer_email,
    status: "paid",
    amount: amount ?? existing.amount,
    currency: currency || existing.currency,
    invite_link: inviteLink,
    invite_expires_at: inviteExpiresAt,
    created_at: existing.created_at || now,
    updated_at: now,
    occurred_at: occurredAt || existing.occurred_at,
  };
  await saveState(state);
  return inviteLink;
}

async function markFailed(state, orderId, customerEmail, occurredAt) {
  const existing = state.orders[orderId] || {};
  const now = new Date().toISOString();
  state.orders[orderId] = {
    ...existing,
    customer_email: customerEmail || existing.customer_email,
    status: "failed",
    updated_at: now,
    occurred_at: occurredAt || existing.occurred_at,
  };
  await saveState(state);
}

async function revoke(state, orderId, occurredAt) {
  const order = state.orders[orderId];
  if (!order) return;
  const token = env("DEEPSTREAM_BOT_TOKEN");
  const proChannel = env("DEEPSTREAM_PRO_CHANNEL_ID");
  if (order.invite_link && token && proChannel) {
    try {
      await revokeChannelInvite(proChannel, order.invite_link);
    } catch (err) {
      console.error(`Failed to revoke invite link for ${orderId}`, err);
    }
  }
  order.invite_link = null;
  order.invite_expires_at = null;
  order.status = "refunded";
  order.updated_at = new Date().toISOString();
  order.occurred_at = occurredAt || order.occurred_at;
  await saveState(state);
}
