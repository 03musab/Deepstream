/* GET /api/access?order_id=...
   Returns the access state for an order so success.html can show the
   Telegram invite link once the ORDER_PAID webhook has been processed. */

import { accessForOrder, json } from "./_shared/cashfree.mjs";

export default async (req) => {
  const url = new URL(req.url);
  const orderId = (url.searchParams.get("order_id") || "").trim();
  if (!orderId) return json({ error: "order_id required" }, 400);
  return json(await accessForOrder(orderId));
};
