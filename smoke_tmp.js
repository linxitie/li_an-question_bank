async (page) => {
  await page.addInitScript((t) => {
    try {
      localStorage.setItem('__VTJ_AUTH_STATE__', JSON.stringify({
        token: t, username: '202516001', userNo: '202516001', userId: 2, loginTime: Date.now()
      }));
    } catch (e) {}
  }, "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoyLCJ1c2VybmFtZSI6IjIwMjUxNjAwMSIsInVzZXJfdHlwZSI6InN0dWRlbnQiLCJyb2xlIjoic3R1ZGVudCIsInJvbGVfbGV2ZWwiOjEsInBlcm1pc3Npb25zIjpbInF1ZXN0aW9uOnZpZXciLCJxdWVzdGlvbjpjcmVhdGUiLCJxdWVzdGlvbjp1cGRhdGUiLCJxdWVzdGlvbjpkZWxldGUiLCJwYXBlcjpjcmVhdGUiLCJwYXBlcjp1cGRhdGUiLCJwYXBlcjp2aWV3IiwiZXhhbTpzdGFydCIsImV4YW06YW5zd2VyIiwiZXhhbTpmaW5pc2giLCJleGFtOmFuYWx5c2lzIl0sInBhcGVyIjoicHVibGlzaCIsImV4YW0iOlsic3RhcnQiLCJhbnN3ZXIiLCJmaW5pc2giLCJhbmFseXNpcyJdLCJleGFtX3R5cGUiOiJ4aW5nY2VfYWxjIiwiZXhwX3R5cGUiOiJ4aW5nY2VfYWxjIiwidXNlcl92aWV3X2FsbCI6ZmFsc2UsIm5pY2tuYW1lIjoiXHU2NzJjXHU1NzMwXHU5YThjXHU4YmMxXHU1YjY2XHU3NTFmIiwidmlkZW9fbGltaXQiOiIiLCJpc19sb2FkZWQiOnRydWUsImlzX3N1cHBvcnQiOnRydWUsImlwIjoiIiwidWlkIjoiIiwiZXhhbV92aWV3X2FsbCI6ZmFsc2UsImV4cCI6MTc5MDk0MTM2MSwidHlwZSI6ImFjY2VzcyIsImlhdCI6MTc5MDkxMjU2MX0.y__VyCJ0eM-x6grrXSgl7CkG_i26AsD5qe6D_sJ7xHA");

  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 170)); });
  page.on('pageerror', (e) => errors.push('PAGEERROR: ' + String(e.message).slice(0, 170)));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('http://127.0.0.1:9527/#/mobile/home', { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);

  const r = await page.evaluate(() => {
    const q = (s) => document.querySelector(s);
    const txt = (s) => { const e = q(s); return e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : null; };
    return {
      url: location.hash,
      isLoggedIn: !!(window.__VTJ_AUTH__ && window.__VTJ_AUTH__.isLoggedIn()),
      greetingText: txt('.greeting-text'),
      greetingMotto: txt('.greeting-motto'),
      oldStatCardsRemoved: document.querySelectorAll('.stat-card').length === 0,
      oldStatsGridGone: !q('.stats-grid'),
      oldBarChartGone: !q('.chart-bars'),
      chartCanvasPresent: !!q('.chart-canvas'),
      echartsCanvasRendered: document.querySelectorAll('.chart-canvas canvas').length,
      chartEmptyText: txt('.chart-empty'),
      switchButtons: [...document.querySelectorAll('.switch-btn')].map(b => b.textContent.trim() + (b.className.includes('active') ? '(on)' : '')),
      goalLabel: txt('.goal-label'),
      quoteText: (txt('.quote-text') || '').slice(0, 34),
      quoteAttribution: txt('.quote-author'),
      quoteRefreshBtn: txt('.quote-refresh'),
      goalFieldLabels: [...document.querySelectorAll('.goal-field-label')].map(e => e.textContent.trim()),
    };
  });
  return { dom: r, consoleErrors: errors.slice(0, 8) };
}