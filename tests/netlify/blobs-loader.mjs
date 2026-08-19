/* Custom Node ESM loader: redirects the "@netlify/blobs" import used by the
   Netlify functions to the in-memory stub (blob-stub.mjs) so the JS tests run
   hermetically — no Netlify deployment, no credentials, no npm install.

   Used by `npm test`:
     node --experimental-loader ./tests/netlify/blobs-loader.mjs --test tests/netlify/

   Works on Node 18.6+ (the declared runtime for the Netlify Functions). */

const BLOB_STUB_URL = new URL("./blob-stub.mjs", import.meta.url).href;

export async function resolve(specifier, context, nextResolve) {
  if (specifier === "@netlify/blobs") {
    return { url: BLOB_STUB_URL, shortCircuit: true };
  }
  return nextResolve(specifier, context);
}
