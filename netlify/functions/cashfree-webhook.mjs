/* POST /webhooks/cashfree
   Cashfree sends signed webhooks (x-webhook-signature header). We verify the
   signature before processing ORDER_PAID / ORDER_FAILED / REFUND_STATUS etc.
   and mint/revoke the Telegram invite link accordingly. */

import { handleWebhookEvent, json, verifyWebhookSignature } from "./_shared/cashfree.mjs";

export default async (req) => {
  const rawBody = await req.text();

  if (!verifyWebhookSignature(rawBody, req.headers)) {
    console.warn("Cashfree webhook signature verification failed");
    return json({ error: "invalid signature" }, 401, req);
  }

  let event;
  try {
    event = JSON.parse(rawBody);
  } catch {
    return json({ error: "invalid body" }, 400, req);
  }
  if (!event || typeof event !== "object") {
    return json({ error: "empty body" }, 400, req);
  }

  try {
    const summary = await handleWebhookEvent(event);
    return json({ success: true, summary }, 200, req);
  } catch (err) {
    console.error("Failed to process Cashfree webhook", err);
    return json({ error: "processing failed" }, 500, req);
  }
};
