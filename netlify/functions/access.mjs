/* GET /api/access?order_id=...
   Returns the access state for an order so success.html can show the
   Telegram invite link once the ORDER_PAID webhook has been processed. */

import { accessForOrder, json, rateLimited, validOrderId } from "./_shared/cashfree.mjs";

export default async (req) => {
  const url = new URL(req.url);
  const orderId = (url.searchParams.get("order_id") || "").trim();
  if (!validOrderId(orderId)) return json({ error: "order_id invalid" }, 400, req);

  // Per-IP limit (mirrors the Python backend's 240 req/min on /api/access).
  // Now that the access path can call out to the Cashfree API, an unthrottled
  // endpoint could be abused to drive provider calls.
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  if (rateLimited(`access:${ip}`, 240, 60_000)) {
    return json({ error: "too many requests" }, 429, req);
  }

  return json(await accessForOrder(orderId), 200, req);
};
