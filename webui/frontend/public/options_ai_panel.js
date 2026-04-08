/**
 * Options AI Engine — Frontend Panel
 * ===================================
 * Vanilla JS, no build step. Inject via:
 *   <script src="/static/options_ai_panel.js"></script>
 *
 * Adds a floating "🤖 AI Advisor" button to the options page.
 * Clicking it opens a side panel with:
 *   - Risk level badge
 *   - AI market view & portfolio advice
 *   - Per-position suggestion cards
 *   - Automation toggle (with confirmation modal)
 *   - Memory / Learning log tab
 *   - "Analyse Now" manual trigger button
 *   - Auto-refresh every 5 minutes when open
 */

(function () {
    'use strict';

    // ── Constants ──────────────────────────────────────────────────────────────
    const API_BASE = '/api/options-ai';
    const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

    // ── State ──────────────────────────────────────────────────────────────────
    let _panelOpen = false;
    let _activeTab = 'suggestions'; // 'suggestions' | 'memory'
    let _refreshTimer = null;
    let _automationEnabled = false;
    let _lastData = null;

    // ── Styles ─────────────────────────────────────────────────────────────────
    const STYLES = `
    #ai-fab {
      position: fixed;
      bottom: 28px;
      right: 28px;
      z-index: 9999;
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      color: #fff;
      border: none;
      border-radius: 50px;
      padding: 12px 20px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(99,102,241,0.45);
      display: flex;
      align-items: center;
      gap: 8px;
      transition: transform 0.15s, box-shadow 0.15s;
    }
    #ai-fab:hover { transform: translateY(-2px); box-shadow: 0 6px 28px rgba(99,102,241,0.6); }
    #ai-fab .ai-fab-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #4ade80; display: inline-block;
      animation: ai-pulse 2s infinite;
    }
    @keyframes ai-pulse { 0%,100%{opacity:1}50%{opacity:0.4} }

    #ai-panel {
      position: fixed;
      top: 60px; right: 0;
      width: 420px;
      height: calc(100vh - 60px);
      background: #0f172a;
      border-left: 1px solid #1e293b;
      z-index: 9998;
      display: flex;
      flex-direction: column;
      box-shadow: -8px 0 40px rgba(0,0,0,0.45);
      transform: translateX(100%);
      transition: transform 0.3s cubic-bezier(0.4,0,0.2,1);
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      color: #e2e8f0;
    }
    #ai-panel.open { transform: translateX(0); }

    .ai-panel-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid #1e293b;
      background: linear-gradient(135deg, #1e1b4b, #0f172a);
      flex-shrink: 0;
    }
    .ai-panel-title { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
    .ai-close-btn {
      background: none; border: none; color: #94a3b8;
      font-size: 20px; cursor: pointer; padding: 4px;
      border-radius: 6px; transition: color 0.15s;
    }
    .ai-close-btn:hover { color: #fff; }

    .ai-risk-badge {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.05em;
    }
    .ai-risk-low    { background: #052e16; color: #4ade80; border: 1px solid #166534; }
    .ai-risk-medium { background: #1c1408; color: #fbbf24; border: 1px solid #92400e; }
    .ai-risk-high   { background: #1c0a05; color: #fb923c; border: 1px solid #9a3412; }
    .ai-risk-critical{ background: #1c0505; color: #f87171; border: 1px solid #991b1b; }
    .ai-risk-unknown{ background: #1e293b; color: #94a3b8; border: 1px solid #334155; }

    .ai-panel-body { flex: 1; overflow-y: auto; padding: 0 0 20px 0; }
    .ai-panel-body::-webkit-scrollbar { width: 4px; }
    .ai-panel-body::-webkit-scrollbar-track { background: #0f172a; }
    .ai-panel-body::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

    .ai-section { padding: 16px 20px; border-bottom: 1px solid #1e293b; }
    .ai-section-title { font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.08em; color: #64748b; margin-bottom: 10px; }

    .ai-overview { background: #0f1e3a; border-radius: 10px; padding: 14px; margin: 0; }
    .ai-overview p { margin: 0; font-size: 13px; line-height: 1.6; color: #cbd5e1; }
    .ai-market-view { font-size: 12px; color: #94a3b8; margin-top: 8px; font-style: italic; }
    .ai-confidence { font-size: 11px; color: #64748b; margin-top: 4px; }

    .ai-tabs { display: flex; gap: 2px; padding: 12px 20px 0; flex-shrink: 0; }
    .ai-tab {
      flex: 1; padding: 8px; text-align: center; font-size: 12px; font-weight: 600;
      border-radius: 8px 8px 0 0; cursor: pointer; border: 1px solid transparent;
      border-bottom: none; transition: all 0.15s; color: #64748b;
    }
    .ai-tab.active { background: #1e293b; color: #e2e8f0; border-color: #334155; }
    .ai-tab:not(.active):hover { color: #94a3b8; }

    .ai-tab-content { padding: 0; }

    .suggestion-card {
      background: #1e293b; border: 1px solid #334155; border-radius: 10px;
      padding: 14px; margin: 12px 20px;
      transition: border-color 0.15s;
    }
    .suggestion-card:hover { border-color: #475569; }
    .suggestion-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .suggestion-symbol { font-size: 12px; font-weight: 700; color: #93c5fd; font-family: monospace; }
    .action-chip {
      display: inline-block; padding: 3px 10px; border-radius: 20px;
      font-size: 11px; font-weight: 700; text-transform: uppercase;
    }
    .action-hold    { background: #052e16; color: #4ade80; }
    .action-reduce  { background: #1c1408; color: #fbbf24; }
    .action-close   { background: #1c0505; color: #f87171; }
    .action-hedge   { background: #0c1a3e; color: #60a5fa; }
    .action-roll    { background: #1a0c3e; color: #c084fc; }

    .urgency-dot {
      display: inline-block; width: 7px; height: 7px;
      border-radius: 50%; margin-right: 4px;
    }
    .urgency-immediate { background: #f87171; animation: ai-pulse 1s infinite; }
    .urgency-monitor   { background: #fbbf24; }
    .urgency-optional  { background: #4ade80; }

    .suggestion-reason { font-size: 12px; color: #94a3b8; margin: 6px 0 4px; line-height: 1.5; }
    .suggestion-alt { font-size: 11px; color: #64748b; font-style: italic; }
    .suggestion-meta { font-size: 11px; color: #475569; margin-top: 6px; display: flex; align-items: center; }

    .ai-automation-section {
      padding: 16px 20px;
      background: #0f172a;
      border-bottom: 1px solid #1e293b;
    }
    .ai-toggle-row { display: flex; align-items: center; justify-content: space-between; }
    .ai-toggle-label { font-size: 13px; font-weight: 600; }
    .ai-toggle-desc { font-size: 11px; color: #64748b; margin-top: 4px; }
    .ai-toggle {
      position: relative; display: inline-block; width: 44px; height: 24px;
    }
    .ai-toggle input { opacity: 0; width: 0; height: 0; }
    .ai-toggle-slider {
      position: absolute; cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background: #334155; border-radius: 24px;
      transition: 0.2s;
    }
    .ai-toggle-slider:before {
      position: absolute; content: '';
      height: 18px; width: 18px; left: 3px; bottom: 3px;
      background: white; border-radius: 50%; transition: 0.2s;
    }
    .ai-toggle input:checked + .ai-toggle-slider { background: #6366f1; }
    .ai-toggle input:checked + .ai-toggle-slider:before { transform: translateX(20px); }

    .ai-actions-bar { display: flex; gap: 8px; padding: 12px 20px; flex-shrink: 0; border-top: 1px solid #1e293b; }
    .ai-btn {
      flex: 1; padding: 10px; border: none; border-radius: 8px;
      font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s;
    }
    .ai-btn-primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; }
    .ai-btn-primary:hover { opacity: 0.9; }
    .ai-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .ai-btn-secondary { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
    .ai-btn-secondary:hover { color: #e2e8f0; }

    .ai-loading {
      display: flex; flex-direction: column; align-items: center;
      justify-content: center; padding: 40px;
      color: #64748b; font-size: 13px; gap: 12px;
    }
    .ai-spinner {
      width: 32px; height: 32px; border: 3px solid #334155;
      border-top-color: #6366f1; border-radius: 50%;
      animation: ai-spin 0.8s linear infinite;
    }
    @keyframes ai-spin { to { transform: rotate(360deg); } }

    .ai-empty { text-align: center; padding: 32px 20px; color: #64748b; font-size: 13px; }
    .ai-error { background: #1c0505; border: 1px solid #991b1b; border-radius: 10px;
      padding: 12px 16px; margin: 12px 20px; color: #fca5a5; font-size: 12px; }

    .memory-item {
      background: #1e293b; border: 1px solid #334155; border-radius: 8px;
      padding: 12px; margin: 10px 20px; font-size: 11px;
    }
    .memory-meta { color: #64748b; margin-bottom: 6px; }
    .memory-summary { color: #94a3b8; line-height: 1.5; }
    .memory-verdict { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700; margin-top: 6px; }
    .verdict-correct { background: #052e16; color: #4ade80; }
    .verdict-incorrect { background: #1c0505; color: #f87171; }
    .verdict-neutral { background: #1e293b; color: #94a3b8; }
    .verdict-pending { background: #1c1408; color: #fbbf24; }

    /* Confirmation Modal */
    #ai-confirm-modal {
      display: none; position: fixed; inset: 0; z-index: 10000;
      background: rgba(0,0,0,0.7); align-items: center; justify-content: center;
    }
    #ai-confirm-modal.open { display: flex; }
    .ai-modal-box {
      background: #1e293b; border: 1px solid #334155; border-radius: 14px;
      padding: 28px; max-width: 360px; width: 90%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    }
    .ai-modal-title { font-size: 16px; font-weight: 700; margin-bottom: 12px; }
    .ai-modal-body { font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 20px; }
    .ai-modal-warning { background: #1c0505; border: 1px solid #991b1b; border-radius: 8px;
      padding: 10px 14px; font-size: 12px; color: #fca5a5; margin-bottom: 16px; }
    .ai-modal-actions { display: flex; gap: 10px; }
    .ai-modal-confirm { flex: 1; padding: 10px; background: #dc2626; color: #fff;
      border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
    .ai-modal-confirm:hover { background: #b91c1c; }
    .ai-modal-cancel { flex: 1; padding: 10px; background: #334155; color: #94a3b8;
      border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
    .ai-modal-cancel:hover { color: #e2e8f0; }
  `;

    // ── Helpers ─────────────────────────────────────────────────────────────────

    function riskClass(level) {
        const map = { low: 'ai-risk-low', medium: 'ai-risk-medium', high: 'ai-risk-high', critical: 'ai-risk-critical' };
        return map[level] || 'ai-risk-unknown';
    }

    function actionClass(action) {
        const map = { hold: 'action-hold', reduce: 'action-reduce', close: 'action-close', hedge: 'action-hedge', roll: 'action-roll' };
        return map[action] || 'action-hold';
    }

    function urgencyClass(urgency) {
        const map = { immediate: 'urgency-immediate', monitor: 'urgency-monitor', optional: 'urgency-optional' };
        return map[urgency] || 'urgency-optional';
    }

    function fmtTime(iso) {
        if (!iso) return '—';
        try { return new Date(iso).toLocaleTimeString(); } catch { return iso; }
    }

    function injectStyles() {
        if (document.getElementById('ai-panel-styles')) return;
        const style = document.createElement('style');
        style.id = 'ai-panel-styles';
        style.textContent = STYLES;
        document.head.appendChild(style);
    }

    // ── API ─────────────────────────────────────────────────────────────────────

    async function fetchStatus() {
        const r = await fetch(`${API_BASE}/status`);
        return r.json();
    }

    async function triggerAnalyze() {
        const r = await fetch(`${API_BASE}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }, body: '{}'
        });
        return r.json();
    }

    async function fetchHistory(n = 10) {
        const r = await fetch(`${API_BASE}/history?n=${n}`);
        return r.json();
    }

    async function toggleAuto(enabled) {
        const r = await fetch(`${API_BASE}/toggle-auto`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled }),
        });
        return r.json();
    }

    // ── Rendering ───────────────────────────────────────────────────────────────

    function renderLoading(msg = 'Analysing positions...') {
        return `<div class="ai-loading"><div class="ai-spinner"></div><span>${msg}</span></div>`;
    }

    function renderSuggestions(data) {
        const ai = (data && data.ai_response) || {};
        const risk = ai.risk_level || 'unknown';
        const suggestions = ai.suggestions || [];
        const pos = (data && data.position_summary) || {};

        let html = `
      <div class="ai-section">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
          <span class="ai-section-title">Portfolio Risk</span>
          <span class="ai-risk-badge ${riskClass(risk)}">${risk.toUpperCase()}</span>
        </div>
        <div class="ai-overview">
          <p>${ai.summary || 'No summary available.'}</p>
          <p class="ai-market-view">📈 ${ai.market_view || '—'}</p>
          <p class="ai-confidence">Confidence: ${((ai.confidence || 0) * 100).toFixed(0)}% · Positions: ${pos.count || 0} · Flagged: ${pos.flagged || 0} · P&L: ${pos.total_pnl != null ? pos.total_pnl.toFixed(2) : '—'}</p>
        </div>
        ${ai.portfolio_advice ? `<div style="margin-top:12px;font-size:12px;color:#94a3b8;line-height:1.6;">${ai.portfolio_advice}</div>` : ''}
      </div>`;

        if (suggestions.length === 0) {
            html += `<div class="ai-empty">No suggestions at this time. Portfolio looks stable.</div>`;
        } else {
            suggestions.forEach(s => {
                html += `
        <div class="suggestion-card">
          <div class="suggestion-header">
            <span class="suggestion-symbol">${s.position_id || '—'}</span>
            <span class="action-chip ${actionClass(s.action)}">${s.action || '—'}</span>
          </div>
          <div class="suggestion-meta">
            <span class="urgency-dot ${urgencyClass(s.urgency)}"></span>
            ${s.urgency || 'optional'}
          </div>
          <div class="suggestion-reason">${s.reason || ''}</div>
          ${s.alternative ? `<div class="suggestion-alt">Alternative: ${s.alternative}</div>` : ''}
        </div>`;
            });
        }
        return html;
    }

    function renderMemory(records) {
        if (!records || records.length === 0) {
            return `<div class="ai-empty">No past decisions recorded yet.<br>Trigger an analysis to start building the learning log.</div>`;
        }
        return records.slice().reverse().map(r => {
            const verdict = r.verdict || 'pending';
            const vClass = `verdict-${verdict}`;
            return `
      <div class="memory-item">
        <div class="memory-meta">${r.timestamp ? r.timestamp.replace('T', ' ').slice(0, 16) : '—'} · ${r.position_count || 0} positions · risk: <strong>${r.risk_level || '—'}</strong></div>
        <div class="memory-summary">${r.summary || '—'}</div>
        <div>
          <span class="memory-verdict ${vClass}">${verdict.toUpperCase()}</span>
          <span style="font-size:10px;color:#475569;margin-left:8px;">action: ${r.action_taken || '—'} · conf: ${((r.confidence || 0) * 100).toFixed(0)}%</span>
          ${r.pnl_before != null ? `<span style="font-size:10px;color:#475569;margin-left:8px;">P&L before: ${r.pnl_before.toFixed(2)}</span>` : ''}
        </div>
      </div>`;
        }).join('');
    }

    function renderError(msg) {
        return `<div class="ai-error">⚠️ ${msg}</div>`;
    }

    // ── Panel DOM ───────────────────────────────────────────────────────────────

    function buildPanel() {
        // FAB
        const fab = document.createElement('button');
        fab.id = 'ai-fab';
        fab.innerHTML = `<span class="ai-fab-dot"></span>🤖 AI Advisor`;
        fab.addEventListener('click', () => togglePanel());
        document.body.appendChild(fab);

        // Panel
        const panel = document.createElement('div');
        panel.id = 'ai-panel';
        panel.innerHTML = `
      <div class="ai-panel-header">
        <div class="ai-panel-title">🤖 Options AI Advisor</div>
        <button class="ai-close-btn" id="ai-close-btn">✕</button>
      </div>

      <div class="ai-automation-section">
        <div class="ai-toggle-row">
          <div>
            <div class="ai-toggle-label">Automation Mode</div>
            <div class="ai-toggle-desc" id="auto-desc">Suggestion only — AI advises, you decide.</div>
          </div>
          <label class="ai-toggle" title="Enable automated trading">
            <input type="checkbox" id="auto-toggle">
            <span class="ai-toggle-slider"></span>
          </label>
        </div>
      </div>

      <div class="ai-tabs">
        <div class="ai-tab active" data-tab="suggestions" id="tab-suggestions">💡 Suggestions</div>
        <div class="ai-tab" data-tab="memory" id="tab-memory">📚 Memory</div>
      </div>

      <div class="ai-panel-body">
        <div id="ai-tab-content" class="ai-tab-content">
          ${renderLoading('Loading status...')}
        </div>
      </div>

      <div class="ai-actions-bar">
        <button class="ai-btn ai-btn-primary" id="ai-analyze-btn">⚡ Analyse Now</button>
        <button class="ai-btn ai-btn-secondary" id="ai-refresh-btn">↻ Refresh</button>
      </div>`;
        document.body.appendChild(panel);

        // Confirmation modal
        const modal = document.createElement('div');
        modal.id = 'ai-confirm-modal';
        modal.innerHTML = `
      <div class="ai-modal-box">
        <div class="ai-modal-title">⚠️ Enable Automation Mode?</div>
        <div class="ai-modal-body">
          When enabled, the AI will automatically execute <strong>critical, immediate</strong> suggestions
          without your confirmation. All actions are logged and subject to a daily loss circuit breaker.
        </div>
        <div class="ai-modal-warning">
          🚨 Automated trading carries real financial risk. Only enable this if you understand the implications.
          The bot will pause automation if daily losses exceed the configured limit.
        </div>
        <div class="ai-modal-actions">
          <button class="ai-modal-cancel" id="modal-cancel">Cancel</button>
          <button class="ai-modal-confirm" id="modal-confirm">Yes, Enable Automation</button>
        </div>
      </div>`;
        document.body.appendChild(modal);

        // Wire events
        document.getElementById('ai-close-btn').addEventListener('click', () => togglePanel(false));

        document.querySelectorAll('.ai-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                _activeTab = tab.dataset.tab;
                document.querySelectorAll('.ai-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                renderActiveTab();
            });
        });

        document.getElementById('ai-analyze-btn').addEventListener('click', runAnalysis);
        document.getElementById('ai-refresh-btn').addEventListener('click', loadData);

        // Automation toggle
        document.getElementById('auto-toggle').addEventListener('change', (e) => {
            if (e.target.checked) {
                // Show confirmation modal
                e.target.checked = false; // revert until confirmed
                document.getElementById('ai-confirm-modal').classList.add('open');
            } else {
                disableAutomation();
            }
        });

        document.getElementById('modal-cancel').addEventListener('click', () => {
            document.getElementById('ai-confirm-modal').classList.remove('open');
        });

        document.getElementById('modal-confirm').addEventListener('click', async () => {
            document.getElementById('ai-confirm-modal').classList.remove('open');
            await enableAutomation();
        });
    }

    // ── Panel Logic ─────────────────────────────────────────────────────────────

    function togglePanel(force) {
        _panelOpen = force !== undefined ? force : !_panelOpen;
        const panel = document.getElementById('ai-panel');
        if (_panelOpen) {
            panel.classList.add('open');
            loadData();
            startAutoRefresh();
        } else {
            panel.classList.remove('open');
            stopAutoRefresh();
        }
    }

    function startAutoRefresh() {
        stopAutoRefresh();
        _refreshTimer = setInterval(loadData, REFRESH_INTERVAL_MS);
    }

    function stopAutoRefresh() {
        if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
    }

    async function loadData() {
        const content = document.getElementById('ai-tab-content');
        if (!content) return;

        if (_activeTab === 'memory') {
            content.innerHTML = renderLoading('Loading history...');
            try {
                const resp = await fetchHistory(20);
                if (resp.success) {
                    content.innerHTML = renderMemory(resp.data);
                } else {
                    content.innerHTML = renderError(resp.error || 'Failed to load history');
                }
            } catch (e) {
                content.innerHTML = renderError(`Network error: ${e.message}`);
            }
            return;
        }

        // Status + last result
        content.innerHTML = renderLoading('Loading analysis...');
        try {
            const statusResp = await fetchStatus();
            if (statusResp.success) {
                const status = statusResp.data;
                _automationEnabled = status.automation_mode;
                const toggle = document.getElementById('auto-toggle');
                const desc = document.getElementById('auto-desc');
                if (toggle) toggle.checked = _automationEnabled;
                if (desc) desc.textContent = _automationEnabled
                    ? '⚡ Automation ACTIVE — AI will auto-execute critical actions.'
                    : 'Suggestion only — AI advises, you decide.';
            }

            // Use last result if available
            if (_lastData) {
                content.innerHTML = renderSuggestions(_lastData);
            } else {
                content.innerHTML = `<div class="ai-empty">No analysis yet. Click "Analyse Now" to start.</div>`;
            }
        } catch (e) {
            content.innerHTML = renderError(`Could not reach AI engine: ${e.message}`);
        }
    }

    function renderActiveTab() {
        loadData();
    }

    async function runAnalysis() {
        const btn = document.getElementById('ai-analyze-btn');
        const content = document.getElementById('ai-tab-content');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ Analysing...'; }
        if (content) content.innerHTML = renderLoading('Running full AI analysis...');
        try {
            const resp = await triggerAnalyze();
            if (resp.success) {
                _lastData = resp.data;
                if (_activeTab === 'suggestions') content.innerHTML = renderSuggestions(_lastData);
            } else {
                if (content) content.innerHTML = renderError(resp.error || 'Analysis failed');
            }
        } catch (e) {
            if (content) content.innerHTML = renderError(`Network error: ${e.message}`);
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '⚡ Analyse Now'; }
        }
    }

    async function enableAutomation() {
        try {
            const resp = await toggleAuto(true);
            if (resp.success) {
                _automationEnabled = true;
                const toggle = document.getElementById('auto-toggle');
                const desc = document.getElementById('auto-desc');
                if (toggle) toggle.checked = true;
                if (desc) desc.textContent = '⚡ Automation ACTIVE — AI will auto-execute critical actions.';
            }
        } catch { }
    }

    async function disableAutomation() {
        try {
            const resp = await toggleAuto(false);
            if (resp.success) {
                _automationEnabled = false;
                const desc = document.getElementById('auto-desc');
                if (desc) desc.textContent = 'Suggestion only — AI advises, you decide.';
            }
        } catch { }
    }

    // ── Init ─────────────────────────────────────────────────────────────────────

    function init() {
        // Skip on mobile devices — AI Advisor is desktop-only
        const isMobile = window.innerWidth < 768 || /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(navigator.userAgent.toLowerCase()) || navigator.maxTouchPoints > 0;
        if (isMobile) {
            console.info('[OptionsAI] Skipping AI Advisor on mobile device.');
            return;
        }

        injectStyles();
        buildPanel();
        console.info('[OptionsAI] Panel ready. Click "🤖 AI Advisor" to open.');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
