// Runs a creative-review dashboard page outside claude.ai (for GitHub Pages).
// The dashboard pages call a small `dash` runtime: dash.data(id), dash.onData(cb), dash.colors.
// This file provides that runtime from the JSON files the scheduled routines commit,
// then loads the dashboard page itself, so the public copy always matches it.
(function () {
  const store = {}, subs = [];
  const notify = () => subs.forEach(cb => { try { cb(); } catch (e) { console.error(e); } });

  window.dash = {
    colors: ['#2f6fdb', '#d9822b', '#2e9e6a', '#8b5cf6', '#d64545', '#0ea5a4', '#b8860b', '#64748b'],
    data: id => store[id] || { status: 'loading', data: null },
    onData: cb => { subs.push(cb); cb(); }
  };

  window.mountDashboard = async function (pageUrl, dataDir, datasets) {
    const app = document.getElementById('app');
    let html;
    try {
      const r = await fetch(pageUrl, { cache: 'no-cache' });
      if (!r.ok) throw new Error(r.status);
      html = await r.text();
    } catch (e) {
      app.textContent = 'Could not load the dashboard. Try reloading the page.';
      return;
    }
    app.innerHTML = html;
    // Scripts inserted through innerHTML don't run; re-create them so they do.
    app.querySelectorAll('script').forEach(old => {
      const s = document.createElement('script');
      s.textContent = old.textContent;
      old.replaceWith(s);
    });

    await Promise.all(datasets.map(async id => {
      try {
        const r = await fetch(dataDir + id + '.json', { cache: 'no-cache' });
        if (!r.ok) throw new Error(r.status);
        store[id] = { status: 'ok', data: await r.json() };
      } catch (e) {
        store[id] = { status: 'error', data: null };
      }
      notify();
    }));
  };
})();
