import { App, PostMessageTransport } from '@modelcontextprotocol/ext-apps';

const brandSource = 'RDC_LOGO_DATA';
document.querySelectorAll('[data-rdc-logo]').forEach(image => { image.src = brandSource; });

// The host mediates every request. This view never contacts a worker URL,
// receives owner credentials, or changes worker/session/job lifetime.
const app = new App({name: 'RDC Preview', version: '0.1.0a5'}, {
  availableDisplayModes: ['inline', 'fullscreen', 'pip'],
});
const el = id => document.getElementById(id);
const state = {
  connected: false, bridgeReady: false, disposed: false, hidden: false, busy: false, timer: null,
  sessionId: null, deviceId: null, sessions: [], paused: false, activeJobs: 0, pendingApprovals: 0,
  mode: 'inline', modes: ['inline'], generation: 0, failures: 0,
  frame: null, haveOpenResult: false, panel: null, dragging: null, selectionLost: false,
  pendingOpen: null, pendingFrames: new Map(), blockedFrames: new Map(), recoveryTimer: null, recoveryWake: null,
};
const POLL_MS = 1500;
const MAX_IMAGE_BASE64 = 12 * 1024 * 1024;
const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
const text = (id, value) => { el(id).textContent = String(value ?? ''); };
function notice(value = '') { text('notice', value); el('notice').hidden = !value; }
function status(value, style = '') { text('connection-text', value); el('connection').className = `status ${style}`; }
function stopPolling() { clearTimeout(state.timer); state.timer = null; }
function visibleConnected() { return state.connected && state.bridgeReady && !state.disposed && !state.hidden && !document.hidden; }
function canView() { return visibleConnected() && !state.selectionLost && state.sessionId; }
function selectedSetupProblem() {
  const selected = state.sessions.find(item => item.session_id === state.sessionId);
  return selected?.setup_status ? `mobile_${selected.setup_status}` : null;
}
function canPoll() { return canView() && !selectedSetupProblem() && !state.pendingFrames.get(state.sessionId)?.halted && !state.blockedFrames.has(state.sessionId); }
function interruptRecovery() {
  clearTimeout(state.recoveryTimer); state.recoveryTimer = null;
  const wake = state.recoveryWake; state.recoveryWake = null; wake?.();
}
function recoveryDelay() {
  return new Promise(resolve => {
    state.recoveryWake = resolve;
    state.recoveryTimer = setTimeout(() => { state.recoveryTimer = null; state.recoveryWake = null; resolve(); }, 500);
  });
}
function schedule(delay = POLL_MS) {
  stopPolling();
  if (visibleConnected() && state.pendingOpen && !state.pendingOpen.halted) state.timer = setTimeout(() => refreshSessions(false), delay);
  else if (canPoll()) state.timer = setTimeout(() => refreshFrame(false), delay);
}
function dataOf(result) {
  if (result?.structuredContent && typeof result.structuredContent === 'object') return result.structuredContent;
  const block = result?.content?.find(item => item.type === 'text');
  if (block?.text) { try { return JSON.parse(block.text); } catch {} }
  return {};
}
function checkResult(result) {
  const data = dataOf(result);
  if (result?.isError || data.ok === false) {
    const error = new Error(data.error?.message || 'The worker could not provide this preview.');
    error.code = data.error?.code;
    throw error;
  }
  return data;
}
function setBusy(value) {
  state.busy = value;
  el('refresh').disabled = value || !canView();
  el('sessions-refresh').disabled = value || !state.connected || !state.bridgeReady || state.disposed;
}
function address(url) {
  try {
    const value = new URL(url);
    if (value.protocol === 'data:') return 'Local browser document';
    if (value.protocol === 'about:') return value.href;
    return `${value.hostname}${value.pathname}`.slice(0, 200);
  } catch { return 'Independent browser'; }
}
function mobileSession(session) { return session?.kind === 'mobile' || session?.session_id?.startsWith('mobile-') === true; }
function sessionName(session) {
  return mobileSession(session) ? `${session.platform || 'Mobile'} · ${session.profile || session.title || 'Configured device'}` : session?.browser || session?.backend || 'Browser';
}
function workState() {
  const taskCount = typeof state.activeJobs === 'number' ? state.activeJobs : 0;
  const reviewCount = typeof state.pendingApprovals === 'number' ? state.pendingApprovals : 0;
  const counts = [];
  if (taskCount > 0) counts.push(`${taskCount} active ${taskCount === 1 ? 'job' : 'jobs'}`);
  if (reviewCount > 0) counts.push(`${reviewCount} ${reviewCount === 1 ? 'action' : 'actions'} awaiting review`);
  // These counters come from open/session refresh, not each live frame.
  const snapshot = counts.length ? `Last status check: ${counts.join('; ')}. ` : '';
  const review = reviewCount > 0 ? "Review requests in RDC's owner panel on the paired computer. " : '';
  const activity = state.paused ? 'Agent input is paused by the owner.' : 'Hiding this view keeps the worker running.';
  const selected = state.sessions.find(item => item.session_id === state.sessionId);
  const input = mobileSession(selected) ? ` ${selected.input_notice || 'Input is shared with anyone using the configured device or emulator.'}` : '';
  text('work-state', `${snapshot}${review}${activity}${input}`);
}
async function retainSelection() {
  // Optional host context, not a chat message and not worker configuration.
  // A new view can be opened with this exact session ID after host dismissal.
  if (!state.connected || state.disposed || !app.getHostCapabilities()?.updateModelContext) return;
  try {
    await app.updateModelContext({structuredContent: {rdc_preview: {
      device_id: state.deviceId, session_id: state.sessionId,
      view_hidden: state.hidden, reopen_tool: 'rdc_preview_open',
      pending_operation_id: state.pendingOpen?.operation_id || state.pendingFrames.get(state.sessionId)?.operation_id || null,
      worker_continues: true,
    }}}, {timeout: 1500});
  } catch { /* Host context is optional; the visible session ID remains usable. */ }
}
function updateSessionLabel() {
  const selected = state.sessions.find(item => item.session_id === state.sessionId);
  const label = mobileSession(selected) ? sessionName(selected) : address(selected?.url);
  text('page-address', label);
  el('page-address').title = label;
}
function selectSession(id) {
  if (id === state.sessionId) return;
  state.generation += 1;
  interruptRecovery();
  state.sessionId = id || null;
  state.frame = null;
  state.failures = 0;
  el('frame').hidden = true;
  el('frame').removeAttribute('src');
  el('cursor').hidden = true;
  el('empty').hidden = false;
  text('empty-title', id ? 'Connecting to the live view' : 'No session is open');
  text('empty-copy', id ? 'The agent continues working while this view connects.' : 'Ask the agent to start a browser or configured mobile session, then refresh Sessions.');
  text('frame-age', 'Waiting for the first frame');
  updateSessionLabel(); workState();
  const blocked = selectedSetupProblem() || state.blockedFrames.get(state.sessionId);
  if (blocked) captureProblem(blocked);
  schedule(0);
}
function pendingFrom(result) {
  const data = dataOf(result);
  if (data.pending !== true) return null;
  if (data.recovery_tool !== 'rdc_operation_status' || typeof data.operation_id !== 'string' || !/^[A-Za-z0-9_.-]{1,128}$/.test(data.operation_id)) {
    throw new Error('The gateway returned an invalid preview recovery reference.');
  }
  return {operation_id: data.operation_id, deadline: performance.now() + 120000, halted: false};
}
function pendingFor(kind, sessionId) { return kind === 'open' ? state.pendingOpen : state.pendingFrames.get(sessionId); }
function savePending(kind, sessionId, value) {
  if (kind === 'open') state.pendingOpen = value;
  else if (value) state.pendingFrames.set(sessionId, value);
  else state.pendingFrames.delete(sessionId);
}
async function resolvePreview(kind, result, sessionId, generation) {
  let pending = pendingFor(kind, sessionId);
  if (result) {
    const supplied = pendingFrom(result);
    if (!supplied) return result;
    if (pending && pending.operation_id !== supplied.operation_id) throw new Error('A preview recovery response changed the operation identity.');
    pending ||= {...supplied, sessionId};
    savePending(kind, sessionId, pending);
  }
  while (pending) {
    if (!visibleConnected() || generation !== state.generation) return null;
    if (pending.halted || performance.now() >= pending.deadline) {
      pending.halted = true;
      throw new Error(kind === 'frame' ? 'The preview recovery wait ended. Use Refresh to request a new observation.' : 'The session recovery wait ended. Use Sessions to request a fresh session list.');
    }
    status('Waiting for worker');
    text('frame-age', 'Recovering the existing preview operation');
    await recoveryDelay();
    if (!visibleConnected() || generation !== state.generation) return null;
    const recovered = await app.callServerTool({name: 'rdc_operation_status', arguments: {operation_id: pending.operation_id}}, {timeout: 15000});
    const continued = pendingFrom(recovered);
    if (continued) {
      if (continued.operation_id !== pending.operation_id) throw new Error('A preview recovery response changed the operation identity.');
      continue;
    }
    try { checkResult(recovered); }
    catch (error) {
      // A completed lookup of an ended session is useful to the open caller:
      // it can clear that selection and fetch the available sessions once.
      if (kind === 'open' && error.code === 'session_not_found') {
        savePending(kind, sessionId, null);
        return recovered;
      }
      pending.halted = true;
      error.message += ` ${kind === 'frame' ? 'Use Refresh to request a new observation.' : 'Use Sessions to request a fresh session list.'}`;
      throw error;
    }
    savePending(kind, sessionId, null);
    return recovered;
  }
  return result;
}
function acceptOpen(data, preserveSelection = false) {
  if (!data || !Array.isArray(data.sessions)) return;
  state.haveOpenResult = true;
  state.deviceId = typeof data.device_id === 'string' ? data.device_id : state.deviceId;
  state.sessions = data.sessions.filter(item => item && typeof item.session_id === 'string');
  for (const id of state.blockedFrames.keys()) if (!state.sessions.some(item => item.session_id === id)) state.blockedFrames.delete(id);
  state.paused = data.paused === true;
  state.activeJobs = data.active_jobs;
  state.pendingApprovals = data.pending_approvals;
  let desired;
  if (preserveSelection && (state.sessionId || state.selectionLost)) {
    if (state.sessions.some(item => item.session_id === state.sessionId)) desired = state.sessionId;
    else { desired = null; state.selectionLost = true; }
  } else {
    desired = typeof data.session_id === 'string' ? data.session_id : state.sessions[0]?.session_id || null;
    state.selectionLost = false;
  }
  const selector = el('session');
  selector.replaceChildren();
  for (const item of state.sessions) {
    const option = document.createElement('option');
    option.value = item.session_id;
    option.textContent = `${sessionName(item)} · ${item.session_id.slice(mobileSession(item) ? 7 : 0, mobileSession(item) ? 15 : 8)}`;
    selector.append(option);
  }
  if (!state.sessions.length || !desired) {
    const option = document.createElement('option');
    option.value = ''; option.textContent = state.selectionLost ? 'Choose another session' : 'No session is open'; selector.prepend(option);
  }
  selector.disabled = !state.sessions.length;
  const changed = desired !== state.sessionId;
  selectSession(desired);
  selector.value = state.sessionId || '';
  if (!changed && !desired) {
    text('empty-title', 'No session is open');
    text('empty-copy', 'Ask the agent to start a browser or configured mobile session, then refresh Sessions.');
  }
  if (state.selectionLost) {
    text('empty-title', 'The selected session is no longer active');
    text('empty-copy', 'Choose an available session. RDC will not switch your preview automatically.');
    notice('The selected session ended. Choose another session to resume the preview.');
  }
  updateSessionLabel(); workState();
  if (state.bridgeReady || !state.connected) status(state.sessionId ? 'Connected' : 'Ready', state.sessionId ? 'live' : '');
  const blocked = selectedSetupProblem() || state.blockedFrames.get(state.sessionId);
  if (blocked) captureProblem(blocked);
}
function captureProblem(code) {
  const labels = {
    screenshot_redaction_required: ['Privacy protected', 'Preview hidden for privacy', 'Use redacted observations or review the configured device in the owner panel.'],
    screenshot_failed: ['Preview unavailable', 'No verified image is available', 'The worker could not verify this capture. The selected session and its tasks are retained.'],
    mobile_session_gone: ['Session ended', 'The native session has ended', "Close this exact session record in RDC's owner panel before starting the profile again."],
    mobile_cleanup_required: ['Cleanup required', 'This session needs cleanup', "Close this exact session in RDC's owner panel before starting a replacement."],
    mobile_creation_unknown: ['Inspect device', 'Session creation is uncertain', "Use RDC's owner panel on the paired computer. Inspect Appium before restarting RDC; do not start a replacement."],
  };
  const label = labels[code];
  if (!label) return false;
  if (code.startsWith('mobile_')) state.blockedFrames.set(state.sessionId, code);
  state.frame = null;
  state.failures = code === 'screenshot_failed' ? state.failures + 1 : 0;
  el('frame').hidden = true; el('frame').removeAttribute('src'); el('cursor').hidden = true;
  el('empty').hidden = false;
  text('empty-title', label[1]); text('empty-copy', label[2]); text('frame-age', label[0]);
  status(label[0]); notice();
  return true;
}
function imageBlock(result) {
  return result.content?.find(item => item.type === 'image' &&
    ['image/png', 'image/jpeg', 'image/webp'].includes(item.mimeType) &&
    typeof item.data === 'string' && item.data.length > 0 && item.data.length <= MAX_IMAGE_BASE64 &&
    /^[A-Za-z0-9+/]*={0,2}$/.test(item.data));
}
function renderFrame(result, data) {
  const image = imageBlock(result);
  if (!image) throw new Error('The worker returned no supported preview image.');
  state.frame = data;
  state.paused = data.paused === true;
  if (typeof data.url === 'string') {
    const session = state.sessions.find(item => item.session_id === state.sessionId);
    if (session) session.url = data.url;
    updateSessionLabel();
  }
  el('frame').src = `data:${image.mimeType};base64,${image.data}`;
  el('frame').hidden = false;
  el('empty').hidden = true;
  text('frame-age', `Updated ${new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'})}`);
  status(state.paused ? 'Input paused' : 'Live', 'live');
  workState();
  updateCursor();
}
function updateCursor() {
  const image = el('frame');
  const cursor = state.frame?.cursor;
  if (image.hidden || !cursor || cursor.visible === false || !Number.isFinite(cursor.x) || !Number.isFinite(cursor.y)) {
    el('cursor').hidden = true; return;
  }
  const sourceWidth = state.frame?.viewport?.width || state.frame?.width || image.naturalWidth;
  const sourceHeight = state.frame?.viewport?.height || state.frame?.height || image.naturalHeight;
  if (!sourceWidth || !sourceHeight || cursor.x < 0 || cursor.y < 0 || cursor.x > sourceWidth || cursor.y > sourceHeight) {
    el('cursor').hidden = true; return;
  }
  const width = el('screen').clientWidth, height = el('screen').clientHeight;
  const factor = Math.min(width / sourceWidth, height / sourceHeight);
  const x = (width - sourceWidth * factor) / 2 + cursor.x * factor;
  const y = (height - sourceHeight * factor) / 2 + cursor.y * factor;
  el('cursor').style.left = `${x - 3}px`;
  el('cursor').style.top = `${y - 2}px`;
  el('cursor').hidden = false;
}
async function refreshFrame(manual = false) {
  stopPolling();
  const setup = selectedSetupProblem();
  if (setup) { captureProblem(setup); return; }
  if (manual) state.blockedFrames.delete(state.sessionId);
  if (manual && state.pendingFrames.get(state.sessionId)?.halted) state.pendingFrames.delete(state.sessionId);
  if (!canPoll()) return;
  if (state.busy) { schedule(250); return; }
  const generation = state.generation, sessionId = state.sessionId;
  setBusy(true);
  try {
    let result = null;
    if (!state.pendingFrames.has(sessionId)) result = await app.callServerTool({name: 'rdc_preview_frame', arguments: {session_id: sessionId}}, {timeout: 15000});
    result = await resolvePreview('frame', result, sessionId, generation);
    if (!result) return;
    if (state.disposed || state.hidden || generation !== state.generation) return;
    const data = checkResult(result);
    if (data.session_id && data.session_id !== sessionId) throw new Error('The preview response belongs to a different session.');
    if (data.device_id && state.deviceId && data.device_id !== state.deviceId) throw new Error('The preview response belongs to a different worker.');
    renderFrame(result, data);
    state.failures = 0; notice();
  } catch (error) {
    if (!state.disposed && !state.hidden && generation === state.generation) {
      if (!captureProblem(error.code)) {
        state.failures += 1;
        status('Reconnecting', 'error');
        notice(error.message || 'The preview connection was interrupted. The worker may still be running.');
      }
    }
  } finally {
    setBusy(false);
    schedule(state.failures ? Math.min(15000, POLL_MS * 2 ** state.failures) : POLL_MS);
  }
}
async function refreshSessions(manual = false) {
  if (!state.connected || !state.bridgeReady || state.disposed || state.busy) return;
  if (manual && state.pendingOpen?.halted) state.pendingOpen = null;
  if (state.pendingOpen?.halted) return;
  stopPolling(); setBusy(true);
  let generation = state.generation;
  try {
    // Reopen the selected session explicitly. If it has ended, retrieve a list
    // but leave the preview unselected until the person chooses another one.
    const requestedSessionId = state.pendingOpen ? state.pendingOpen.sessionId : state.sessionId;
    const args = requestedSessionId ? {session_id: requestedSessionId} : {};
    let result = state.pendingOpen ? null : await app.callServerTool({name: 'rdc_preview_open', arguments: args}, {timeout: 15000});
    result = await resolvePreview('open', result, requestedSessionId, generation);
    if (!result) return;
    if (dataOf(result)?.error?.code === 'session_not_found') {
      // Preserve a newer explicit choice if selection changed while the
      // original operation was pending. Otherwise clear the ended session
      // before fetching, so a delayed list never retries the stale selection.
      if (state.sessionId === requestedSessionId) {
        state.selectionLost = true;
        selectSession(null);
        el('session').value = '';
      }
      generation = state.generation;
      result = await app.callServerTool({name: 'rdc_preview_open', arguments: {}}, {timeout: 15000});
      result = await resolvePreview('open', result, null, generation);
      if (!result) return;
    }
    if (!state.disposed) { notice(); acceptOpen(checkResult(result), true); }
  } catch (error) { if (!state.disposed) notice(error.message || 'Could not refresh sessions.'); }
  finally { setBusy(false); schedule(0); }
}
function hidePreview() {
  state.hidden = true; state.generation += 1; stopPolling();
  interruptRecovery();
  el('panel').hidden = true; el('closed-card').hidden = false;
  text('closed-note', 'The worker and its tasks keep running.');
  el('closed-session-label').hidden = !state.sessionId;
  el('closed-session-id').value = state.sessionId || '';
  if (state.mode === 'fullscreen') el('canvas').style.height = 'auto';
  void retainSelection();
  el('reopen').focus();
}
function reopenPreview() {
  state.hidden = false; state.generation += 1;
  el('closed-card').hidden = true; el('panel').hidden = false;
  applyLayout();
  schedule(0);
  void retainSelection();
  el('hide').focus();
}
function canvasSize() {
  const context = app.getHostContext();
  const hostHeight = context?.containerDimensions?.height;
  return {width: Math.max(1, document.documentElement.clientWidth), height: Math.max(1, Number.isFinite(hostHeight) ? hostHeight : window.innerHeight)};
}
function clampPanel() {
  const size = canvasSize(), margin = Math.min(size.width < 500 ? 4 : 16, size.width / 4, size.height / 4);
  const availableWidth = size.width - 2 * margin, availableHeight = size.height - 2 * margin;
  const minWidth = Math.min(320, availableWidth), minHeight = Math.min(300, availableHeight);
  const p = state.panel;
  p.width = clamp(p.width, minWidth, availableWidth);
  p.height = clamp(p.height, minHeight, availableHeight);
  p.x = clamp(p.x, margin, size.width - margin - p.width);
  p.y = clamp(p.y, margin, size.height - margin - p.height);
}
function resetLayout() {
  const {width, height} = canvasSize(), margin = Math.min(width < 500 ? 4 : 16, width / 4, height / 4);
  const panelWidth = Math.min(1100, width - 2 * margin);
  state.panel = {x: (width - panelWidth) / 2, y: margin, width: panelWidth, height: height - 2 * margin};
  applyLayout();
}
function applyLayout() {
  const fullscreen = state.mode === 'fullscreen';
  el('canvas').dataset.mode = state.mode;
  ['move', 'resize', 'reset-layout', 'movement-note'].forEach(id => { el(id).hidden = !fullscreen; });
  el('size-label').hidden = fullscreen || state.mode === 'pip';
  if (fullscreen && !state.hidden) {
    el('canvas').style.height = `${canvasSize().height}px`;
    if (!state.panel) { resetLayout(); return; }
    clampPanel();
    const p = state.panel;
    Object.assign(el('panel').style, {left: `${p.x}px`, top: `${p.y}px`, width: `${p.width}px`, height: `${p.height}px`});
    el('screen').style.height = '';
  } else {
    el('canvas').style.height = '';
    ['left', 'top', 'width', 'height'].forEach(key => { el('panel').style[key] = ''; });
    el('screen').style.height = state.mode === 'inline' ? `${el('view-size').value}px` : '';
  }
  updateCursor();
}
function hostContextChanged(context = {}) {
  if (context.theme) document.documentElement.dataset.theme = context.theme;
  const current = app.getHostContext() || context;
  if (Array.isArray(current.availableDisplayModes)) state.modes = current.availableDisplayModes;
  if (current.displayMode) state.mode = current.displayMode;
  el('expand').hidden = state.mode === 'fullscreen' || !state.modes.includes('fullscreen');
  el('float').hidden = state.mode === 'pip' || !state.modes.includes('pip');
  el('inline').hidden = state.mode === 'inline' || !state.modes.includes('inline');
  applyLayout();
}
async function requestMode(mode) {
  if (!state.connected || !state.modes.includes(mode)) return;
  try {
    const result = await app.requestDisplayMode({mode}, {timeout: 10000});
    // The host may choose a different mode. Never claim the request was granted.
    state.mode = result.mode;
    el('expand').hidden = state.mode === 'fullscreen' || !state.modes.includes('fullscreen');
    el('float').hidden = state.mode === 'pip' || !state.modes.includes('pip');
    el('inline').hidden = state.mode === 'inline' || !state.modes.includes('inline');
    applyLayout();
    if (result.mode !== mode) notice('Your AI app kept the preview in its current display mode.');
    else notice();
  } catch (error) { notice(error.message || 'Your AI app could not change the display mode.'); }
}
function pointerStart(event, kind) {
  if (state.mode !== 'fullscreen' || event.button !== 0) return;
  event.preventDefault();
  state.dragging = {kind, x: event.clientX, y: event.clientY, start: {...state.panel}, pointerId: event.pointerId};
  event.currentTarget.setPointerCapture(event.pointerId);
}
function pointerMove(event) {
  const d = state.dragging;
  if (!d || event.pointerId !== d.pointerId) return;
  const dx = event.clientX - d.x, dy = event.clientY - d.y;
  state.panel = d.kind === 'move' ? {...d.start, x: d.start.x + dx, y: d.start.y + dy} :
    {...d.start, width: d.start.width + dx, height: d.start.height + dy};
  applyLayout();
}
function keyboardLayout(event, kind) {
  if (state.mode !== 'fullscreen' || !['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) return;
  event.preventDefault();
  const step = event.shiftKey ? 4 : 20;
  const x = (event.key === 'ArrowRight' ? step : 0) - (event.key === 'ArrowLeft' ? step : 0);
  const y = (event.key === 'ArrowDown' ? step : 0) - (event.key === 'ArrowUp' ? step : 0);
  if (kind === 'move') { state.panel.x += x; state.panel.y += y; }
  else { state.panel.width += x; state.panel.height += y; }
  applyLayout();
}
function dispose() {
  state.disposed = true; state.generation += 1; stopPolling();
  interruptRecovery();
  state.dragging = null;
  el('frame').removeAttribute('src');
  el('frame').hidden = true; el('cursor').hidden = true;
  state.frame = null;
  // Deliberately no browser_close, job_cancel, pause, or owner API call.
}

app.ontoolinput = ({arguments: args}) => {
  if (typeof args?.session_id === 'string' && !state.haveOpenResult) state.sessionId = args.session_id;
};
app.ontoolresult = result => {
  if (state.disposed) return;
  try {
    const pending = pendingFrom(result);
    if (pending) {
      if (!state.pendingOpen) state.pendingOpen = {...pending, sessionId: state.sessionId};
    } else acceptOpen(checkResult(result));
    if (!state.hidden) schedule(0);
  }
  catch (error) { notice(error.message); status('Unavailable', 'error'); }
};
app.onhostcontextchanged = hostContextChanged;
app.onteardown = async () => { dispose(); return {}; };
el('hide').addEventListener('click', hidePreview);
el('reopen').addEventListener('click', reopenPreview);
el('dismiss').addEventListener('click', async () => {
  if (!state.connected || state.disposed) return;
  try {
    await retainSelection();
    await app.requestTeardown();
    text('closed-note', 'Dismiss requested. The worker keeps running. Ask your agent to reopen this session.');
  } catch { text('closed-note', 'This AI app could not dismiss the view. The worker keeps running.'); }
});
el('expand').addEventListener('click', () => requestMode('fullscreen'));
el('float').addEventListener('click', () => requestMode('pip'));
el('inline').addEventListener('click', () => requestMode('inline'));
el('session').addEventListener('change', event => { state.selectionLost = false; notice(); selectSession(event.target.value); void retainSelection(); });
el('closed-session-id').addEventListener('click', event => event.target.select());
el('refresh').addEventListener('click', () => refreshFrame(true));
el('sessions-refresh').addEventListener('click', () => refreshSessions(true));
el('view-size').addEventListener('change', applyLayout);
el('reset-layout').addEventListener('click', resetLayout);
el('frame').addEventListener('load', updateCursor);
for (const kind of ['move', 'resize']) {
  const handle = el(kind);
  handle.addEventListener('pointerdown', event => pointerStart(event, kind));
  handle.addEventListener('pointermove', pointerMove);
  handle.addEventListener('pointerup', () => { state.dragging = null; });
  handle.addEventListener('pointercancel', () => { state.dragging = null; });
  handle.addEventListener('keydown', event => keyboardLayout(event, kind));
}
document.addEventListener('visibilitychange', () => { if (document.hidden) { stopPolling(); interruptRecovery(); } else schedule(0); });
window.addEventListener('resize', applyLayout);
window.addEventListener('pagehide', dispose, {once: true});

async function connect() {
  if (window.parent === window) {
    status('Host required');
    text('empty-title', 'Open this preview inside your AI app');
    text('empty-copy', 'RDC delivers this view through an MCP Apps connection. Ask your connected agent to open the RDC preview.');
    return;
  }
  try {
    await app.connect(new PostMessageTransport(window.parent, window.parent), {timeout: 15000});
    if (state.disposed) return;
    state.connected = true;
    hostContextChanged(app.getHostContext());
    state.bridgeReady = !!app.getHostCapabilities()?.serverTools;
    if (!state.bridgeReady) {
      status('Preview unavailable', 'error');
      notice('This AI app does not provide the server-tool bridge needed for live preview.');
      return;
    }
    setBusy(false);
    // The host owns the initial tool invocation and will deliver its result.
    // Starting another open here could duplicate a still-pending cloud request.
    if (state.haveOpenResult || state.pendingOpen) schedule(0);
    else { status('Waiting for tool result'); text('empty-copy', 'Waiting for your AI app to deliver the active preview. Sessions can request a fresh view if needed.'); }
  } catch (error) {
    if (state.disposed) return;
    status('Connection unavailable', 'error');
    text('empty-title', 'The preview could not connect');
    text('empty-copy', 'Your AI app must support MCP Apps. The worker and its tasks are separate from this view.');
    notice(error.message || 'The host did not complete preview initialization.');
  }
}
connect();
