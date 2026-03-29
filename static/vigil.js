/* ═══════════════════════════════════════════════════════════════
   VIGIL — Application Logic
   ═══════════════════════════════════════════════════════════════ */

// ── CONSTANTS ─────────────────────────────────────────────────

const ACTION = {
  ENTER:      { color: '#22c55e', bg: 'rgba(34,197,94,0.09)',  border: 'rgba(34,197,94,0.22)',  icon: '▲' },
  WAIT:       { color: '#f59e0b', bg: 'rgba(245,158,11,0.09)', border: 'rgba(245,158,11,0.22)', icon: '◐' },
  AVOID:      { color: '#ef4444', bg: 'rgba(239,68,68,0.09)',  border: 'rgba(239,68,68,0.22)',  icon: '▼' },
  STAND_DOWN: { color: '#64748b', bg: 'rgba(100,116,139,0.07)',border: 'rgba(100,116,139,0.18)','icon': '◌' },
};

const STATE_COLOR = {
  BREAKOUT:     '#22c55e',
  TRENDING_UP:  '#34d399',
  TRENDING_DOWN:'#f87171',
  RANGING:      '#64748b',
  ACCUMULATING: '#818cf8',
  VOLATILE:     '#f59e0b',
  UNKNOWN:      '#334155',
};

const MTF_COLOR = { UP: '#22c55e', NEUTRAL: '#334155', DOWN: '#ef4444' };

const COMBO_LABEL = {
  ACCUM_BREAKOUT:        'Accum → Breakout',
  CONFIRMED_BREAKOUT:    'Confirmed Breakout',
  WEAK_BREAKOUT:         'Weak Breakout',
  ACCUMULATION_BUILDING: 'Accumulating',
  TRENDING_CONTINUATION: 'Trend Continuation',
  DISTRIBUTION:          'Distribution',
  TRENDING_BREAKDOWN:    'Breakdown',
  VOLUME_ONLY_UP:        'Vol Event ↑',
  VOLUME_ONLY_DOWN:      'Vol Event ↓',
};

const REGIME_COLOR = {
  TRENDING: '#22c55e', RISK_OFF: '#ef4444',
  VOLATILE: '#f59e0b', SIDEWAYS: '#5E6AD2', UNKNOWN: '#64748b',
};

const REGIME_DESC = {
  TRENDING: 'All signal types performing at or above baseline.',
  RISK_OFF:  'Risk-off conditions — caution on all long positions.',
  VOLATILE:  'Elevated volatility — reduce size, avoid breakout chasing.',
  SIDEWAYS:  'Consolidation regime — breakouts less reliable.',
  UNKNOWN:   'Insufficient data to classify regime.',
};

// ── STATE ─────────────────────────────────────────────────────

let _alerts     = [];
let _expandedId = null;

// ── SPOTLIGHT TRACKING ────────────────────────────────────────

document.addEventListener('mousemove', e => {
  document.querySelectorAll('.card').forEach(el => {
    const r = el.getBoundingClientRect();
    el.style.setProperty('--mx', `${e.clientX - r.left}px`);
    el.style.setProperty('--my', `${e.clientY - r.top}px`);
  });
});

// ── FORMATTERS ────────────────────────────────────────────────

function fmtHours(h) {
  if (h === 0 || h === undefined) return '';
  return h < 1 ? `${Math.round(h * 60)}m` : `${h.toFixed(1)}h`;
}

function fmtCombo(c) {
  return COMBO_LABEL[c] || (c || '').replace(/_/g, ' ');
}

function edgeColor(score) {
  if (score === null || score === undefined) return '#475569';
  return score >= 7.5 ? '#22c55e' : score >= 4.5 ? '#f59e0b' : '#ef4444';
}

function decayColor(pct) {
  return pct > 65 ? '#22c55e' : pct > 35 ? '#f59e0b' : '#ef4444';
}

function stateColor(s) {
  return STATE_COLOR[s] || STATE_COLOR.UNKNOWN;
}

function actionCfg(a) {
  return ACTION[a] || { color: '#475569', bg: 'rgba(71,85,105,0.07)', border: 'rgba(71,85,105,0.18)', icon: '·' };
}

// ── RENDER: MTF DOTS ─────────────────────────────────────────

function renderMTF(weekly, daily, recent, showLabels = false) {
  const tfs = [['W', weekly], ['D', daily], ['5D', recent]];
  const dots = tfs.map(([lbl, v]) => `
    <div class="mtf-item" title="${lbl}: ${v || 'N/A'}">
      <div class="mtf-dot" style="background:${MTF_COLOR[v] || '#1e293b'}"></div>
      <span class="mtf-key">${lbl}</span>
    </div>
  `).join('');
  const label = showLabels && weekly
    ? `<span class="mtf-expanded-label">— ${weekly} / ${daily} / ${recent}</span>`
    : '';
  return `<div class="mtf-group">${dots}${label}</div>`;
}

// ── RENDER: TRAP WARNING ──────────────────────────────────────

function renderTrap(alert) {
  if (!alert.trap_conviction || alert.trap_conviction <= 0.4) return '';
  const reasons = (alert.trap_reasons || []).map(r => `
    <div class="trap-reason">
      <span class="trap-arrow">→</span>
      <span class="trap-text">${r}</span>
    </div>
  `).join('');
  return `
    <div class="trap-box">
      <div class="trap-box-title">⚠ POTENTIAL ${alert.trap_type || 'BULL TRAP'} · ${Math.round(alert.trap_conviction * 100)}% conviction</div>
      ${reasons}
    </div>
  `;
}

// ── RENDER: EDGE BREAKDOWN ────────────────────────────────────

function renderEdgeBreakdown(alert) {
  if (alert.edge_score === null || alert.edge_score === undefined) return '';
  const score = alert.edge_score;
  const color = edgeColor(score);

  const mtfAdj = {
    FULL_UP: 1.5, PARTIAL_UP: 0.8, CONFLICTED: -0.3,
    PARTIAL_DOWN: -0.8, FULL_DOWN: -1.5,
  }[alert.mtf_alignment] ?? -0.3;

  const trapPenalty = alert.trap_conviction ? -(alert.trap_conviction * 3.0) : 0;
  const stateBonus  = alert.days_in_state >= 14 ? 0.8 : alert.days_in_state >= 7 ? 0.4 : 0;
  const volBonus    = alert.volume_ratio > 3 ? 0.5 : alert.volume_ratio > 2 ? 0.25 : 0;

  const rows = [
    ['Signal base',     score - mtfAdj - stateBonus - volBonus - trapPenalty, 5.5],
    ['MTF alignment',   mtfAdj,     1.5],
    ['Days in state',   stateBonus, 0.8],
    ['Volume',          volBonus,   0.5],
    ['Trap penalty',    trapPenalty, 0],
  ];

  const rowsHtml = rows.map(([label, val, max]) => {
    const isNeg   = val < 0;
    const barFill = isNeg ? '#ef444440' : val >= 1 ? '#22c55e' : '#5E6AD2';
    const barMax  = max > 0 ? max : 3;
    const barW    = Math.min(Math.abs(val) / barMax * 100, 100);
    return `
      <div class="edge-row-item">
        <div class="edge-row-lbl" style="color:${isNeg ? '#7f1d1d' : '#6b7db3'}">${label}</div>
        <div class="edge-row-track">
          <div class="edge-row-fill" style="width:${barW}%;background:${barFill}"></div>
        </div>
        <div class="edge-row-val" style="color:${isNeg ? '#ef4444' : '#6b8aaa'}">
          ${val > 0 ? '+' : ''}${val.toFixed(1)}
        </div>
      </div>
    `;
  }).join('');

  return `
    <div class="edge-box">
      <div class="edge-box-header">
        <span class="edge-box-title">EDGE BREAKDOWN</span>
        <span class="edge-box-score" style="color:${color}">${score}<span class="edge-denom">/10</span></span>
      </div>
      ${rowsHtml}
    </div>
  `;
}

// ── RENDER: EXPANDED BODY ─────────────────────────────────────

function renderBody(alert) {
  const trap = renderTrap(alert);

  const hasMTF = alert.mtf_weekly || alert.mtf_daily || alert.mtf_recent;
  const mtf = hasMTF ? `
    <div class="mtf-expanded">
      ${renderMTF(alert.mtf_weekly, alert.mtf_daily, alert.mtf_recent, true)}
    </div>
  ` : '';

  const cells = [
    alert.regime        && ['REGIME',        alert.regime,                         ''],
    alert.days_in_state && ['DAYS IN STATE',  `${alert.days_in_state}d`,            ''],
    alert.prev_state    && alert.prev_state !== 'UNKNOWN' && ['PREV STATE', alert.prev_state, ''],
    alert.volume_ratio  && ['VOLUME RATIO',   `${alert.volume_ratio}×`,             ''],
    alert.accum_conviction && ['ACCUM CONV',  `${Math.round(alert.accum_conviction * 100)}%`, alert.accum_conviction > 0.7 ? 'good' : 'warn'],
    alert.outcome_pct !== null && alert.outcome_pct !== undefined && [
      'OUTCOME',
      `${alert.outcome_pct > 0 ? '+' : ''}${alert.outcome_pct.toFixed(2)}% · ${alert.outcome_result || ''}`,
      alert.outcome_pct > 0 ? 'good' : 'bad',
    ],
  ].filter(Boolean);

  const grid = cells.length ? `
    <div class="detail-grid">
      ${cells.map(([lbl, val, cls]) => `
        <div class="detail-cell">
          <div class="detail-cell-label">${lbl}</div>
          <div class="detail-cell-value ${cls}">${val}</div>
        </div>
      `).join('')}
    </div>
  ` : '';

  const edge = renderEdgeBreakdown(alert);

  return `<div class="alert-body">${trap}${mtf}${grid}${edge}</div>`;
}

// ── RENDER: SINGLE ALERT CARD ─────────────────────────────────

function renderCard(alert) {
  const a      = actionCfg(alert.action);
  const decay  = alert.decay || { pct: 50, status: 'UNKNOWN', hours_old: 0 };
  const dc     = decayColor(decay.pct);
  const ec     = edgeColor(alert.edge_score);
  const sc     = stateColor(alert.state);
  const hasTrap= alert.trap_conviction && alert.trap_conviction > 0.4;
  const isOpen = _expandedId === alert.id;

  const decayStatusLabel = {
    FRESH: 'Fresh', DECAYING: 'Decaying', DETERIORATING: 'Weakening',
    EXPIRED: 'Expired', UNKNOWN: '—',
  }[decay.status] || decay.status;

  const prevColor  = stateColor(alert.prev_state);
  const hasChange  = alert.prev_state && alert.prev_state !== alert.state && alert.prev_state !== 'UNKNOWN';
  const stateRow   = (alert.state || alert.prev_state) ? `
    <div class="state-row">
      ${hasChange ? `
        <span class="state-pill" style="color:${prevColor};background:${prevColor}1a">${alert.prev_state}</span>
        <span class="state-arrow">→</span>
        <span class="state-pill" style="color:${sc};background:${sc}1a">${alert.state}${alert.days_in_state ? ' · ' + alert.days_in_state + 'd' : ''}</span>
      ` : `
        <span class="state-pill" style="color:${sc};background:${sc}1a">${alert.state || ''}${alert.days_in_state ? ' · ' + alert.days_in_state + 'd' : ''}</span>
      `}
    </div>
  ` : '';

  return `
    <div class="alert-card${isOpen ? ' is-expanded' : ''}" id="alert-${alert.id}" onclick="toggleCard(${alert.id})">
      <div class="alert-bar" style="background:linear-gradient(180deg,${a.color},${a.color}28)"></div>

      <div class="decay-row">
        <div class="decay-track">
          <div class="decay-fill" style="width:${decay.pct}%;background:${dc}"></div>
        </div>
        <div class="decay-info">
          <span class="decay-label" style="color:${dc}">
            ${decayStatusLabel.toUpperCase()}${decay.hours_old > 0 ? ' · ' + fmtHours(decay.hours_old) : ''}
          </span>
        </div>
      </div>

      <div class="alert-main">
        <div class="alert-top">
          <div class="alert-left">
            <span class="ticker">${alert.ticker}</span>
            <div class="action-badge" style="background:${a.bg};border:1px solid ${a.border};color:${a.color}">
              ${a.icon} ${alert.action || '—'}
            </div>
            ${alert.signal_combination ? `<span class="combo-tag">${fmtCombo(alert.signal_combination)}</span>` : ''}
            ${hasTrap ? `<span class="trap-tag">⚠ Trap Risk</span>` : ''}
            ${renderMTF(alert.mtf_weekly, alert.mtf_daily, alert.mtf_recent)}
          </div>
          <div class="alert-right">
            ${alert.edge_score !== null && alert.edge_score !== undefined
              ? `<span class="edge-score" style="color:${ec}">${alert.edge_score}<span class="edge-denom">/10</span></span>`
              : ''}
            <span class="alert-date">${alert.date || ''}</span>
          </div>
        </div>

        ${stateRow}

        ${alert.summary
          ? `<div class="alert-summary">${alert.summary}</div>`
          : ''}
      </div>

      ${isOpen ? renderBody(alert) : ''}
    </div>
  `;
}

// ── TOGGLE EXPAND ─────────────────────────────────────────────

function toggleCard(id) {
  _expandedId = _expandedId === id ? null : id;
  renderFeed(_alerts);
}

// ── RENDER: BRIEFING ──────────────────────────────────────────

function renderBriefing(active) {
  if (!active.length) return '';

  const now = new Date();
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  const dateStr = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  const rows = active.slice(0, 3).map((a, i) => {
    const ac    = actionCfg(a.action);
    const decay = a.decay || { pct: 50, status: 'UNKNOWN' };
    const dc    = decayColor(decay.pct);
    const ec    = edgeColor(a.edge_score);
    return `
      <div class="briefing-row">
        <span class="briefing-num">${i + 1}.</span>
        <span class="briefing-ticker">${a.ticker}</span>
        <div class="action-badge" style="background:${ac.bg};border:1px solid ${ac.border};color:${ac.color};font-size:9px;padding:2px 8px;">
          ${ac.icon} ${a.action}
        </div>
        ${a.edge_score !== null && a.edge_score !== undefined
          ? `<span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:${ec}">${a.edge_score}</span>`
          : ''}
        <div class="briefing-decay">
          <div class="briefing-decay-fill" style="width:${decay.pct}%;background:${dc}"></div>
        </div>
        <span class="briefing-status" style="color:${dc}">${decay.status || ''}</span>
      </div>
    `;
  }).join('');

  const others = _alerts.length - active.length;

  return `
    <div class="briefing">
      <div class="briefing-head">
        <span class="briefing-title">Today's Briefing</span>
        <span class="briefing-time">${dateStr} · ${timeStr}</span>
      </div>
      <div class="briefing-body">
        <p class="briefing-intro">
          ${active.length} signal${active.length !== 1 ? 's' : ''} worth your attention.
          ${others > 0 ? `${others} other${others !== 1 ? 's' : ''} did not meet the threshold.` : ''}
        </p>
        ${rows}
      </div>
    </div>
  `;
}

// ── RENDER: FULL FEED ─────────────────────────────────────────

function renderFeed(alerts) {
  _alerts = alerts;
  const container = document.getElementById('alerts-container');
  const briefingEl = document.getElementById('briefing-container');
  const metaEl     = document.getElementById('feed-meta');

  if (!alerts.length) {
    if (briefingEl) briefingEl.innerHTML = '';
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">◌</span>
        <div class="empty-title">Silence as Signal</div>
        <p class="empty-body">No alerts detected. Staying out is a valid position.<br>The system is watching.</p>
      </div>
    `;
    if (metaEl) metaEl.textContent = '0 alerts';
    return;
  }

  // Partition
  const active = alerts.filter(a =>
    a.action && ['ENTER', 'WAIT', 'AVOID'].includes(a.action) && !a.outcome_result
  );
  const historical = alerts.filter(a => !active.includes(a));

  // Briefing
  if (briefingEl) briefingEl.innerHTML = renderBriefing(active);

  // Feed
  let html = '';
  if (active.length) {
    html += `<div class="divider-lbl">Active Signals</div>`;
    html += active.map(renderCard).join('');
  }
  if (historical.length) {
    html += `<div class="divider-lbl">Historical</div>`;
    html += historical.slice(0, 25).map(renderCard).join('');
  }
  container.innerHTML = html;

  if (metaEl) metaEl.textContent = `${alerts.length} alerts · ${active.length} active`;
}

// ── UPDATE: STATS ─────────────────────────────────────────────

function updateStats(stats) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set('s-pf',     stats.profit_factor ?? '—');
  set('s-sharpe', stats.sharpe        ?? '—');
  set('s-wr',     stats.win_rate      ? `${stats.win_rate}%` : '—');
  set('s-trades', stats.total_trades  ?? '0');
  const liveEl = document.getElementById('live-status');
  if (liveEl) liveEl.textContent = `Live · ${new Set((_alerts || []).map(a => a.ticker)).size} assets`;
}

// ── UPDATE: REGIME ────────────────────────────────────────────

function updateRegime(regime) {
  const r      = regime || 'UNKNOWN';
  const color  = REGIME_COLOR[r] || '#64748b';
  const desc   = REGIME_DESC[r]  || '';
  const lbl    = document.getElementById('regime-text');
  const descEl = document.getElementById('regime-desc');
  const dot    = document.querySelector('.regime-dot');
  if (lbl)    { lbl.textContent = `REGIME: ${r}`; lbl.style.color = color; }
  if (descEl)   descEl.textContent = desc;
  if (dot)      dot.style.background = color;
}

// ── FETCH ─────────────────────────────────────────────────────

async function fetchAll() {
  try {
    const [ar, sr, rr] = await Promise.all([
      fetch('/alerts?limit=60'),
      fetch('/stats'),
      fetch('/regime'),
    ]);
    const alerts = await ar.json();
    const stats  = await sr.json();
    const regime = await rr.json();
    updateStats(stats);
    updateRegime(regime.regime);
    renderFeed(alerts);
  } catch (err) {
    console.error('Vigil fetch error:', err);
  }
}

// ── RUN PULSE ─────────────────────────────────────────────────

async function runPulse() {
  const btn = document.getElementById('btn-pulse');
  if (!btn) return;
  btn.textContent = 'Scanning...';
  btn.disabled = true;
  try {
    await fetch('/trigger');
    setTimeout(() => { fetchAll(); btn.textContent = 'Run Pulse'; btn.disabled = false; }, 5000);
  } catch {
    btn.textContent = 'Run Pulse';
    btn.disabled = false;
  }
}

// ── BOOT ──────────────────────────────────────────────────────

fetchAll();
setInterval(fetchAll, 60 * 1000);