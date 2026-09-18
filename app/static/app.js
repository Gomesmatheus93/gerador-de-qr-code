document.addEventListener('DOMContentLoaded', () => {
  const menuButton = document.querySelector('[data-menu-toggle]');
  const sidebar = document.getElementById('sidebar');
  menuButton?.addEventListener('click', () => {
    const open = sidebar.classList.toggle('open');
    menuButton.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('click', event => {
    if (sidebar?.classList.contains('open') && !sidebar.contains(event.target) && event.target !== menuButton) {
      sidebar.classList.remove('open');
      menuButton?.setAttribute('aria-expanded', 'false');
    }
  });
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        const old = button.textContent;
        button.textContent = 'Copiado!';
        setTimeout(() => button.textContent = old, 1800);
      } catch (_) { button.textContent = 'Não foi possível copiar'; }
    });
  });
  document.querySelector('[data-image-size]')?.addEventListener('change', event => {
    document.querySelectorAll('[data-download]').forEach(link => {
      const url = new URL(link.href);
      url.searchParams.set('size', event.target.value);
      link.href = url.toString();
    });
  });
  document.querySelector('[data-period-select]')?.addEventListener('change', () => {
    document.querySelectorAll('[data-date-field]').forEach(input => input.value = '');
  });
  const dataNode = document.getElementById('chart-data');
  if (!dataNode || !window.Chart) return;
  let data;
  try { data = JSON.parse(dataNode.textContent); } catch (_) { return; }
  const colors = ['#315cf5', '#38b59d', '#f1b654', '#7b6de8', '#ed7e83', '#4ea6d9', '#9aa9ba', '#d39ae6'];
  Chart.defaults.font.family = 'Inter, ui-sans-serif, system-ui, sans-serif';
  Chart.defaults.color = '#8491a5';
  const daily = document.getElementById('dailyChart');
  if (daily && data.daily) new Chart(daily, {
    type: 'line',
    data: { labels: data.daily.labels, datasets: [{ label: 'Scans', data: data.daily.values, borderColor: colors[0], backgroundColor: 'rgba(49,92,245,.10)', fill: true, tension: .35, pointRadius: data.daily.labels.length > 90 ? 0 : 2, pointHoverRadius: 5, borderWidth: 2.5 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8, callback: function(value) { const raw = this.getLabelForValue(value); return raw?.slice(5).split('-').reverse().join('/'); } } }, y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#edf1f6' } } } }
  });
  function bar(id, items) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    new Chart(canvas, { type: 'bar', data: { labels: items.map(item => item.name), datasets: [{ data: items.map(item => item.count), backgroundColor: colors[0], borderRadius: 6, barThickness: 18 }] }, options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#edf1f6' } }, y: { grid: { display: false } } } } });
  }
  function doughnut(id, items) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    new Chart(canvas, { type: 'doughnut', data: { labels: items.map(item => item.name), datasets: [{ data: items.map(item => item.count), backgroundColor: colors, borderWidth: 3, borderColor: '#fff' }] }, options: { responsive: true, maintainAspectRatio: false, cutout: '66%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 14 } } } } });
  }
  bar('qrChart', data.per_qr || []);
  doughnut('deviceChart', data.devices || []);
  doughnut('osChart', data.operating_systems || []);
  doughnut('browserChart', data.browsers || []);
});
