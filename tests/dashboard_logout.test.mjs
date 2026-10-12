import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";

const source = fs.readFileSync(new URL("../dashboard/src/App.jsx", import.meta.url), "utf8");
const handler = source.match(/  async function signOut\(\) \{[\s\S]*?\n  \}/)?.[0];
assert.ok(handler, "Dashboard logout handler exists");

for (const [name, failure, shouldRedirect] of [
  ["successful logout opens login", null, true],
  ["expired session opens login", { status: 401 }, true],
  ["server failure preserves the dashboard and shows an error", { status: 503 }, false],
  ["network failure preserves the dashboard and shows an error", new Error("network"), false],
  ["CSRF failure preserves the dashboard and shows an error", { status: 403 }, false],
]) {
  test(name, async () => {
    const destinations = [];
    const messages = [];
    const context = vm.createContext({
      api: async () => { if (failure) throw failure; },
      showToast: message => messages.push(message),
      window: { location: { replace: destination => destinations.push(destination) } },
    });
    vm.runInContext(handler, context);
    await context.signOut();
    assert.deepEqual(destinations, shouldRedirect ? ["/login"] : []);
    assert.equal(messages.length, shouldRedirect ? 0 : 1);
  });
}
