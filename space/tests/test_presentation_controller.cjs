/* Synthetic controller regressions in memory. No browser, server or provider.
 * SPDX-License-Identifier: Apache-2.0 */
const assert = require('node:assert/strict');
const { createHash, webcrypto } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const html = fs.readFileSync(path.join(__dirname, '../c2/index.html'), 'utf8');
const start = html.indexOf("const chainEl = document.getElementById('chain');");
const end = html.indexOf('</script>', start);
assert.ok(start > 0 && end > start);
const controller = html.slice(start, end);

function sample() {
  let previous = '0'.repeat(64);
  const events = [0, 1].map(seq => {
    const event = { seq, t: seq, track: seq + 1, kind: 'spawn', r: 30, theta: 0, cls: 'unknown', truth: 'LOCAL_QA_SYNTHETIC' };
    const body = JSON.stringify(event, Object.keys(event).sort()).replace(/\s/g, '');
    const chainHash = createHash('sha256').update(previous + body).digest('hex');
    const result = { ...event, prev_hash: previous, chain_hash: chainHash };
    previous = chainHash;
    return result;
  });
  return { state: 'MEASURED', seed: 7, events, terminal: previous, receipt: { sha256: 'a'.repeat(64) }, truth: 'LOCAL_QA_SYNTHETIC' };
}

function harness(responder) {
  function element() {
    return {
      children: [], attributes: {}, textContent: '', innerHTML: '', value: '7', disabled: false,
      style: {}, classList: { remove() {} },
      append(...nodes) { this.children.push(...nodes); },
      prepend(node) { this.children.unshift(node); },
      replaceChildren(...nodes) { this.children = nodes; },
      setAttribute(name, value) { this.attributes[name] = value; },
    };
  }
  const nodes = Object.fromEntries(['chain', 'ticker', 'stats', 'chainstate', 'run', 'verify', 'seed'].map(id => [id, element()]));
  nodes.verify.disabled = true;
  const calls = [];
  const context = vm.createContext({
    document: { getElementById: id => nodes[id], createElement: element },
    webgl: false, tracks3: Object.create(null), window: {}, amber: '#ffb454', red: '#ff5d73', teal: '#3af4c8',
    motionPaused: () => true, drawScope() {},
    setTimeout: fn => { fn(); return 1; },
    TextEncoder, crypto: webcrypto, AbortSignal,
    fetch: async (url, options = {}) => { calls.push({ url, options }); return responder(url, options, calls.length); },
  });
  vm.runInContext(controller, context, { timeout: 1000 });
  return { nodes, calls };
}

test('valid synthetic response is rendered as text and local recomputation remains explicit', async () => {
  const response = sample();
  response.events[0].kind = '<img src=x onerror=alert(1)>';
  const h = harness(async () => ({ ok: true, json: async () => response }));
  await h.nodes.run.onclick();
  assert.equal(h.nodes.chain.children.length, 2);
  assert.equal(h.nodes.chain.children[1].children[1].textContent, '#0 <img src=x onerror=alert(1)>');
  assert.equal(h.nodes.chain.children[1].innerHTML, '');
  assert.match(h.nodes.chainstate.textContent, /LOCAL RECOMPUTE FAIL/);
  assert.equal(h.nodes.run.disabled, false);
  assert.equal(h.nodes.verify.disabled, false);
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, '/api/c2/scenario?seed=7&n=28');
  assert.ok(h.calls[0].options.signal);
});

test('new unavailable or malformed scenario clears the previous chain and verdict', async () => {
  let phase = 0;
  const h = harness(async () => ({ ok: phase !== 1, json: async () => phase === 2 ? { state: 'MEASURED', events: [] } : sample() }));
  await h.nodes.run.onclick();
  assert.match(h.nodes.chainstate.textContent, /LOCAL RECOMPUTE PASS/);
  for (phase of [1, 2]) {
    await h.nodes.run.onclick();
    assert.equal(h.nodes.chain.children.length, 0);
    assert.equal(h.nodes.verify.disabled, true);
    assert.match(h.nodes.chainstate.textContent, /SCENARIO UNAVAILABLE/);
    assert.doesNotMatch(h.nodes.chainstate.textContent, /RECOMPUTE PASS/);
    assert.equal(h.nodes.stats.textContent, 'No scenario loaded.');
  }
});

test('verification retains its exact request shape and an old result cannot label a new scenario', async () => {
  let completeVerification;
  const h = harness(async (url, options) => {
    if (options.method === 'POST') return new Promise(resolve => { completeVerification = resolve; });
    return { ok: true, json: async () => sample() };
  });
  await h.nodes.run.onclick();
  const verifying = h.nodes.verify.onclick();
  for (let i = 0; i < 50 && !completeVerification; i++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(typeof completeVerification, 'function');
  const request = h.calls.find(call => call.options.method === 'POST');
  assert.equal(request.url, '/api/c2/verify');
  assert.deepEqual(JSON.parse(request.options.body), { events: sample().events });
  assert.deepEqual(JSON.parse(JSON.stringify(request.options.headers)), { 'Content-Type': 'application/json' });
  await h.nodes.run.onclick();
  const current = h.nodes.ticker.textContent;
  completeVerification({ ok: true, json: async () => ({ state: 'OLD_RESULT', detail: 'must not render' }) });
  await verifying;
  assert.equal(h.nodes.ticker.textContent, current);
  assert.equal(h.nodes.verify.disabled, false);
});
