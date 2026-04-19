/* ═══════════════════════════════════════════════════════
   CYBERTERM — Frontend Logic v2
   ═══════════════════════════════════════════════════════ */

// ── GLOBALS ──
let phonesData = [];
let autoRefresh = null;
let activeModalPhone = null;

// ── SIDEBAR / NAVIGATION ──
function initNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.toggle('active', link.getAttribute('href') === path);
  });

  const hamburger = document.getElementById('hamburger');
  const sidebar = document.getElementById('sidebar');
  if (hamburger && sidebar) {
    hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.addEventListener('click', (e) => {
      if (window.innerWidth <= 768 && sidebar.classList.contains('open')
          && !sidebar.contains(e.target) && e.target !== hamburger) {
        sidebar.classList.remove('open');
      }
    });
  }
}

// ── CLOCK ──
function updateClock() {
  const el = document.getElementById('topbarClock');
  if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}

// ── API HELPERS ──
async function apiGet(url) {
  const res = await fetch(url);
  if (res.status === 401) { window.location.href = '/login'; return null; }
  return res.json();
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { window.location.href = '/login'; return null; }
  return res.json();
}

// ── AUTH ──
async function doLogin(e) {
  e.preventDefault();
  const pass = document.getElementById('loginPassword').value;
  const errEl = document.getElementById('loginError');
  errEl.style.display = 'none';

  const data = await apiPost('/api/login', { password: pass });
  if (data && data.success) {
    window.location.href = '/dashboard';
  } else {
    errEl.textContent = '[ ACCESS DENIED ] Invalid credentials';
    errEl.style.display = 'block';
  }
}

async function doLogout() {
  await apiPost('/api/logout', {});
  window.location.href = '/login';
}

// ═══════════════════════ DASHBOARD ═══════════════════════

async function refreshDashboard() {
  const data = await apiGet('/api/phones');
  if (!data) return;
  phonesData = data.phones || [];
  renderStats();
  renderPhones();

  const ts = document.getElementById('lastUpdate');
  if (ts) ts.textContent = 'synced ' + new Date().toLocaleTimeString('en-US', { hour12: false });
}

function renderStats() {
  const el = (id) => document.getElementById(id);
  const total = phonesData.length;
  const connected = phonesData.filter(p => p.status === 'connected').length;
  const active = phonesData.filter(p => ['connected', 'active'].includes(p.status)).length;

  if (el('statTotal')) el('statTotal').textContent = total;
  if (el('statConnected')) el('statConnected').textContent = connected;
  if (el('statActive')) el('statActive').textContent = active;
  if (el('statHost')) el('statHost').textContent = window.location.hostname;

  // Update phone selector in terminal page
  const sel = document.getElementById('cmdPhone');
  if (sel) {
    sel.innerHTML = '';
    phonesData.forEach(p => {
      const opt = document.createElement('option');
      opt.value = JSON.stringify({ port: p.tunnel_port, user: p.user, id: p.id });
      opt.textContent = p.name + ' [:' + p.tunnel_port + ']';
      sel.appendChild(opt);
    });
  }

  const badge = document.getElementById('phoneBadge');
  if (badge) badge.textContent = total;
}

function renderPhones() {
  const grid = document.getElementById('phonesGrid');
  if (!grid) return;

  if (phonesData.length === 0) {
    grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">📡</div><div>No devices detected</div><div style="font-size:0.7rem;margin-top:0.3rem;color:var(--text-muted)">Run install.sh on a Termux device to connect</div></div>';
    return;
  }

  grid.innerHTML = phonesData.map((phone, idx) => {
    const s = phone.stats || {};
    const statusCls = phone.status || 'unknown';
    const batText = s.BAT || 'N/A';
    const portText = phone.tunnel_port || '—';
    const hasPass = phone.has_password ? '🔑' : '🔓';

    return '<div class="phone-card" onclick="openPhoneModal(' + idx + ')">' +
      '<div class="phone-card-header">' +
        '<div class="phone-name">' +
          '<span class="status-indicator ' + (statusCls === 'connected' || statusCls === 'active' ? 'on' : 'off') + '"></span>' +
          esc(phone.name) +
        '</div>' +
        '<span class="phone-status ' + statusCls + '">' + statusCls + '</span>' +
      '</div>' +
      '<div class="phone-summary">' +
        '<div class="phone-summary-item"><span class="label">Port</span><span class="value">' + portText + '</span></div>' +
        '<div class="phone-summary-item"><span class="label">User</span><span class="value">' + esc(phone.user) + '</span></div>' +
        '<div class="phone-summary-item"><span class="label">Bat</span><span class="value">' + esc(batText) + '</span></div>' +
        '<div class="phone-summary-item"><span class="label">Key</span><span class="value">' + hasPass + '</span></div>' +
        '<div class="phone-summary-item" style="margin-left:auto;color:var(--text-muted);font-size:0.6rem">click to open ▸</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

// ═══════════════════════ PHONE MODAL ═══════════════════════

function openPhoneModal(idx) {
  const phone = phonesData[idx];
  if (!phone) return;
  activeModalPhone = phone;

  const overlay = document.getElementById('phoneModalOverlay');
  if (!overlay) return;

  const s = phone.stats || {};
  const statusCls = phone.status || 'unknown';
  const batNum = parseInt(s.BAT) || 0;
  const memNum = parseInt(s.MEM) || 0;
  const storNum = parseInt(s.STORAGE) || 0;
  const tunnelUp = (s.TUNNEL || '').toUpperCase() === 'ACTIVE';

  const barColor = (val, invert) => {
    if (invert) return val < 60 ? 'green' : val < 85 ? 'yellow' : 'red';
    return val > 50 ? 'green' : val > 20 ? 'yellow' : 'red';
  };

  // Header
  document.getElementById('pmName').innerHTML =
    '<span class="status-indicator ' + (statusCls === 'connected' || statusCls === 'active' ? 'on' : 'off') + '"></span> ' +
    esc(phone.name) +
    ' <span class="phone-status ' + statusCls + '" style="margin-left:0.5rem">' + statusCls + '</span>';

  // Info tab
  document.getElementById('pmInfo').innerHTML =
    '<div class="phone-metrics">' +
      metricHTML('Battery', s.BAT, batNum, barColor(batNum, false)) +
      metricHTML('Memory', s.MEM, memNum, barColor(memNum, true)) +
      metricHTML('Storage', s.STORAGE, storNum, barColor(storNum, true)) +
      '<div class="metric"><span class="metric-label">Tunnel</span><span class="metric-value" style="color:' + (tunnelUp ? 'var(--green)' : 'var(--red)') + '">' + (tunnelUp ? 'ACTIVE' : esc(s.TUNNEL || 'N/A')) + '</span></div>' +
      '<div class="metric"><span class="metric-label">Processes</span><span class="metric-value">' + esc(s.PROCS || 'N/A') + '</span></div>' +
      '<div class="metric"><span class="metric-label">Port</span><span class="metric-value" style="color:var(--cyan)">' + (phone.tunnel_port || 'N/A') + '</span></div>' +
    '</div>' +
    '<div class="ssh-box" style="margin-top:1rem"><code>ssh -p ' + phone.tunnel_port + ' ' + esc(phone.user) + '@' + window.location.hostname + '</code></div>' +
    (phone.last_seen ? '<div style="margin-top:0.5rem;font-size:0.7rem;color:var(--text-muted)">Last seen: ' + esc(phone.last_seen) + '</div>' : '');

  // Reset terminal
  document.getElementById('pmTermOutput').innerHTML = '<span class="info">Ready. Type command or use quick actions.</span>';
  document.getElementById('pmTermInput').value = '';

  // Reset file browser
  currentBrowsePath = '/sdcard';
  fileSelectedPaths.clear();
  const fl = document.getElementById('fileList');
  if (fl) fl.innerHTML = '<div class="file-loading">Switch to Files tab to browse</div>';
  const bc = document.getElementById('fileBreadcrumb');
  if (bc) bc.textContent = '/sdcard';

  // Config tab — password
  const pwInput = document.getElementById('pmPassword');
  if (pwInput) pwInput.value = phone.ssh_password || '';

  // Show modal
  overlay.classList.add('active');
  switchModalTab('info');

  // Auto-load system info
  loadPhoneSysInfo();
}

function metricHTML(label, text, num, color) {
  return '<div class="metric">' +
    '<span class="metric-label">' + label + '</span>' +
    '<span class="metric-value">' + esc(text || 'N/A') + '</span>' +
    '<div class="progress"><div class="progress-fill ' + color + '" style="width:' + num + '%"></div></div>' +
  '</div>';
}

function closePhoneModal() {
  const overlay = document.getElementById('phoneModalOverlay');
  if (overlay) overlay.classList.remove('active');
  activeModalPhone = null;
}

function switchModalTab(tab) {
  document.querySelectorAll('.phone-modal-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.phone-modal-section').forEach(s => s.classList.toggle('active', s.id === 'pmSec_' + tab));
  if (tab === 'files' && activeModalPhone) {
    fileBrowseTo(currentBrowsePath || '/sdcard');
  }
}

// ── MODAL TERMINAL ──
async function runModalCmd() {
  const phone = activeModalPhone;
  if (!phone) return;
  const input = document.getElementById('pmTermInput');
  const output = document.getElementById('pmTermOutput');
  const cmd = input.value.trim();
  if (!cmd) return;

  output.innerHTML += '\n<span class="prompt">' + esc(phone.user) + '@phone:' + phone.tunnel_port + '$</span> ' + esc(cmd) + '\n<span class="info">executing...</span>';
  output.scrollTop = output.scrollHeight;

  const data = await apiPost('/api/command', { port: phone.tunnel_port, user: phone.user, command: cmd });

  // Remove "executing..."
  const lines = output.innerHTML.split('\n');
  lines.pop();
  output.innerHTML = lines.join('\n');

  if (data) {
    if (data.output) output.innerHTML += '\n' + esc(data.output);
    if (data.error && data.code !== 0) output.innerHTML += '\n<span class="error">' + esc(data.error) + '</span>';
  } else {
    output.innerHTML += '\n<span class="error">Network error</span>';
  }
  output.scrollTop = output.scrollHeight;
  input.value = '';
}

function modalQuickCmd(cmd) {
  document.getElementById('pmTermInput').value = cmd;
  runModalCmd();
}

function clearModalTerminal() {
  document.getElementById('pmTermOutput').innerHTML = '<span class="info">Terminal cleared.</span>';
}

// ═══════════════════════ FILE BROWSER ═══════════════════════

let currentBrowsePath = '/sdcard';
let fileSelectedPaths = new Set();

async function fileBrowseTo(path) {
  const phone = activeModalPhone;
  if (!phone) return;
  currentBrowsePath = path;
  fileSelectedPaths.clear();
  updateFileSelectionUI();

  const bc = document.getElementById('fileBreadcrumb');
  if (bc) bc.textContent = path;

  const fl = document.getElementById('fileList');
  if (fl) fl.innerHTML = '<div class="file-loading">Loading...</div>';

  const status = document.getElementById('fileStatus');

  const data = await apiGet('/api/phone/' + encodeURIComponent(phone.id) + '/files?path=' + encodeURIComponent(path));
  if (!data || data.error) {
    fl.innerHTML = '<div class="file-loading" style="color:var(--red)">' + esc(data ? data.error : 'Failed to load') + '</div>';
    return;
  }

  const files = data.files || [];
  if (files.length === 0) {
    fl.innerHTML = '<div class="file-loading">Empty directory</div>';
    if (status) status.textContent = '0 items';
    return;
  }

  fl.innerHTML = files.map(f => {
    const icon = f.is_dir ? '📁' : getFileIcon(f.name);
    const cls = f.is_dir ? 'is-dir' : (f.is_link ? 'is-link' : '');
    const fullPath = currentBrowsePath.replace(/\/$/, '') + '/' + f.name;
    const sizeText = f.is_dir ? '—' : formatFileSize(f.size);
    const pathAttr = fullPath.replace(/&/g,'&amp;').replace(/"/g,'&quot;');

    return '<div class="file-item ' + cls + '" data-path="' + pathAttr + '" data-isdir="' + f.is_dir + '">' +
      '<input type="checkbox" class="file-item-check" data-fpath="' + pathAttr + '" data-fisdir="' + f.is_dir + '">' +
      '<span class="file-item-icon">' + icon + '</span>' +
      '<span class="file-item-name">' + esc(f.name) + '</span>' +
      '<span class="file-item-size">' + sizeText + '</span>' +
      '<span class="file-item-date">' + esc(f.date) + '</span>' +
      (f.is_dir ? '' : '<button class="file-item-dl" data-dlpath="' + pathAttr + '">⬇</button>') +
    '</div>';
  }).join('');

  // Attach event listeners via delegation
  fl.addEventListener('click', function handler(e) {
    const item = e.target.closest('.file-item');
    if (!item) return;
    const path = item.dataset.path;
    const isDir = item.dataset.isdir === 'true';

    // Checkbox click
    if (e.target.classList.contains('file-item-check')) {
      e.stopPropagation();
      if (e.target.checked) { fileSelectedPaths.add(path); } else { fileSelectedPaths.delete(path); }
      updateFileSelectionUI();
      return;
    }

    // Download button click
    if (e.target.classList.contains('file-item-dl')) {
      e.stopPropagation();
      fileDownloadSingle(e.target.dataset.dlpath);
      return;
    }

    // Name / row click
    if (isDir) {
      fileBrowseTo(path);
    } else {
      filePreviewClick(path);
    }
  });

  if (status) {
    const dirCount = files.filter(f => f.is_dir).length;
    const fileCount = files.filter(f => !f.is_dir).length;
    status.textContent = dirCount + ' folders, ' + fileCount + ' files';
  }
}

function fileBrowseUp() {
  if (currentBrowsePath === '/' || !currentBrowsePath) return;
  const parent = currentBrowsePath.replace(/\/[^/]+\/?$/, '') || '/';
  fileBrowseTo(parent);
}

function fileSelectAll() {
  const items = document.querySelectorAll('#fileList .file-item');
  const allChecked = fileSelectedPaths.size > 0;
  fileSelectedPaths.clear();
  items.forEach(item => {
    const cb = item.querySelector('.file-item-check');
    const path = item.dataset.path;
    if (allChecked) {
      cb.checked = false;
    } else {
      if (item.dataset.isdir !== 'true') {
        cb.checked = true;
        fileSelectedPaths.add(path);
      }
    }
  });
  updateFileSelectionUI();
}

function updateFileSelectionUI() {
  const btn = document.getElementById('fileDownloadSelectedBtn');
  if (!btn) return;
  if (fileSelectedPaths.size > 0) {
    btn.style.display = 'inline-block';
    btn.textContent = '⬇ Download ' + fileSelectedPaths.size + ' file(s)';
  } else {
    btn.style.display = 'none';
  }
}

function fileDownloadSingle(path) {
  const phone = activeModalPhone;
  if (!phone) return;
  const url = '/api/phone/' + encodeURIComponent(phone.id) + '/download?path=' + encodeURIComponent(path);
  window.open(url, '_blank');
}

async function fileDownloadSelected() {
  const phone = activeModalPhone;
  if (!phone || fileSelectedPaths.size === 0) return;

  if (fileSelectedPaths.size === 1) {
    fileDownloadSingle([...fileSelectedPaths][0]);
    return;
  }

  const status = document.getElementById('fileStatus');
  if (status) status.textContent = 'Creating archive...';

  const res = await fetch('/api/phone/' + encodeURIComponent(phone.id) + '/download-zip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths: [...fileSelectedPaths] }),
  });

  if (res.ok) {
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'phone_files.tar.gz';
    a.click();
    URL.revokeObjectURL(url);
    if (status) status.textContent = 'Download complete';
  } else {
    const err = await res.json().catch(() => ({ error: 'Download failed' }));
    if (status) status.textContent = 'Error: ' + (err.error || 'Failed');
  }
}

function filePreviewClick(path) {
  // For now just highlight the click — could add preview later
  const status = document.getElementById('fileStatus');
  if (status) status.textContent = 'Selected: ' + path;
}

function getFileIcon(name) {
  const ext = (name.split('.').pop() || '').toLowerCase();
  const icons = {
    jpg: '🖼', jpeg: '🖼', png: '🖼', gif: '🖼', webp: '🖼', bmp: '🖼', svg: '🖼',
    mp4: '🎬', mkv: '🎬', avi: '🎬', mov: '🎬', webm: '🎬', '3gp': '🎬',
    mp3: '🎵', wav: '🎵', flac: '🎵', ogg: '🎵', aac: '🎵', m4a: '🎵',
    pdf: '📄', doc: '📝', docx: '📝', txt: '📝', md: '📝', log: '📝',
    zip: '📦', gz: '📦', tar: '📦', rar: '📦', '7z': '📦',
    apk: '📱', json: '⚙', xml: '⚙', yml: '⚙', yaml: '⚙', sh: '⚙',
    py: '🐍', js: '💛', html: '🌐', css: '🎨', java: '☕',
    db: '🗃', sqlite: '🗃', csv: '📊', xls: '📊', xlsx: '📊',
  };
  return icons[ext] || '📄';
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// ═══════════════════════ PHONE SYSTEM INFO ═══════════════════════

async function loadPhoneSysInfo() {
  const phone = activeModalPhone;
  if (!phone) return;

  const el = document.getElementById('pmInfo');
  if (!el) return;
  el.innerHTML = '<div class="file-loading">Gathering system info...</div>';

  const data = await apiGet('/api/phone/' + encodeURIComponent(phone.id) + '/sysinfo');
  if (!data || data.error) {
    el.innerHTML = '<div style="color:var(--red);text-align:center;padding:1rem">' + esc(data ? data.error : 'Failed') + '</div>';
    return;
  }

  const s = phone.stats || {};
  const batNum = parseInt(s.BAT) || 0;
  const memNum = parseInt(s.MEM) || 0;
  const storNum = parseInt(s.STORAGE) || 0;
  const tunnelUp = (s.TUNNEL || '').toUpperCase() === 'ACTIVE';
  const barColor = (val, invert) => {
    if (invert) return val < 60 ? 'green' : val < 85 ? 'yellow' : 'red';
    return val > 50 ? 'green' : val > 20 ? 'yellow' : 'red';
  };

  let html = '<div class="phone-metrics">' +
    metricHTML('Battery', s.BAT, batNum, barColor(batNum, false)) +
    metricHTML('Memory', s.MEM, memNum, barColor(memNum, true)) +
    metricHTML('Storage', s.STORAGE, storNum, barColor(storNum, true)) +
    '<div class="metric"><span class="metric-label">Tunnel</span><span class="metric-value" style="color:' + (tunnelUp ? 'var(--green)' : 'var(--red)') + '">' + (tunnelUp ? 'ACTIVE' : esc(s.TUNNEL || 'N/A')) + '</span></div>' +
  '</div>';

  html += '<div style="margin-top:1rem"><div class="page-title" style="margin-bottom:0.5rem">// System Details</div></div>';
  html += '<div class="sysinfo-grid">';

  const fields = [
    ['USER', 'User'], ['KERNEL', 'Kernel'], ['ARCH', 'Architecture'],
    ['HOSTNAME', 'Hostname'], ['UPTIME', 'Uptime'], ['DATE', 'Date/Time'],
    ['STORAGE_TOTAL', 'Storage Total'], ['STORAGE_USED', 'Storage Used'],
    ['STORAGE_AVAIL', 'Storage Free'], ['STORAGE_PCT', 'Storage Used %'],
    ['MEM_TOTAL', 'RAM Total'], ['MEM_USED', 'RAM Used'], ['MEM_FREE', 'RAM Free'],
    ['PROCS', 'Processes'], ['TERMUX_VER', 'Termux Version'],
    ['PKG_COUNT', 'Installed Packages'], ['PHOTOS', 'Camera Photos'],
    ['PHOTOS_SIZE', 'Photos Size'], ['SHELL', 'Shell'],
  ];

  fields.forEach(([key, label]) => {
    const val = data[key] || 'N/A';
    html += '<div class="sysinfo-item"><span class="sysinfo-label">' + label + '</span><span class="sysinfo-value">' + esc(val) + '</span></div>';
  });

  html += '</div>';
  html += '<div class="ssh-box" style="margin-top:1rem"><code>ssh -p ' + phone.tunnel_port + ' ' + esc(phone.user) + '@' + window.location.hostname + '</code></div>';
  if (phone.last_seen) {
    html += '<div style="margin-top:0.5rem;font-size:0.7rem;color:var(--text-muted)">Last seen: ' + esc(phone.last_seen) + '</div>';
  }

  el.innerHTML = html;
}

// ── SAVE PHONE CONFIG ──
async function savePhoneConfig() {
  const phone = activeModalPhone;
  if (!phone) return;
  const pw = document.getElementById('pmPassword').value;
  const name = document.getElementById('pmPhoneName').value || phone.name;

  const data = await apiPost('/api/phone/' + encodeURIComponent(phone.id) + '/config', {
    ssh_password: pw,
    name: name
  });

  const msg = document.getElementById('pmConfigMsg');
  if (data && data.success) {
    msg.textContent = '[ SAVED ]';
    msg.style.color = 'var(--green)';
    // Update local data
    phone.ssh_password = pw;
    phone.name = name;
    phone.has_password = !!pw;
  } else {
    msg.textContent = '[ ERROR ] ' + (data ? data.error : 'Failed');
    msg.style.color = 'var(--red)';
  }
  msg.style.display = 'block';
  setTimeout(() => msg.style.display = 'none', 3000);
}

function togglePasswordVis(btn) {
  const input = btn.previousElementSibling;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🔒';
  } else {
    input.type = 'password';
    btn.textContent = '👁';
  }
}

// ═══════════════════════ TERMINAL PAGE ═══════════════════════

async function runCmd() {
  const sel = document.getElementById('cmdPhone');
  const input = document.getElementById('cmdInput');
  const output = document.getElementById('cmdOutput');
  if (!sel || !sel.value || !input.value.trim()) return;

  const { port, user } = JSON.parse(sel.value);
  const cmd = input.value.trim();

  output.innerHTML += '\n<span class="prompt">' + esc(user) + '@phone:' + port + '$</span> ' + esc(cmd) + '\n<span class="info">executing...</span>';
  output.scrollTop = output.scrollHeight;

  const data = await apiPost('/api/command', { port, user, command: cmd });
  const lines = output.innerHTML.split('\n');
  lines.pop();
  output.innerHTML = lines.join('\n');

  if (data) {
    if (data.output) output.innerHTML += '\n' + esc(data.output);
    if (data.error && data.code !== 0) output.innerHTML += '\n<span class="error">' + esc(data.error) + '</span>';
  } else {
    output.innerHTML += '\n<span class="error">Network error</span>';
  }
  output.scrollTop = output.scrollHeight;
  input.value = '';
}

function quickCmd(cmd) {
  const input = document.getElementById('cmdInput');
  if (input) { input.value = cmd; runCmd(); }
}

function quickCmdPhone(port, user, cmd) {
  if (!document.getElementById('cmdPhone')) {
    window.location.href = '/terminal?port=' + port + '&user=' + encodeURIComponent(user) + '&cmd=' + encodeURIComponent(cmd);
    return;
  }
  const sel = document.getElementById('cmdPhone');
  for (const opt of sel.options) {
    const v = JSON.parse(opt.value);
    if (v.port === port) { sel.value = opt.value; break; }
  }
  document.getElementById('cmdInput').value = cmd;
  runCmd();
}

function clearTerminal() {
  const output = document.getElementById('cmdOutput');
  if (output) output.innerHTML = '<span class="info">Terminal cleared. Ready.</span>';
}

// ═══════════════════════ INVITES ═══════════════════════

async function loadInvites() {
  const data = await apiGet('/api/invites');
  if (!data) return;
  const tbody = document.getElementById('invitesTableBody');
  if (!tbody) return;

  const list = data.invites || [];
  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No invites created yet</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(inv =>
    '<tr><td style="color:var(--cyan)">' + esc(inv.token.substring(0, 8)) + '...</td>' +
    '<td>' + inv.port + '</td>' +
    '<td><span class="badge ' + (inv.used ? 'badge-green' : 'badge-yellow') + '">' + (inv.used ? 'USED' : 'PENDING') + '</span></td>' +
    '<td>' + esc(inv.used_by || '\u2014') + '</td>' +
    '<td style="color:var(--text-muted)">' + esc(inv.created) + '</td></tr>'
  ).join('');
}

async function generateInvite() {
  const portEl = document.getElementById('invitePort');
  const port = parseInt(portEl.value) || 2223;
  const data = await apiPost('/api/invite', { port });
  if (!data || !data.success) return;

  document.getElementById('inviteResult').style.display = 'block';
  document.getElementById('inviteCmd').textContent = data.install_command;
  loadInvites();
}

function copyInviteCmd() {
  const cmd = document.getElementById('inviteCmd').textContent;
  navigator.clipboard.writeText(cmd).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = cmd;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  });
  const btn = document.querySelector('.copy-btn');
  if (btn) { btn.textContent = '[ COPIED ]'; setTimeout(() => btn.textContent = '[ COPY ]', 2000); }
}

// ═══════════════════════ SETTINGS ═══════════════════════

async function loadSettings() {
  const data = await apiGet('/api/settings');
  if (!data) return;
  const container = document.getElementById('settingsEnv');
  if (!container) return;

  const settings = data.settings || {};
  container.innerHTML = Object.entries(settings).map(([k, v]) =>
    '<div class="setting-row"><span class="setting-key">' + esc(k) + '</span><span class="setting-val">' + esc(v) + '</span></div>'
  ).join('');
}

async function loadSystemInfo() {
  const data = await apiGet('/api/system');
  if (!data) return;
  const el = (id) => document.getElementById(id);
  if (el('sysUptime')) el('sysUptime').textContent = data.uptime || 'N/A';
  if (el('sysHostname')) el('sysHostname').textContent = data.hostname || 'N/A';
  if (el('sysMem')) el('sysMem').textContent = (data.mem_used || '?') + ' / ' + (data.mem_total || '?');
  if (el('sysDisk')) el('sysDisk').textContent = (data.disk_used || '?') + ' / ' + (data.disk_total || '?') + ' (' + (data.disk_pct || '?') + ')';
}

async function loadPhoneCredentials() {
  const data = await apiGet('/api/phones');
  if (!data) return;
  const tbody = document.getElementById('phoneCredsBody');
  if (!tbody) return;

  const phones = data.phones || [];
  if (phones.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No phones registered</td></tr>';
    return;
  }

  tbody.innerHTML = phones.map(p =>
    '<tr>' +
      '<td style="color:var(--accent)">' + esc(p.name) + '</td>' +
      '<td>' + esc(p.user) + '</td>' +
      '<td style="color:var(--cyan)">' + (p.tunnel_port || '—') + '</td>' +
      '<td>' +
        '<div class="password-field">' +
          '<input type="password" id="pw_' + esc(p.id) + '" value="' + esc(p.ssh_password || '') + '" placeholder="not set">' +
          '<button class="password-toggle" onclick="togglePasswordVis(this)">👁</button>' +
        '</div>' +
      '</td>' +
      '<td>' +
        '<button class="btn btn-sm" onclick="savePhonePw(\'' + esc(p.id) + '\')">Save</button>' +
      '</td>' +
    '</tr>'
  ).join('');
}

async function savePhonePw(phoneId) {
  const input = document.getElementById('pw_' + phoneId);
  if (!input) return;
  const data = await apiPost('/api/phone/' + encodeURIComponent(phoneId) + '/config', { ssh_password: input.value });
  if (data && data.success) {
    input.style.borderColor = 'var(--green)';
    setTimeout(() => input.style.borderColor = '', 2000);
  }
}

async function changePassword(e) {
  e.preventDefault();
  const current = document.getElementById('currentPass').value;
  const newPass = document.getElementById('newPass').value;
  const confirm = document.getElementById('confirmPass').value;
  const msg = document.getElementById('passMsg');

  if (newPass !== confirm) {
    msg.textContent = '[ ERROR ] Passwords do not match';
    msg.style.color = 'var(--red)';
    msg.style.display = 'block';
    return;
  }

  const data = await apiPost('/api/settings/password', { current, new_password: newPass });
  if (data && data.success) {
    msg.textContent = '[ OK ] Password updated successfully';
    msg.style.color = 'var(--green)';
    document.getElementById('currentPass').value = '';
    document.getElementById('newPass').value = '';
    document.getElementById('confirmPass').value = '';
  } else {
    msg.textContent = '[ ERROR ] ' + (data ? data.error : 'Failed');
    msg.style.color = 'var(--red)';
  }
  msg.style.display = 'block';
}

// ═══════════════════════ LOGS ═══════════════════════

async function loadCommandHistory() {
  const data = await apiGet('/api/command-history');
  if (!data) return;
  const container = document.getElementById('logsContainer');
  if (!container) return;

  const logs = data.logs || [];
  if (logs.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div><div>No command history yet</div></div>';
    return;
  }

  container.innerHTML = logs.map(log =>
    '<div class="log-entry">' +
      '<div style="display:flex;justify-content:space-between;align-items:center">' +
        '<span class="log-phone">' + esc(log.phone_id) + '</span>' +
        '<span class="log-time">' + esc(log.time) + '</span>' +
      '</div>' +
      '<div class="log-cmd">$ ' + esc(log.command) + '</div>' +
      '<div style="color:var(--text-dim);font-size:0.75rem;margin-top:2px">' +
        esc((log.output || '').substring(0, 200)) +
        ' <span class="' + (log.exit_code === 0 ? 'log-exit-ok' : 'log-exit-fail') + '">[exit ' + log.exit_code + ']</span>' +
      '</div>' +
    '</div>'
  ).join('');
}

// ═══════════════════════ UTILS ═══════════════════════

function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

// ═══════════════════════ INIT ═══════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initNav();
  updateClock();
  setInterval(updateClock, 1000);

  const page = window.location.pathname;

  // Login
  const loginForm = document.getElementById('loginForm');
  if (loginForm) loginForm.addEventListener('submit', doLogin);

  // Close modal on Escape only (NOT on overlay click)
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePhoneModal(); });

  // Dashboard
  if (page === '/dashboard') {
    refreshDashboard();
    autoRefresh = setInterval(refreshDashboard, 30000);
  }

  // Terminal
  if (page === '/terminal') {
    refreshDashboard().then(() => {
      const params = new URLSearchParams(window.location.search);
      const port = params.get('port');
      const user = params.get('user');
      const cmd = params.get('cmd');
      if (port && user) {
        const sel = document.getElementById('cmdPhone');
        if (sel) {
          for (const opt of sel.options) {
            const v = JSON.parse(opt.value);
            if (v.port === parseInt(port)) { sel.value = opt.value; break; }
          }
        }
        if (cmd) {
          document.getElementById('cmdInput').value = cmd;
          runCmd();
        }
      }
    });

    const cmdInput = document.getElementById('cmdInput');
    if (cmdInput) cmdInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') runCmd(); });
  }

  // Modal terminal Enter key
  const pmInput = document.getElementById('pmTermInput');
  if (pmInput) pmInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') runModalCmd(); });

  // Invites
  if (page === '/invites') loadInvites();

  // Settings
  if (page === '/settings') {
    loadSettings();
    loadSystemInfo();
    loadPhoneCredentials();
    const passForm = document.getElementById('passForm');
    if (passForm) passForm.addEventListener('submit', changePassword);
  }

  // Logs
  if (page === '/logs') loadCommandHistory();
});
