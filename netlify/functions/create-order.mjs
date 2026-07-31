/* POST /api/create-order
   Body: { customer_email, customer_phone }
   Creates a Cashfree order for one month of Pro access and returns
   { order_id, payment_session_id, order_status } for the JS SDK checkout. */

import { randomUUID } from "node:crypto";

import { cashfreeRequest, env, json } from "./_shared/cashfree.mjs";

export default async (req) => {
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);

  let payload = {};
  try {
    payload = await req.json();
  } catch {
    return json({ error: "invalid body" }, 400);
  }

  const customerEmail = String(payload.customer_email || "").trim();
  const customerPhone = String(payload.customer_phone || "").trim();
  if (!customerEmail) return json({ error: "customer_email required" }, 400);

  const orderId = "ds_" + randomUUID().replace(/-/g, "").slice(0, 16);
  const amount = Number(env("CASHFREE_ORDER_AMOUNT", "29"));
  const currency = env("CASHFREE_ORDER_CURRENCY", "USD");
  const siteUrl = env("CASHFREE_SITE_URL", "").replace(/\/+$/, "");

  const body = {
    order_id: orderId,
    order_amount: amount,
    order_currency: currency,
    order_note: "Deepstream Pro — 30 day access",
    customer_details: {
      customer_id: "cust_" + randomUUID().replace(/-/g, "").slice(0, 12),
      customer_email: customerEmail,
      customer_phone: customerPhone,
    },
  };
  if (siteUrl) body.order_meta = { return_url: `${siteUrl}/success.html` };

  try {
    const data = await cashfreeRequest("POST", "/pg/orders", body);
    return json({
      order_id: orderId,
      payment_session_id: data.payment_session_id || "",
      order_status: data.order_status || "",
    });
  } catch (err) {
    console.error("Create order failed", err);
    return json({ error: "order creation failed" }, 502);
  }
};
