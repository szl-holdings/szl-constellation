/* SPDX-License-Identifier: Apache-2.0 */
'use strict';

const state = {
  rows: [],
  truthBoundary: [],
  disposition: '',
  successor: '',
  query: '',
  selected: null,
};

const byId = (id) => document.getElementById(id);
const grid = byId('registry-grid');
const field = byId('successor-field');
const dialog = byId('repository-dialog');

function element(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined) value.textContent = text;
  return value;
}

function dispositionLabel(value) {
  return {
    SOURCE_OWNER: 'SOURCE OWNER',
    CONSOLIDATE: 'CONSOLIDATED',
    HISTORICAL: 'HISTORICAL',
  }[value] || value;
}

function sourceUrl(name) {
  return /^[a-z0-9][a-z0-9._-]{0,99}$/.test(name)
    ? `https://github.com/szl-holdings/${name}`
    : 'https://github.com/szl-holdings';
}

function filteredRows() {
  const needle = state.query.trim().toLocaleLowerCase();
  return state.rows.filter((row) => {
    if (state.disposition && row.disposition !== state.disposition) return false;
    if (state.successor && row.successor !== state.successor) return false;
    if (!needle) return true;
    const haystack = `${row.name} ${row.successor || ''} ${row.capability} ${row.showcase.join(' ')}`.toLocaleLowerCase();
    return haystack.includes(needle);
  });
}

function badge(row) {
  return element('span', `badge badge-${row.disposition.toLowerCase().replace('_', '-')}`, dispositionLabel(row.disposition));
}

function card(row) {
  const button = element('button', 'repository-card');
  button.type = 'button';
  button.setAttribute('aria-label', `Open ${row.name} lineage evidence`);
  button.dataset.disposition = row.disposition;

  const head = element('div', 'card-head');
  head.append(badge(row), element('span', 'provider-state', 'PROVIDER UNMEASURED'));
  const title = element('h3', '', row.name);
  const capability = element('p', 'capability', row.capability);
  const relation = element('div', 'relation');
  if (row.disposition === 'SOURCE_OWNER') {
    relation.append(element('span', '', 'Owns source'), element('strong', '', row.name));
  } else if (row.disposition === 'CONSOLIDATE') {
    relation.append(element('span', '', 'Successor'), element('strong', '', row.successor));
  } else {
    relation.append(element('span', '', 'Retention'), element('strong', '', 'Immutable evidence'));
  }
  button.append(head, title, capability, relation);
  button.addEventListener('click', () => openRepository(row));
  return button;
}

function renderGrid() {
  const rows = filteredRows();
  grid.replaceChildren(...rows.map(card));
  byId('result-summary').textContent = `${rows.length} of ${state.rows.length} repositories shown`;
  byId('empty-state').hidden = rows.length !== 0;
}

function groupRows(rows) {
  const groups = new Map();
  rows.forEach((row) => {
    const key = row.disposition === 'HISTORICAL' ? 'immutable-history' : (row.successor || row.name);
    const current = groups.get(key) || [];
    current.push(row);
    groups.set(key, current);
  });
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

function renderField() {
  const rows = filteredRows();
  const groups = groupRows(rows);
  field.replaceChildren();
  groups.forEach(([successor, members]) => {
    const group = element('article', 'successor-group');
    const hub = element('div', 'successor-hub');
    hub.append(
      element('span', 'hub-kicker', members[0].disposition === 'HISTORICAL' ? 'RETENTION VAULT' : 'CANONICAL OWNER'),
      element('strong', '', successor),
      element('span', 'hub-count', `${members.length} source${members.length === 1 ? '' : 's'}`),
    );
    const sources = element('div', 'source-nodes');
    members.forEach((row) => {
      const node = element('button', `source-node source-${row.disposition.toLowerCase()}`);
      node.type = 'button';
      node.textContent = row.name;
      node.setAttribute('aria-label', `Open ${row.name} lineage`);
      node.addEventListener('click', () => openRepository(row));
      sources.append(node);
    });
    group.append(hub, sources);
    field.append(group);
  });
}

function render() {
  renderGrid();
  renderField();
}

function addEvidence(term, value) {
  const list = byId('dialog-evidence');
  list.append(element('dt', '', term), element('dd', '', value === null || value === undefined ? 'NONE' : String(value)));
}

function openRepository(row) {
  state.selected = row;
  byId('dialog-disposition').textContent = dispositionLabel(row.disposition);
  byId('dialog-title').textContent = row.name;
  byId('dialog-capability').textContent = row.capability;
  byId('dialog-evidence').replaceChildren();
  addEvidence('Successor', row.successor);
  addEvidence('Expected archived', row.expected_archived ? 'YES' : 'NO');
  addEvidence('Immutable history', row.immutable_history ? 'YES' : 'NO');
  addEvidence('Provider state', row.provider_state);
  addEvidence('Showcase', row.showcase.join(', '));
  byId('dialog-source').href = sourceUrl(row.name);
  byId('readback-result').hidden = true;
  byId('readback-result').textContent = '';
  byId('readback-button').disabled = false;
  byId('readback-button').textContent = 'Read local evidence';
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.setAttribute('open', '');
}

async function localReadback() {
  const row = state.selected;
  if (!row) return;
  const button = byId('readback-button');
  const result = byId('readback-result');
  button.disabled = true;
  button.textContent = 'Reading…';
  result.hidden = false;
  result.textContent = 'Reading source-controlled evidence.';
  try {
    const response = await fetch(`/api/archive-revival/${encodeURIComponent(row.name)}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    result.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    result.textContent = JSON.stringify({ status: 'UNAVAILABLE', detail: String(error.message || error) }, null, 2);
  } finally {
    button.disabled = false;
    button.textContent = 'Read again';
  }
}

function selectDisposition(value) {
  state.disposition = value;
  document.querySelectorAll('.metrics button[data-disposition]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.disposition === value));
  });
  render();
}

async function loadSource() {
  try {
    const response = await fetch('/api/source', { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const source = payload.source || {};
    byId('source-state').textContent = source.state === 'MEASURED'
      ? `Source ${String(source.revision).slice(0, 12)} measured`
      : 'Source revision unavailable — local contract only';
  } catch (_error) {
    byId('source-state').textContent = 'Source evidence unavailable';
  }
}

async function loadRegistry() {
  try {
    const response = await fetch('/api/archive-revival', { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    state.rows = Array.isArray(payload.repositories) ? payload.repositories : [];
    state.truthBoundary = Array.isArray(payload.truth_boundary) ? payload.truth_boundary : [];
    const counts = payload.declared_counts || {};
    byId('source-count').textContent = String(counts.source_owner ?? 0);
    byId('consolidate-count').textContent = String(counts.consolidate ?? 0);
    byId('historical-count').textContent = String(counts.historical ?? 0);
    byId('total-count').textContent = String(counts.total ?? state.rows.length);

    const select = byId('successor-filter');
    [...new Set(state.rows.map((row) => row.successor).filter(Boolean))]
      .sort()
      .forEach((successor) => {
        const option = document.createElement('option');
        option.value = successor;
        option.textContent = successor;
        select.append(option);
      });

    const ladder = byId('truth-boundary');
    ladder.replaceChildren(...state.truthBoundary.map((item, index) => {
      const li = element('li');
      li.append(element('span', 'step-number', String(index + 1).padStart(2, '0')), element('strong', '', item));
      return li;
    }));
    render();
  } catch (error) {
    byId('result-summary').textContent = `Registry unavailable: ${String(error.message || error)}`;
    byId('empty-state').hidden = false;
  }
}

document.querySelector('.metrics').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-disposition]');
  if (button) selectDisposition(button.dataset.disposition);
});

byId('search').addEventListener('input', (event) => {
  state.query = event.target.value;
  render();
});

byId('successor-filter').addEventListener('change', (event) => {
  state.successor = event.target.value;
  render();
});

byId('clear-filters').addEventListener('click', () => {
  state.query = '';
  state.successor = '';
  byId('search').value = '';
  byId('successor-filter').value = '';
  selectDisposition('');
});

byId('readback-button').addEventListener('click', localReadback);
dialog.addEventListener('click', (event) => {
  if (event.target === dialog) dialog.close();
});

document.addEventListener('keydown', (event) => {
  if (event.key === '/' && !event.ctrlKey && !event.metaKey && document.activeElement?.tagName !== 'INPUT') {
    event.preventDefault();
    byId('search').focus();
  }
});

Promise.all([loadRegistry(), loadSource()]);
