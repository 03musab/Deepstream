/* In-memory stand-in for `@netlify/blobs` (redirected to this file by
   blobs-loader.mjs). Mirrors the parts of the getStore() API that
   netlify/functions/_shared/cashfree.mjs uses, so tests need no Netlify
   deployment, credentials, or an npm install. */

const stores = new Map();

export function getStore({ name }) {
  if (!stores.has(name)) stores.set(name, new Map());
  const map = stores.get(name);
  return {
    get: async (key) => (map.has(key) ? map.get(key) : null),
    set: async (key, value) => {
      map.set(key, String(value));
    },
    delete: async (key) => {
      map.delete(key);
    },
  };
}

// Test helper: wipe all stores between tests.
export function __resetStores() {
  stores.clear();
}
