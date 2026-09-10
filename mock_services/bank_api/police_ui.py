"""mock_services/bank_api/police_ui.py — Interactive Police LEA Incident Dashboard HTML/JS app.

Single-Page Web Application served at GET /police or GET /police-app.
Provides law enforcement officers with an authorized, data-minimized investigation interface.
"""

POLICE_APP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberShield — Law Enforcement Alert & Dispatch Command</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #0B0F19;
            --surface-dark: #111827;
            --card-bg: #1F2937;
            --border-color: #374151;
            --text-main: #F9FAFB;
            --text-muted: #9CA3AF;
            --cyan-accent: #06B6D4;
            --blue-accent: #3B82F6;
            --orange-alert: #F97316;
            --red-critical: #EF4444;
            --amber-warn: #F59E0B;
            --green-safe: #10B981;
            --purple-badge: #8B5CF6;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            background-color: var(--surface-dark);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-icon {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--cyan-accent), var(--blue-accent));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 18px;
            color: #fff;
        }
        .brand-text h1 { font-size: 18px; font-weight: 700; color: var(--text-main); letter-spacing: 0.5px; }
        .brand-text p { font-size: 12px; color: var(--text-muted); }
        .role-badge {
            background: rgba(6, 182, 212, 0.15);
            color: var(--cyan-accent);
            border: 1px solid rgba(6, 182, 212, 0.4);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .role-dot { width: 8px; height: 8px; background-color: var(--green-safe); border-radius: 50%; box-shadow: 0 0 8px var(--green-safe); }

        main {
            flex: 1;
            padding: 24px 32px;
            max-width: 1600px;
            margin: 0 auto;
            width: 100%;
        }

        /* Metric Cards */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .metric-card {
            background: var(--surface-dark);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .metric-card .title { font-size: 13px; color: var(--text-muted); font-weight: 500; }
        .metric-card .value { font-size: 28px; font-weight: 800; }
        .metric-card.critical .value { color: var(--red-critical); }
        .metric-card.acknowledged .value { color: var(--blue-accent); }
        .metric-card.investigation .value { color: var(--amber-warn); }
        .metric-card.resolved .value { color: var(--green-safe); }

        /* Filter Controls & Search */
        .controls-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            gap: 16px;
            flex-wrap: wrap;
        }
        .filters { display: flex; gap: 8px; }
        .btn-filter {
            background: var(--surface-dark);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-filter.active, .btn-filter:hover {
            background: var(--card-bg);
            color: var(--text-main);
            border-color: var(--cyan-accent);
        }
        .btn-refresh {
            background: linear-gradient(135deg, var(--blue-accent), var(--cyan-accent));
            border: none;
            color: white;
            padding: 9px 20px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Queue Table */
        .table-container {
            background: var(--surface-dark);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }
        th {
            background: #182232;
            padding: 14px 20px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border-color);
        }
        td {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            vertical-align: middle;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(255, 255, 255, 0.02); }

        .badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            display: inline-block;
        }
        .badge.critical { background: rgba(239, 68, 68, 0.15); color: var(--red-critical); border: 1px solid rgba(239, 68, 68, 0.4); }
        .badge.high { background: rgba(249, 115, 22, 0.15); color: var(--orange-alert); border: 1px solid rgba(249, 115, 22, 0.4); }
        .badge.medium { background: rgba(245, 158, 11, 0.15); color: var(--amber-warn); border: 1px solid rgba(245, 158, 11, 0.4); }
        .badge.sent { background: rgba(249, 115, 22, 0.2); color: #FFA500; border: 1px solid #FFA500; }
        .badge.acknowledged { background: rgba(59, 130, 246, 0.2); color: var(--blue-accent); border: 1px solid var(--blue-accent); }
        .badge.under_investigation { background: rgba(245, 158, 11, 0.2); color: var(--amber-warn); border: 1px solid var(--amber-warn); }
        .badge.resolved, .badge.closed { background: rgba(16, 185, 129, 0.2); color: var(--green-safe); border: 1px solid var(--green-safe); }

        .btn-action {
            background: var(--card-bg);
            border: 1px solid var(--cyan-accent);
            color: var(--cyan-accent);
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-action:hover { background: var(--cyan-accent); color: #000; }

        /* Modal Detail View */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(4px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            padding: 20px;
        }
        .modal-overlay.active { display: flex; }
        .modal-content {
            background: var(--surface-dark);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            width: 100%;
            max-width: 1000px;
            max-height: 90vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
        }
        .modal-header {
            padding: 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #141E2E;
        }
        .modal-header h2 { font-size: 20px; font-weight: 700; display: flex; align-items: center; gap: 12px; }
        .btn-close {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 24px;
            cursor: pointer;
        }
        .modal-body { padding: 24px; display: flex; flex-direction: column; gap: 24px; }

        .section-box {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 18px;
        }
        .section-box h3 {
            font-size: 14px;
            font-weight: 700;
            color: var(--cyan-accent);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .info-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; }
        .info-row:last-child { border-bottom: none; }
        .info-label { color: var(--text-muted); font-weight: 500; }
        .info-value { font-weight: 600; font-family: 'JetBrains Mono', monospace; }

        /* Money Trail Chain */
        .chain-timeline { display: flex; flex-direction: column; gap: 10px; }
        .chain-step {
            background: rgba(0,0,0,0.25);
            border-left: 4px solid var(--cyan-accent);
            padding: 12px 16px;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 13px;
        }
        .chain-step .accounts { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
        .chain-step .amount { color: var(--green-safe); font-weight: 700; }

        .action-footer {
            padding: 20px 24px;
            background: #141E2E;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
        }
        .status-select {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
        }
        .btn-ack {
            background: var(--blue-accent);
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
        }
        .btn-update {
            background: var(--green-safe);
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
        }

        .mono { font-family: 'JetBrains Mono', monospace; }
        .empty-state { padding: 40px; text-align: center; color: var(--text-muted); font-size: 14px; }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="brand-icon">POL</div>
            <div class="brand-text">
                <h1>Police LEA Alert & Investigation Command</h1>
                <p>CyberShield Strategic Bank Escapes & Egress Interception</p>
            </div>
        </div>
        <div class="role-badge">
            <div class="role-dot"></div>
            <span>Role: POLICE_OFFICER (Authorized LEA)</span>
        </div>
    </header>

    <main>
        <!-- Metrics Bar -->
        <div class="metrics-grid">
            <div class="metric-card critical">
                <div class="title">Total Active Escalations</div>
                <div class="value" id="m-total">0</div>
            </div>
            <div class="metric-card acknowledged">
                <div class="title">Acknowledged Receipts</div>
                <div class="value" id="m-ack">0</div>
            </div>
            <div class="metric-card investigation">
                <div class="title">Under Active Investigation</div>
                <div class="value" id="m-inv">0</div>
            </div>
            <div class="metric-card resolved">
                <div class="title">Resolved / Closed Cases</div>
                <div class="value" id="m-res">0</div>
            </div>
        </div>

        <!-- Controls -->
        <div class="controls-bar">
            <div class="filters">
                <button class="btn-filter active" onclick="filterQueue('ALL')">All Alerts</button>
                <button class="btn-filter" onclick="filterQueue('CRITICAL')">Critical Priority</button>
                <button class="btn-filter" onclick="filterQueue('SENT')">New / Unacknowledged</button>
                <button class="btn-filter" onclick="filterQueue('ACKNOWLEDGED')">Acknowledged</button>
                <button class="btn-filter" onclick="filterQueue('UNDER_INVESTIGATION')">Under Investigation</button>
            </div>
            <button class="btn-refresh" onclick="fetchAlerts()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
                Sync LEA Queue
            </button>
        </div>

        <!-- Queue Table -->
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Police Alert ID</th>
                        <th>Correlated Case ID</th>
                        <th>Priority</th>
                        <th>Status</th>
                        <th>Suspected Egress Terminal</th>
                        <th>Escalation Time</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="queue-body">
                    <tr><td colspan="7" class="empty-state">Loading police escalation queue...</td></tr>
                </tbody>
            </table>
        </div>
    </main>

    <!-- Detail Modal -->
    <div class="modal-overlay" id="detail-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>
                    <span id="modal-alert-id" class="mono">POL-ALERT-XXXX</span>
                    <span id="modal-priority-badge" class="badge critical">CRITICAL</span>
                </h2>
                <button class="btn-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <!-- Grid 1: Incident & Origin -->
                <div class="grid-2">
                    <div class="section-box">
                        <h3>Incident Summary</h3>
                        <div class="info-row"><span class="info-label">Case ID:</span><span class="info-value" id="d-case-id">-</span></div>
                        <div class="info-row"><span class="info-label">Risk Band / Score:</span><span class="info-value" id="d-risk">-</span></div>
                        <div class="info-row"><span class="info-label">Escalation Reason:</span><span class="info-value" id="d-reason">-</span></div>
                        <div class="info-row"><span class="info-label">Flagged Mule Account:</span><span class="info-value" id="d-account">-</span></div>
                    </div>
                    <div class="section-box">
                        <h3>Origin Transaction</h3>
                        <div class="info-row"><span class="info-label">Transaction ID:</span><span class="info-value" id="d-tx-id">-</span></div>
                        <div class="info-row"><span class="info-label">Victim &rarr; Mule:</span><span class="info-value" id="d-tx-leg">-</span></div>
                        <div class="info-row"><span class="info-label">Origin Amount:</span><span class="info-value" id="d-tx-amt" style="color:var(--green-safe);">-</span></div>
                        <div class="info-row"><span class="info-label">Channel & Status:</span><span class="info-value" id="d-tx-status">-</span></div>
                    </div>
                </div>

                <!-- Money Trail -->
                <div class="section-box">
                    <h3>Provenanced Downstream Money Trail</h3>
                    <div class="chain-timeline" id="d-money-trail">
                        <div class="empty-state">No money trail records.</div>
                    </div>
                </div>

                <!-- ATM & Egress Evidence -->
                <div class="grid-2">
                    <div class="section-box">
                        <h3>Recorded ATM / Cashout Attempts</h3>
                        <div id="d-withdrawals" class="chain-timeline">
                            <div class="empty-state">No withdrawal attempts recorded.</div>
                        </div>
                    </div>
                    <div class="section-box">
                        <h3>Nearby Alternative Egress Terminals</h3>
                        <div id="d-nearby" class="chain-timeline">
                            <div class="empty-state">No nearby terminals computed.</div>
                        </div>
                    </div>
                </div>

                <!-- Timeline & Evidence Reasons -->
                <div class="grid-2">
                    <div class="section-box">
                        <h3>Chronological Evidence Timeline</h3>
                        <div id="d-timeline" class="chain-timeline"></div>
                    </div>
                    <div class="section-box">
                        <h3>Bank Escalation Evidence</h3>
                        <ul id="d-evidence-list" style="padding-left: 20px; font-size: 13px; color: var(--text-main); display: flex; flex-direction: column; gap: 6px;"></ul>
                    </div>
                </div>
            </div>
            <div class="action-footer">
                <div>
                    <button class="btn-ack" id="btn-ack-action" onclick="acknowledgeCurrentAlert()">ACKNOWLEDGE RECEIPT</button>
                </div>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <span style="font-size: 13px; color: var(--text-muted);">Investigation Status:</span>
                    <select id="status-dropdown" class="status-select">
                        <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                        <option value="UNDER_INVESTIGATION">UNDER_INVESTIGATION</option>
                        <option value="RESOLVED">RESOLVED</option>
                        <option value="CLOSED">CLOSED</option>
                    </select>
                    <button class="btn-update" onclick="updateCurrentStatus()">UPDATE STATUS</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let allAlerts = [];
        let activeFilter = 'ALL';
        let currentAlert = null;

        async function fetchAlerts() {
            try {
                const res = await fetch('/police-alerts', {
                    headers: { 'X-User-Role': 'POLICE_OFFICER' }
                });
                if (res.ok) {
                    const data = await res.json();
                    allAlerts = data.police_alerts || [];
                    renderQueue();
                    renderMetrics();
                }
            } catch (err) {
                console.error("Failed to fetch LEA police alerts:", err);
            }
        }

        function renderMetrics() {
            document.getElementById('m-total').innerText = allAlerts.length;
            document.getElementById('m-ack').innerText = allAlerts.filter(a => a.alert_status === 'ACKNOWLEDGED').length;
            document.getElementById('m-inv').innerText = allAlerts.filter(a => a.alert_status === 'UNDER_INVESTIGATION').length;
            document.getElementById('m-res').innerText = allAlerts.filter(a => a.alert_status === 'RESOLVED' || a.alert_status === 'CLOSED').length;
        }

        function filterQueue(status) {
            activeFilter = status;
            document.querySelectorAll('.btn-filter').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            renderQueue();
        }

        function renderQueue() {
            const body = document.getElementById('queue-body');
            let filtered = allAlerts;
            if (activeFilter === 'CRITICAL') filtered = allAlerts.filter(a => a.priority === 'CRITICAL');
            else if (activeFilter === 'SENT') filtered = allAlerts.filter(a => a.alert_status === 'SENT' || a.alert_status === 'PENDING');
            else if (activeFilter === 'ACKNOWLEDGED') filtered = allAlerts.filter(a => a.alert_status === 'ACKNOWLEDGED');
            else if (activeFilter === 'UNDER_INVESTIGATION') filtered = allAlerts.filter(a => a.alert_status === 'UNDER_INVESTIGATION');

            if (filtered.length === 0) {
                body.innerHTML = `<tr><td colspan="7" class="empty-state">No police alerts match active filter.</td></tr>`;
                return;
            }

            body.innerHTML = filtered.map(alert => {
                const inc = alert.incident || {};
                const termId = (alert.withdrawal_attempts && alert.withdrawal_attempts.length > 0) ? alert.withdrawal_attempts[0].terminal_id : (alert.nearby_terminals && alert.nearby_terminals.length > 0 ? alert.nearby_terminals[0].terminal_id : 'ATM-SBI-ND-042');
                const prioClass = (alert.priority || 'HIGH').toLowerCase();
                const statusClass = (alert.alert_status || 'SENT').toLowerCase();

                return `
                    <tr>
                        <td class="mono" style="font-weight:700;">${alert.police_alert_id}</td>
                        <td class="mono">${alert.case_id}</td>
                        <td><span class="badge ${prioClass}">${alert.priority}</span></td>
                        <td><span class="badge ${statusClass}">${alert.alert_status}</span></td>
                        <td class="mono">${termId}</td>
                        <td>${new Date(alert.created_at).toLocaleTimeString()}</td>
                        <td><button class="btn-action" onclick="openModal('${alert.police_alert_id}')">VIEW CASE</button></td>
                    </tr>
                `;
            }).join('');
        }

        function openModal(alertId) {
            currentAlert = allAlerts.find(a => a.police_alert_id === alertId);
            if (!currentAlert) return;

            document.getElementById('modal-alert-id').innerText = currentAlert.police_alert_id;
            const pBadge = document.getElementById('modal-priority-badge');
            pBadge.innerText = currentAlert.priority;
            pBadge.className = `badge ${(currentAlert.priority || 'HIGH').toLowerCase()}`;

            const inc = currentAlert.incident || {};
            document.getElementById('d-case-id').innerText = currentAlert.case_id;
            document.getElementById('d-risk').innerText = `${inc.risk_level || 'HIGH'} (${((inc.risk_score || 0) * 100).toFixed(0)}%)`;
            document.getElementById('d-reason').innerText = inc.reason_for_escalation || 'Explicit Bank Official Approval';
            document.getElementById('d-account').innerText = inc.flagged_account_id || '-';

            const orig = currentAlert.origin_transaction || {};
            document.getElementById('d-tx-id').innerText = orig.transaction_id || '-';
            document.getElementById('d-tx-leg').innerText = `${orig.origin_account || 'Victim'} → ${orig.destination_account || 'Mule'}`;
            document.getElementById('d-tx-amt').innerText = `₹${(orig.amount || 0).toLocaleString()}`;
            document.getElementById('d-tx-status').innerText = `${orig.channel || 'IMPS'} (${orig.confirmation_status || 'UNCONFIRMED'})`;

            // Money Trail
            const trail = currentAlert.money_trail || [];
            document.getElementById('d-money-trail').innerHTML = trail.length ? trail.map(t => `
                <div class="chain-step">
                    <span class="accounts">Hop ${t.hop}: ${t.source_account} &rarr; ${t.destination_account}</span>
                    <span class="amount">₹${(t.amount || 0).toLocaleString()} (${t.channel})</span>
                </div>
            `).join('') : '<div class="empty-state">No money trail records.</div>';

            // Withdrawals
            const w = currentAlert.withdrawal_attempts || [];
            document.getElementById('d-withdrawals').innerHTML = w.length ? w.map(att => `
                <div class="chain-step">
                    <span class="accounts">${att.terminal_id} (${att.terminal_type})</span>
                    <span class="amount" style="color:${att.status === 'BLOCKED' ? 'var(--red-critical)' : 'var(--green-safe)'};">${att.status}: ₹${(att.amount || 0).toLocaleString()}</span>
                </div>
            `).join('') : '<div class="empty-state">No withdrawal attempts recorded.</div>';

            // Nearby Terminals
            const n = currentAlert.nearby_terminals || [];
            document.getElementById('d-nearby').innerHTML = n.length ? n.map(term => `
                <div class="chain-step">
                    <span class="accounts">${term.terminal_id} (${term.terminal_type || 'ATM'})</span>
                    <span style="color:var(--cyan-accent); font-weight:600;">${term.distance_km} km nearby</span>
                </div>
            `).join('') : '<div class="empty-state">No nearby terminals computed.</div>';

            // Timeline
            const tl = currentAlert.location_timeline || [];
            document.getElementById('d-timeline').innerHTML = tl.length ? tl.map(loc => `
                <div class="chain-step">
                    <span class="accounts">[${loc.event_type}] ${loc.terminal_id}</span>
                    <span style="color:var(--text-muted);">${new Date(loc.timestamp).toLocaleTimeString()}</span>
                </div>
            `).join('') : '<div class="empty-state">No location timeline.</div>';

            // Evidence
            const ev = currentAlert.evidence || [];
            document.getElementById('d-evidence-list').innerHTML = ev.map(e => `<li>${e}</li>`).join('');

            // Controls
            document.getElementById('status-dropdown').value = currentAlert.alert_status;
            document.getElementById('detail-modal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('detail-modal').classList.remove('active');
            currentAlert = null;
        }

        async function acknowledgeCurrentAlert() {
            if (!currentAlert) return;
            try {
                const res = await fetch(`/police-alerts/${currentAlert.police_alert_id}/acknowledge`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-User-Role': 'POLICE_OFFICER' },
                    body: JSON.stringify({ officer_id: 'DUTY-OFFICER-01', notes: 'Acknowledged via LEA Web Portal' })
                });
                if (res.ok) {
                    await fetchAlerts();
                    openModal(currentAlert.police_alert_id);
                    alert("Alert receipt ACKNOWLEDGED successfully!");
                }
            } catch (err) {
                console.error(err);
            }
        }

        async function updateCurrentStatus() {
            if (!currentAlert) return;
            const newStatus = document.getElementById('status-dropdown').value;
            try {
                const res = await fetch(`/police-alerts/${currentAlert.police_alert_id}/status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-User-Role': 'POLICE_OFFICER' },
                    body: JSON.stringify({ status: newStatus, officer_id: 'DUTY-OFFICER-01', notes: `Status changed to ${newStatus}` })
                });
                if (res.ok) {
                    await fetchAlerts();
                    openModal(currentAlert.police_alert_id);
                    alert(`Investigation status updated to ${newStatus}`);
                }
            } catch (err) {
                console.error(err);
            }
        }

        // Initial load & poll every 5s
        fetchAlerts();
        setInterval(fetchAlerts, 5000);
    </script>
</body>
</html>
"""
