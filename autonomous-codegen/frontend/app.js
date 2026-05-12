// ─── Config ──────────────────────────────────────────────────────────────────
const BACKEND_WS   = `ws://${window.location.host}/ws`;
const BACKEND_HTTP = `http://${window.location.host}/api`;

// ─── State ───────────────────────────────────────────────────────────────────
let ws          = null;
let sessionId   = null;
let isRunning   = false;
let currentTab  = 'log';
let codeFiles   = {};        // filename → content
let outputCount = 0;
let logCount    = 0;
let fileCount   = 0;
let autoScroll  = true;

// ─── Helpers ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function genId() {
    return Math.random().toString(36).slice(2, 11);
}

function escHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function langFromFilename(name) {
    const ext = (name.split('.').pop() || '').toLowerCase();
    return { py:'python', js:'javascript', ts:'typescript',
             html:'html', css:'css', json:'json', sh:'bash',
             md:'markdown', yml:'yaml', yaml:'yaml', sql:'sql',
             txt:'plaintext', toml:'ini' }[ext] || 'plaintext';
}

function fmtJson(obj) {
    try { return JSON.stringify(obj, null, 2); }
    catch { return String(obj); }
}

function nowStr() {
    return new Date().toLocaleTimeString();
}

// ─── Tab management ───────────────────────────────────────────────────────────
function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach((t, i) => {
        t.classList.toggle('active', ['log','code','output'][i] === tab);
    });
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    $(`${tab}Tab`).classList.add('active');

    // Clear badge for active tab
    const badge = $(`${tab}Badge`);
    if (badge) { badge.classList.add('hidden'); badge.textContent = '0'; }
}

function bumpBadge(tab) {
    if (currentTab === tab) return;
    const badge = $(`${tab}Badge`);
    if (!badge) return;
    badge.classList.remove('hidden');
    badge.textContent = String(Number(badge.textContent) + 1);
}

// ─── Quick prompts ────────────────────────────────────────────────────────────
function setPrompt(text) {
    $('taskInput').value = text;
    $('taskInput').focus();
}

// ─── Status helpers ───────────────────────────────────────────────────────────
function setStatus(s) {
    const d = $('statusIndicator');
    d.className = `status-dot ${s}`;
    d.title = s[0].toUpperCase() + s.slice(1);
}

function setRunning(r) {
    isRunning = r;
    $('startBtn').disabled = r;
    $('stopBtn').disabled  = !r;
    $('taskInput').disabled = r;
    $('modelSelect').disabled = r;
}

// ─── Agent Log ────────────────────────────────────────────────────────────────
function addLog(type, title, body = '', collapsible = true) {
    const log = $('agentLog');
    const welcome = log.querySelector('.welcome-msg');
    if (welcome) welcome.remove();

    logCount++;

    const entry = document.createElement('div');
    entry.className = `log-entry entry-${type}`;

    // Header
    const hdr = document.createElement('div');
    hdr.className = 'log-header';

    const titleSpan = document.createElement('span');
    titleSpan.textContent = title;
    hdr.appendChild(titleSpan);

    let bodyEl = null;
    if (body) {
        const toggle = document.createElement('span');
        toggle.className = 'log-toggle open';
        toggle.textContent = '▲';
        hdr.appendChild(toggle);

        bodyEl = document.createElement('div');
        bodyEl.className = 'log-body';

        // Render body content
        if (type === 'thought') {
            bodyEl.textContent = body;
        } else if (type === 'complete') {
            bodyEl.innerHTML = body;
        } else {
            // Check if it looks like code/JSON (multi-line or starts with { [ )
            const trimmed = body.trim();
            const isCode = trimmed.includes('\n') || trimmed.startsWith('{') ||
                           trimmed.startsWith('[') || trimmed.length > 120;
            if (isCode) {
                const pre = document.createElement('pre');
                pre.textContent = body;
                bodyEl.appendChild(pre);
            } else {
                bodyEl.textContent = body;
            }
        }

        if (collapsible) {
            hdr.style.cursor = 'pointer';
            hdr.onclick = () => {
                const hidden = bodyEl.style.display === 'none';
                bodyEl.style.display = hidden ? '' : 'none';
                toggle.textContent = hidden ? '▲' : '▼';
                toggle.classList.toggle('open', hidden);
            };
        }

        entry.appendChild(hdr);
        entry.appendChild(bodyEl);
    } else {
        entry.appendChild(hdr);
    }

    log.appendChild(entry);

    // Auto-scroll
    if (autoScroll) {
        log.scrollTop = log.scrollHeight;
    }

    bumpBadge('log');
    return entry;
}

// ─── Code Viewer ─────────────────────────────────────────────────────────────
function upsertCodeFile(filename, content) {
    const isNew = !codeFiles[filename];
    codeFiles[filename] = content;

    const viewer = $('codeViewer');
    const placeholder = viewer.querySelector('.placeholder-text');
    if (placeholder) placeholder.remove();

    const safeAttr = CSS.escape(filename);
    let fileEl = viewer.querySelector(`[data-file="${safeAttr}"]`);

    if (!fileEl) {
        fileEl = document.createElement('div');
        fileEl.className = 'code-file';
        fileEl.dataset.file = filename;

        const header = document.createElement('div');
        header.className = 'code-file-header';

        const nameSpan = document.createElement('span');
        nameSpan.textContent = `📄 ${filename}`;

        const right = document.createElement('div');
        right.style.display = 'flex';
        right.style.alignItems = 'center';
        right.style.gap = '8px';

        const lineCount = document.createElement('span');
        lineCount.className = 'line-count';
        lineCount.style.color = 'var(--text-muted)';
        lineCount.style.fontSize = '0.72rem';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = '📋 Copy';
        copyBtn.onclick = () => copyCode(filename, copyBtn);

        right.appendChild(lineCount);
        right.appendChild(copyBtn);
        header.appendChild(nameSpan);
        header.appendChild(right);

        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.className = `language-${langFromFilename(filename)}`;
        pre.appendChild(code);

        fileEl.appendChild(header);
        fileEl.appendChild(pre);
        viewer.appendChild(fileEl);
    }

    // Update content
    const code = fileEl.querySelector('code');
    const lineCount = fileEl.querySelector('.line-count');
    const lines = content.split('\n');

    code.textContent = content;
    lineCount.textContent = `${lines.length} lines`;

    try { hljs.highlightElement(code); } catch {}

    if (isNew) {
        bumpBadge('code');
        fileCount++;
        $('codeBadge').textContent = String(fileCount);
    }
}

function copyCode(filename, btn) {
    const content = codeFiles[filename] || '';
    navigator.clipboard.writeText(content).then(() => {
        btn.textContent = '✅ Copied!';
        setTimeout(() => { btn.textContent = '📋 Copy'; }, 1500);
    });
}

// ─── Output Viewer ────────────────────────────────────────────────────────────
function addOutput(tool, content, language, success) {
    const viewer = $('outputViewer');
    const placeholder = viewer.querySelector('.placeholder-text');
    if (placeholder) placeholder.remove();

    outputCount++;

    const entry = document.createElement('div');
    entry.className = `output-entry ${success ? 'success' : 'failure'}`;

    const hdr = document.createElement('div');
    hdr.className = 'output-entry-header';
    hdr.innerHTML = `
        <span>${success ? '✅' : '❌'} ${escHtml(tool)} ${language ? `(${escHtml(language)})` : ''}</span>
        <span>${nowStr()}</span>
    `;

    const pre = document.createElement('pre');
    pre.textContent = content || '(no output)';

    entry.appendChild(hdr);
    entry.appendChild(pre);
    viewer.appendChild(entry);
    viewer.scrollTop = viewer.scrollHeight;

    bumpBadge('output');
    $('outputBadge').textContent = String(outputCount);
}

// ─── Files Panel ─────────────────────────────────────────────────────────────
function updateFilesList(files) {
    const section = $('filesSection');
    const list    = $('filesList');
    section.classList.remove('hidden');

    // Add new files only
    files.forEach(f => {
        const exists = list.querySelector(`[data-fname="${CSS.escape(f)}"]`);
        if (exists) return;

        const item = document.createElement('div');
        item.className = 'file-item';
        item.dataset.fname = f;
        item.innerHTML = `<span>📄</span><span title="${escHtml(f)}">${escHtml(f)}</span>`;
        item.onclick = () => {
            switchTab('code');
            setTimeout(() => {
                const el = $('codeViewer').querySelector(`[data-file="${CSS.escape(f)}"]`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 50);
        };
        list.appendChild(item);
    });
}

async function downloadAll() {
    // Download each file individually as text
    for (const [filename, content] of Object.entries(codeFiles)) {
        const blob = new Blob([content], { type: 'text/plain' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename.replace(/\//g, '_');
        a.click();
        URL.revokeObjectURL(a.href);
        await new Promise(r => setTimeout(r, 150));
    }
}

// ─── Progress ────────────────────────────────────────────────────────────────
function updateProgress(current, max) {
    $('progressSection').classList.remove('hidden');
    const pct = Math.round((current / max) * 100);
    $('progressLabel').textContent   = `Iteration ${current}/${max}`;
    $('progressPercent').textContent = `${pct}%`;
    $('progressFill').style.width    = `${pct}%`;
}

// ─── Fetch file from backend and display it ───────────────────────────────────
async function fetchAndShowFile(filename) {
    try {
        const resp = await fetch(`${BACKEND_HTTP}/files/${sessionId}/${encodeURIComponent(filename)}`);
        if (resp.ok) {
            const text = await resp.text();
            if (text && text.trim()) {
                upsertCodeFile(filename, text);
                return true;
            }
        }
    } catch (e) {
        console.warn('Could not fetch file:', filename, e);
    }
    return false;
}

// ─── Message Handler ──────────────────────────────────────────────────────────
function handleMessage(msg) {
    switch (msg.type) {

        case 'task_started':
            addLog('info', `🚀 Task Started`, msg.task, false);
            break;

        case 'agent_start':
            addLog('info', `🤖 ${msg.message}`, '', false);
            break;

        case 'iteration_start':
            updateProgress(msg.iteration, msg.max_iterations);
            addLog('iteration', `🔄 Iteration ${msg.iteration} / ${msg.max_iterations}`, '', false);
            break;

        case 'thinking':
            addLog('thinking', '💭 Querying LLM...', '', false);
            break;

        case 'thought':
            addLog('thought', '💡 Agent Thought', msg.content);
            break;

        case 'llm_response': {
            // Show truncated LLM raw response (collapsed by default)
            const content = msg.content || '';
            const preview = content.length > 800
                ? content.slice(0, 800) + `\n... [${content.length - 800} more chars]`
                : content;
            addLog('llm', '🧠 LLM Response', preview, true);
            break;
        }

        case 'tool_call':
            addLog('tool-call',
                `🔧 Calling: ${msg.tool}`,
                fmtJson(msg.params), true);
            break;

        case 'tool_result':
            handleToolResult(msg);
            break;

        case 'warning':
            addLog('warning', `⚠️ ${msg.message}`, '', false);
            break;

        case 'error':
            addLog('error', `❌ Error: ${msg.message}`, '', false);
            setStatus('error');
            setRunning(false);
            break;

        case 'complete':
        case 'task_complete':
            handleComplete(msg.result);
            break;

        case 'stopped':
            addLog('warning', `⏹ Stopped: ${msg.message}`, '', false);
            setStatus('idle');
            setRunning(false);
            break;

        case 'pong':
            break;

        default:
            console.log('Unhandled message:', msg);
    }
}

// ─── Tool Result Handler ──────────────────────────────────────────────────────
async function handleToolResult(msg) {
    const { tool, result } = msg;

    if (!result) {
        addLog('error', `❌ ${tool}: no result`, '', false);
        return;
    }

    switch (tool) {

        case 'write_file': {
            if (result.success) {
                addLog('tool-result', `✅ File Written: ${result.message || ''}`, '', false);
                // The agent just wrote a file — fetch it immediately to show in Code tab
                const filename = msg.params?.filename || result.message?.replace('Written: ', '');
                if (filename) {
                    await fetchAndShowFile(filename);
                    updateFilesList([filename]);
                }
            } else {
                addLog('error', `❌ Write Failed`, result.error || '', false);
            }
            break;
        }

        case 'read_file': {
            if (result.success) {
                addLog('tool-result', `📄 Read: ${result.filename}`,
                    (result.content || '').slice(0, 200), true);
                if (result.filename && result.content) {
                    upsertCodeFile(result.filename, result.content);
                }
            } else {
                addLog('error', `❌ Read Failed`, result.error || '', false);
            }
            break;
        }

        case 'execute_code':
        case 'execute_file': {
            const lang = result.language || '';
            if (result.success) {
                const out = result.output || '(no output)';
                addLog('tool-result', `✅ Executed ${lang}`,
                    out.slice(0, 300) + (out.length > 300 ? '\n...' : ''), true);
                addOutput(tool, out, lang, true);
            } else {
                const err = result.error || 'Unknown error';
                addLog('error', `❌ Execution Error`,
                    err.slice(0, 400), true);
                addOutput(tool, err, lang, false);
            }
            break;
        }

        case 'install_package': {
            if (result.success) {
                addLog('tool-result', `📦 Installed: ${result.message}`, '', false);
            } else {
                addLog('error', `❌ Install Failed`, result.error || '', false);
            }
            break;
        }

        case 'web_search': {
            if (result.success) {
                const lines = (result.results || []).map((r, i) =>
                    `${i+1}. ${r.title}\n   ${r.url}\n   ${r.snippet}`
                ).join('\n\n');
                addLog('tool-result', `🔍 Search: "${result.query}" (${result.results.length} results)`,
                    lines, true);
            } else {
                addLog('error', `❌ Search Failed`, result.error || '', false);
            }
            break;
        }

        case 'web_fetch': {
            if (result.success) {
                const snippet = (result.content || '').slice(0, 400);
                addLog('tool-result', `🌐 Fetched: ${result.url}`, snippet, true);
            } else {
                addLog('error', `❌ Fetch Failed: ${result.url}`, result.error || '', false);
            }
            break;
        }

        case 'list_files': {
            if (result.success) {
                const lines = (result.files || []).map(f => `${f.name}  (${f.size}B)`).join('\n');
                addLog('tool-result', `📁 Workspace Files (${(result.files||[]).length})`, lines, true);
            }
            break;
        }

        case 'think': {
            // Already handled via 'thought' event; skip duplicate
            break;
        }

        default: {
            const body = result.success
                ? fmtJson(result).slice(0, 300)
                : (result.error || fmtJson(result)).slice(0, 300);
            addLog(result.success ? 'tool-result' : 'error',
                `${result.success ? '✅' : '❌'} ${tool}`, body, true);
        }
    }
}

// ─── Task Complete ────────────────────────────────────────────────────────────
async function handleComplete(result) {
    if (!result) return;

    const files    = result.files_created || [];
    const summary  = result.summary || 'Done';
    const output   = result.output  || '';
    const iters    = result.iterations || '?';

    // Build complete log entry
    let html = `<strong style="color:var(--accent)">${escHtml(summary)}</strong>`;
    if (files.length) {
        html += `<br><br><strong>📁 Files:</strong> `;
        html += files.map(f => `<code style="background:var(--bg2);padding:2px 5px;border-radius:3px">${escHtml(f)}</code>`).join(' ');
    }
    if (output) {
        html += `<br><br><strong>📤 Output:</strong><br><code>${escHtml(output.slice(0,300))}</code>`;
    }
    html += `<br><br><em style="color:var(--text-muted)">✨ Completed in ${iters} iterations</em>`;

    addLog('complete', '🎉 Task Complete!', html, false);

    // Fetch all files and display them
    if (files.length) {
        updateFilesList(files);
        for (const f of files) {
            await fetchAndShowFile(f);
        }
        // Switch to code tab automatically
        setTimeout(() => switchTab('code'), 300);
    }

    setStatus('complete');
    setRunning(false);
}

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connectWS(onOpen) {
    sessionId = genId();
    ws = new WebSocket(`${BACKEND_WS}/${sessionId}`);

    ws.onopen = () => {
        console.log('WS open, session:', sessionId);
        setStatus('running');
        if (onOpen) onOpen();
    };

    ws.onmessage = e => {
        let msg;
        try { msg = JSON.parse(e.data); }
        catch { console.error('Bad JSON:', e.data); return; }
        handleMessage(msg);
    };

    ws.onerror = err => {
        console.error('WS error:', err);
        addLog('error', '❌ Connection error — is the backend running?', '', false);
        setStatus('error');
        setRunning(false);
    };

    ws.onclose = () => {
        console.log('WS closed');
        if (isRunning) {
            setStatus('idle');
            setRunning(false);
        }
    };
}

// ─── Actions ──────────────────────────────────────────────────────────────────
function startTask() {
    const task = $('taskInput').value.trim();
    if (!task) { alert('Please enter a task first.'); return; }

    const model        = $('modelSelect').value;
    const maxIter      = parseInt($('maxIterations').value) || 15;

    // Reset state
    codeFiles    = {};
    outputCount  = 0;
    logCount     = 0;
    fileCount    = 0;
    autoScroll   = true;

    $('agentLog').innerHTML      = '';
    $('codeViewer').innerHTML    = '<p class="placeholder-text">Code files will appear here as the agent writes them...</p>';
    $('outputViewer').innerHTML  = '<p class="placeholder-text">Execution output will appear here...</p>';
    $('filesList').innerHTML     = '';
    $('filesSection').classList.add('hidden');
    $('progressSection').classList.add('hidden');
    ['log','code','output'].forEach(t => {
        const b = $(`${t}Badge`);
        b.classList.add('hidden');
        b.textContent = '0';
    });
    switchTab('log');

    setRunning(true);
    setStatus('running');

    connectWS(() => {
        ws.send(JSON.stringify({
            type: 'start_task',
            task,
            model,
            max_iterations: maxIter
        }));
    });
}

function stopTask() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'stop' }));
    }
    setRunning(false);
    setStatus('idle');
}

function clearAll() {
    if (isRunning) stopTask();

    codeFiles   = {};
    outputCount = 0;
    logCount    = 0;
    fileCount   = 0;

    $('agentLog').innerHTML = `
        <div class="welcome-msg">
            <div class="welcome-icon">⚡</div>
            <h2>Autonomous Code Generator</h2>
            <p>Enter a task and click Start. The agent will:</p>
            <ul>
                <li>🔍 Search the web for info &amp; docs</li>
                <li>✍️ Write code files</li>
                <li>🔧 Execute &amp; test in sandbox</li>
                <li>🐛 Debug and fix errors automatically</li>
                <li>✅ Deliver complete working code</li>
            </ul>
        </div>`;
    $('codeViewer').innerHTML   = '<p class="placeholder-text">Code files will appear here as the agent writes them...</p>';
    $('outputViewer').innerHTML = '<p class="placeholder-text">Execution output will appear here...</p>';
    $('filesList').innerHTML    = '';
    $('filesSection').classList.add('hidden');
    $('progressSection').classList.add('hidden');
    $('taskInput').value        = '';
    ['log','code','output'].forEach(t => {
        const b = $(`${t}Badge`);
        b.classList.add('hidden');
        b.textContent = '0';
    });

    setStatus('idle');
}

// ─── Load Models ──────────────────────────────────────────────────────────────
async function loadModels() {
    try {
        const resp = await fetch(`${BACKEND_HTTP}/models`);
        const data = await resp.json();
        const sel  = $('modelSelect');
        sel.innerHTML = '';
        (data.models || []).forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m.includes('deepseek-coder')) opt.selected = true;
            sel.appendChild(opt);
        });
    } catch (e) {
        console.warn('Could not load models:', e);
        // Fallback options
        $('modelSelect').innerHTML = `
            <option value="deepseek-coder:6.7b">deepseek-coder:6.7b</option>
            <option value="mistral:7b">mistral:7b</option>
            <option value="llama3:8b">llama3:8b</option>
            <option value="phi3:mini">phi3:mini</option>
            <option value="llama3.2:latest">llama3.2:latest</option>`;
    }
}

// Stop auto-scroll when user scrolls up
$('agentLog').addEventListener('scroll', () => {
    const log = $('agentLog');
    autoScroll = log.scrollTop + log.clientHeight >= log.scrollHeight - 50;
});

// Keep WS alive
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
    }
}, 25000);

// Init
loadModels();
