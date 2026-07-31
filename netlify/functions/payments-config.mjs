/* GET /api/payments_config
   Public-safe config the landing page needs to initialize the Cashfree JS SDK
   (mode: sandbox | production, plus the displayed amount/currency). */

import { json, paymentsConfig } from "./_shared/cashfree.mjs";

export default async () => json(paymentsConfig());
