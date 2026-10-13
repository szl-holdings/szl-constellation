/* Page presentation and a text-based view of the bundled estate manifest.
   No operational POST, evaluation, authority or source-receipt logic. */
(() => {
  'use strict';
  const root = document.documentElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const storageKey = 'szl-constellation-appearance';
  let theme = 'dark';
  try { const saved = localStorage.getItem(storageKey); if (saved === 'light' || saved === 'dark') theme = saved; } catch { /* Appearance remains usable when storage is denied. */ }
  let paused = reduced.matches;
  function applyAppearance() {
    root.dataset.surface = theme;
    root.dataset.motion = paused ? 'paused' : 'running';
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.textContent = theme === 'dark' ? 'Light theme' : 'Dark theme';
      button.setAttribute('aria-label', 'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' theme');
    });
    document.querySelectorAll('[data-motion-toggle]').forEach(button => {
      button.textContent = paused ? 'Resume motion' : 'Pause motion';
      button.setAttribute('aria-pressed', String(paused));
    });
    document.querySelectorAll('[data-motion-effect]').forEach(button => { button.disabled = paused; });
    document.dispatchEvent(new CustomEvent('szl:motion-change'));
  }
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-theme-toggle]')) return;
    theme = theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(storageKey, theme); } catch { /* No persistence is required. */ }
    applyAppearance();
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-motion-toggle]')) return;
    paused = !paused; applyAppearance();
  });
  // Gradio mounts its HTML after the head script. Bind appearance by delegation
  // and initialize only newly added controls; no Gradio event is invoked.
  new MutationObserver(records => {
    if (records.some(record => [...record.addedNodes].some(node => node.nodeType === 1 && (node.matches('[data-theme-toggle],[data-motion-toggle]') || node.querySelector('[data-theme-toggle],[data-motion-toggle]'))))) applyAppearance();
  }).observe(document.documentElement, {childList: true, subtree: true});
  reduced.addEventListener('change', () => { paused = reduced.matches; applyAppearance(); });
  applyAppearance();

  const panel = document.getElementById('panel');
  if (panel) {
    let wasOpen = false;
    let returnFocus = null;
    const close = panel.querySelector('.close');
    const syncPanel = () => {
      const open = panel.classList.contains('open');
      panel.inert = !open;
      panel.setAttribute('aria-hidden', String(!open));
      if (open && !wasOpen) { returnFocus = document.activeElement; close.focus(); }
      if (!open && wasOpen && returnFocus?.isConnected) returnFocus.focus();
      wasOpen = open;
    };
    new MutationObserver(syncPanel).observe(panel, {attributes: true, attributeFilter: ['class']});
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && panel.classList.contains('open')) { event.preventDefault(); close.click(); }
    });
    syncPanel();
  }

  const list = document.getElementById('native-estates');
  if (!list) return;
  const search = document.getElementById('estate-search');
  const status = document.getElementById('directory-status');
  let estates = [];
  function safeUrl(value) {
    if (typeof value !== 'string' || value.length > 2048) return null;
    try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : null; } catch { return null; }
  }
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text);
    if (className) element.className = className;
    return element;
  }
  function link(parent, label, url) {
    const destination = safeUrl(url);
    if (!destination) return;
    const element = node('a', label);
    element.href = destination;
    element.target = '_blank';
    element.rel = 'noopener noreferrer';
    parent.append(element);
  }
  function render() {
    const query = search.value.trim().toLocaleLowerCase();
    const filtered = estates.filter(estate => [estate.name, estate.tier, estate.desc].some(value => typeof value === 'string' && value.toLocaleLowerCase().includes(query)));
    list.replaceChildren();
    for (const estate of filtered) {
      const item = node('article', undefined, 'native-estate');
      item.append(node('small', (estate.tier || 'Unclassified') + ' · bundled topology'), node('h3', estate.name), node('p', typeof estate.desc === 'string' ? estate.desc : 'No description declared.'));
      const details = node('details');
      details.append(node('summary', 'Source and declared links'));
      const links = node('div', undefined, 'native-source-links');
      if (typeof estate.repo === 'string' && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(estate.repo)) link(links, 'GitHub source · ' + estate.repo, 'https://github.com/' + estate.repo);
      if (Array.isArray(estate.live)) estate.live.forEach((url, index) => link(links, 'Declared surface ' + (index + 1), url));
      if (estate.release && typeof estate.release === 'object') {
        link(links, 'Published release · ' + String(estate.release.tag || 'version unspecified'), estate.release.url);
        links.append(node('p', 'Release artifacts do not establish a running service.'));
      }
      if (estate.candidate && typeof estate.candidate === 'object') link(links, 'Source candidate · outside the release', estate.candidate.url);
      if (!links.children.length) links.append(node('p', 'No admissible public link is declared.'));
      details.append(links);
      item.append(details);
      list.append(item);
    }
    status.textContent = filtered.length + ' of ' + estates.length + ' source-listed estates shown. This is the bundled historical topology, not a current organization census.';
    if (!filtered.length) list.append(node('p', 'No source-listed estate matches this filter.', 'native-directory-status'));
  }
  search.addEventListener('input', render);
  async function load() {
    try {
      const response = await fetch('/static/estates.json', {signal: AbortSignal.timeout(15000), credentials: 'omit'});
      if (!response.ok) throw new Error('Manifest HTTP status');
      const text = await response.text();
      if (text.length > 1_000_000) throw new Error('Manifest exceeds the presentation limit');
      const data = JSON.parse(text);
      if (!data || !Array.isArray(data.estates) || data.estates.length > 1000 || data.estates.some(item => !item || typeof item !== 'object' || typeof item.name !== 'string' || !item.name.trim())) throw new Error('Manifest shape');
      estates = data.estates;
      render();
    } catch {
      list.replaceChildren();
      status.textContent = 'DIRECTORY UNAVAILABLE — the bundled manifest could not be read. No estate count or availability is inferred.';
      search.disabled = true;
    }
  }
  load();
})();
