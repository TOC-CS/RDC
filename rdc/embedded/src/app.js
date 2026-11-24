import { App, PostMessageTransport } from '@modelcontextprotocol/ext-apps';

const brandSource = 'RDC_LOGO_DATA';
document.querySelectorAll('[data-rdc-logo]').forEach(image => { image.src = brandSource; });

// The host mediates every request. This view never contacts a worker URL,
// receives owner credentials, or changes worker/session/job lifetime.
const app = new App({name: 'RDC Preview', version: '0.1.0a8-preview.9'}, {
  availableDisplayModes: ['inline', 'fullscreen', 'pip'],
});
const el = id => document.getElementById(id);
const state = {
  connected: false, connecting: false, bridgeReady: false, disposed: false,
  hidden: false, busy: false, timer: null, generation: 0,
  sessionId: null, deviceId: null, frame: null, haveOpenResult: false, unboundResultReceived: false,
  taskJobId: null, taskClosed: false,
  availability: null, selectionLost: false, setupProblem: null,
  mode: 'inline', modes: ['inline'], presentationBridge: 'mcp',
  autoFloatAttempted: false, floatPending: false, modeRequest: 0, openPresentationRequested: false,
  resizeEnabled: false, resizeBlocked: false, pendingResize: null, resizedFor: null, resizeActual: null,
  pendingOpen: null, pendingFrames: new Map(), blockedFrames: new Map(),
  recoveryTimer: null, recoveryWake: null, retiredOpens: new Set(), retiredObservations: new Map(),
};
const POLL_MS = 1500;
const MAX_IMAGE_BASE64 = 12 * 1024 * 1024;
const sourceId = value => typeof value === 'string' &&
  /^(?:(?:(?:mobile|window)-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|android-adb)$/.test(value);
const text = (id, value) => { el(id).textContent = String(value ?? ''); };
function status(value, style = '') { text('connection-text', value); el('connection').className = 'status ' + style; }
function stopPolling() { clearTimeout(state.timer); state.timer = null; }
function visibleConnected() { return state.connected && state.bridgeReady && !state.disposed && !state.hidden && !document.hidden; }
function visibleGeneration(generation) { return visibleConnected() && generation === state.generation; }
function canPoll() {
  return visibleConnected() && state.haveOpenResult && state.sessionId && !state.taskClosed && !state.selectionLost &&
    !state.availability && !state.setupProblem && !state.pendingFrames.get(state.sessionId)?.halted && !state.blockedFrames.has(state.sessionId);
}
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
  if (!visibleConnected() || state.availability || state.selectionLost) return;
  if (state.pendingOpen) {
    if (!state.pendingOpen.halted) state.timer = setTimeout(() => refreshSessions(), delay);
  } else if (state.unboundResultReceived && sourceId(state.sessionId)) {
    state.timer = setTimeout(() => refreshSessions(), delay);
  } else if (canPoll()) state.timer = setTimeout(() => refreshFrame(), delay);
}
function dataOf(result) {
  if (result?.structuredContent && typeof result.structuredContent === 'object') return result.structuredContent;
  const block = result?.content?.find(item => item.type === 'text');
  if (block?.text) { try { return JSON.parse(block.text); } catch {} }
  return {};
}
const operationId = value => typeof value === 'string' && /^[A-Za-z0-9_.-]{1,128}$/.test(value);
const jobId = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
const previewTools = new Set(['rdc_preview_open', 'rdc_preview_frame', 'rdc_operation_status', 'rdc_preview_resize']);
function previewError(data = {}) {
  const messages = {
    result_expired: 'The previous preview observation expired.',
    result_unavailable: 'The previous preview observation is unavailable.',
    operation_not_found: 'The original preview operation is no longer retained.',
    operation_unknown: 'The original preview request has an uncertain outcome.',
    observation_interrupted: 'The read-only observation was interrupted.',
    session_not_found: 'This preview session has ended.',
    session_required: 'Open the preview for the visual source this task is using.',
  };
  const error = new Error(messages[data.error?.code] || 'The preview request could not be confirmed.');
  error.code = data.error?.code;
  error.operation_id = data.operation_id;
  error.completed = data.completed === true;
  error.previewSafe = true;
  return error;
}
function failureData(value, depth = 0) {
  // Hosts can wrap a tool result in JSON and a Python TextContent repr. Parse
  // bounded data only. Words inside an opaque exception never authorize retry.
  if (!value || depth > 5) return null;
  if (typeof value === 'object') {
    if (value.ok === false && typeof value.error?.code === 'string') return value;
    const nested = [value.structuredContent, value.data, value.detail, value.details, value.message,
      ...(Array.isArray(value.content) ? value.content.slice(0, 2).map(item => item?.text) : [])];
    for (const item of nested) { const found = failureData(item, depth + 1); if (found) return found; }
    return null;
  }
  if (typeof value !== 'string' || value.length > 65536) return null;
  const candidates = [value];
  // A JSON-RPC error may prefix the JSON object with its own error label.
  const first = value.indexOf('{'), last = value.lastIndexOf('}');
  if (first >= 0 && last > first && (first !== 0 || last !== value.length - 1)) candidates.push(value.slice(first, last + 1));
  for (const candidate of candidates) {
    try { const found = failureData(JSON.parse(candidate), depth + 1); if (found) return found; } catch {}
  }
  const wrapped = /TextContent\(type=(?:'text'|"text"),\s*text=('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")/.exec(value);
  if (wrapped) {
    const decoded = wrapped[1].slice(1, -1).replace(/\\(['"\\])/g, '$1');
    try { return failureData(JSON.parse(decoded), depth + 1); } catch {}
  }
  return null;
}
function normalizePreviewError(error) { return error?.previewSafe ? error : previewError(failureData(error) || {}); }
function failureResult(error) { return {isError:true,structuredContent:{ok:false,error:{code:error.code}}}; }
function missingLookupData(value, depth = 0) {
  if (!value || depth > 5) return null;
  if (typeof value === 'object') {
    if (value.code === -32002 && value.data?.code === 'operation_not_found') return value.data;
    for (const item of [value.error, value.data, value.detail, value.details, value.message]) {
      const found = missingLookupData(item, depth + 1); if (found) return found;
    }
  } else if (typeof value === 'string' && value.length <= 65536) {
    const first = value.indexOf('{'), last = value.lastIndexOf('}');
    for (const candidate of [value, first >= 0 && last > first ? value.slice(first, last + 1) : '']) {
      try { const found = missingLookupData(JSON.parse(candidate), depth + 1); if (found) return found; } catch {}
    }
  }
  return null;
}
async function callPreviewTool(name, args = {}) {
  if (!previewTools.has(name)) throw new Error('Unsupported preview observation.');
  try { return await app.callServerTool({name, arguments: args}, {timeout: 15000}); }
  catch (error) {
    const missing = name === 'rdc_operation_status' && operationId(args.operation_id) ? missingLookupData(error) : null;
    if (missing && (missing.operation_id === undefined || missing.operation_id === args.operation_id)) {
      // The typed RPC lookup failure is bound to this exact read request. It
      // says the identity is no longer retained, never that work completed.
      const normalized = previewError({error:{code:'operation_not_found'},operation_id:args.operation_id});
      normalized.missing_lookup_id = args.operation_id;
      throw normalized;
    }
    throw normalizePreviewError(error);
  }
}
function checkResult(result) {
  const data = dataOf(result);
  if (result?.isError || data.ok === false) throw previewError(data);
  return data;
}
function refreshRequired(result, pending, tool) {
  const data = dataOf(result);
  if (data.preview_refresh_required !== true) return false;
  if (result?.isError || data.ok !== true || data.completed !== true || data.refresh_tool !== tool ||
      !operationId(data.operation_id) || (pending && data.operation_id !== pending.operation_id) ||
      !['result_expired', 'result_unavailable'].includes(data.reason)) throw new Error('The preview recovery response could not be verified.');
  if (pending) pending.refreshReason = data.reason;
  return true;
}
function expiredObservation(error, pending) {
  return ['result_expired', 'result_unavailable'].includes(error.code) && error.completed === true &&
    operationId(error.operation_id) && error.operation_id === pending?.operation_id;
}
function renewableObservation(error, pending) {
  if (expiredObservation(error, pending)) {pending.refreshReason = error.code; return true;}
  if (error.code === 'operation_not_found' && error.missing_lookup_id === pending?.operation_id && error.operation_id === pending.operation_id) {
    pending.refreshReason = 'operation_not_found'; return true;
  }
  return false;
}
function retireObservation(tool, pending) {
  state.retiredObservations.set(pending.operation_id, {operation_id:pending.operation_id,tool,reason:pending.refreshReason || 'read_refresh_requested'});
  if (state.retiredObservations.size > 64) state.retiredObservations.delete(state.retiredObservations.keys().next().value);
}
function retireOpen(id) {
  state.retiredOpens.add(id);
  if (state.retiredOpens.size > 64) state.retiredOpens.delete(state.retiredOpens.values().next().value);
}
function resumePending(pending) {
  if (!pending) return;
  pending.halted = false; pending.deadline = performance.now() + 120000;
  if (pending.terminal) pending.replacements = 0;
}
function setBusy(value) {
  state.busy = value;
  el('preview-retry').disabled = value || !visibleConnected();
}
function clearFrame() {
  state.frame = null;
  el('frame').removeAttribute('src');
  el('frame').hidden = true;
  el('cursor').hidden = true;
}
function empty(title, copy, retry = false) {
  clearFrame();
  text('empty-title', title);
  text('empty-copy', copy);
  el('empty').hidden = false;
  el('preview-retry').hidden = !retry;
  setBusy(state.busy);
}
function unbound() {
  state.haveOpenResult = false;
  state.unboundResultReceived = true;
  empty('No visual source', 'Open the preview for the RDC session this task is using.');
  status('No source');
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
  } catch { /* Host context is optional; the agent can retain the original tool input. */ }
}
function pendingFrom(result) {
  const data = dataOf(result);
  if (data.pending !== true) return null;
  if (data.recovery_tool !== 'rdc_operation_status' || !operationId(data.operation_id)) {
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
async function renewPreview(kind, pending, sessionId, generation) {
  pending.terminal = true; pending.halted = true;
  retireObservation(kind === 'open' ? 'rdc_preview_open' : 'rdc_preview_frame', pending);
  if (kind === 'open') retireOpen(pending.operation_id);
  if ((pending.replacements || 0) >= 1) throw new Error('The fresh preview observation also expired. Retry preview to try again.');
  pending.replacements = 1;
  if (!sessionId) throw previewError({error:{code:'session_required'}});
  status('Refreshing');
  const tool = kind === 'open' ? 'rdc_preview_open' : 'rdc_preview_frame';
  const fresh = await callPreviewTool(tool, {session_id: sessionId,
    ...(state.taskJobId ? {job_id:state.taskJobId} : {})});
  // Even if the view was hidden while awaiting the call, record the new
  // pending identity before returning. Its outcome must not be guessed.
  savePending(kind, sessionId, null);
  return resolvePreview(kind, fresh, sessionId, generation, 1);
}
async function resolvePreview(kind, result, sessionId, generation, replacements = 0) {
  const tool = kind === 'open' ? 'rdc_preview_open' : 'rdc_preview_frame';
  let pending = pendingFor(kind, sessionId);
  if (result) {
    if (refreshRequired(result, pending, tool)) {
      pending ||= {operation_id: dataOf(result).operation_id, deadline: performance.now() + 120000, sessionId, replacements};
      pending.terminal = true; pending.halted = false;
      savePending(kind, sessionId, pending);
    } else {
      const supplied = pendingFrom(result);
      if (!supplied) return result;
      if (pending && pending.operation_id !== supplied.operation_id) throw new Error('A preview recovery response changed the operation identity.');
      pending ||= {...supplied, sessionId, replacements};
      savePending(kind, sessionId, pending);
    }
  }
  while (pending) {
    if (!visibleConnected() || generation !== state.generation) return null;
    if (pending.halted || performance.now() >= pending.deadline) {
      pending.halted = true;
      throw new Error(kind === 'frame' ? 'The preview recovery wait ended. Retry preview checks the original observation.' : 'The preview open is still unconfirmed. Retry preview checks the original request.');
    }
    if (pending.terminal) return renewPreview(kind, pending, sessionId, generation);
    status('Waiting for worker');
    await recoveryDelay();
    if (!visibleConnected() || generation !== state.generation) return null;
    let recovered;
    try { recovered = await callPreviewTool('rdc_operation_status', {operation_id: pending.operation_id}); }
    catch (error) {
      if (!visibleConnected() || generation !== state.generation) return null;
      if (renewableObservation(error, pending)) return renewPreview(kind, pending, sessionId, generation);
      if (captureErrors.has(error.code)) recovered = failureResult(error);
      else {pending.halted = true;throw error;}
    }
    // A newer availability observation, hide, or selection supersedes this
    // lookup. Retain its original pending reference for explicit inspection.
    if (!visibleConnected() || generation !== state.generation) return null;
    if (refreshRequired(recovered, pending, tool)) return renewPreview(kind, pending, sessionId, generation);
    const continued = pendingFrom(recovered);
    if (continued) {
      if (continued.operation_id !== pending.operation_id) throw new Error('A preview recovery response changed the operation identity.');
      continue;
    }
    try { checkResult(recovered); }
    catch (error) {
      if (renewableObservation(error, pending)) return renewPreview(kind, pending, sessionId, generation);
      if (captureErrors.has(error.code)) {
        savePending(kind, sessionId, null);
        if (kind === 'open') retireOpen(pending.operation_id);
        return recovered;
      }
      pending.halted = true;
      error.message += ` ${kind === 'frame' ? 'Retry preview checks the original observation.' : 'Retry preview checks the original request.'}`;
      throw error;
    }
    savePending(kind, sessionId, null);
    if (kind === 'open') retireOpen(pending.operation_id);
    return recovered;
  }
  return result;
}
function acceptAvailability(data) {
  if (data?.preview_unavailable !== true) return false;
  const descriptions = {
    device_offline: ['Device offline', 'The paired device is offline. No new preview request was queued.'],
    gateway_busy: ['Gateway busy', 'The gateway is busy. No new preview request was queued.'],
  };
  const description = descriptions[data.preview_status];
  if (!description) throw new Error('The gateway returned an unsupported preview availability result.');
  requireDevice(data);
  state.availability = data.preview_status;
  state.generation += 1;
  stopPolling(); interruptRecovery();
  empty(description[0], description[1], Boolean(state.sessionId || state.pendingOpen));
  status(description[0], 'error');
  return true;
}
function requireDevice(data) {
  if (data.device_id && state.deviceId && data.device_id !== state.deviceId) {
    throw new Error('The preview response belongs to a different worker.');
  }
  if (typeof data.device_id === 'string' && data.device_id) state.deviceId ||= data.device_id;
}
function acceptOpen(data) {
  if (acceptAvailability(data)) return;
  // A legacy worker may report global focus when called without a session ID.
  // Accept an ID only from this mount's tool input or an explicit binding
  // confirmed by the worker. Never infer a target from an activity/session list.
  if (!state.sessionId && data.viewer?.bound_to_session === true && sourceId(data.session_id)) {
    state.sessionId = data.session_id;
  }
  if (!state.sessionId) { unbound(); return; }
  if (data.session_id !== state.sessionId) throw new Error('The preview response belongs to a different session.');
  if (state.taskJobId && data.viewer?.task_job_id !== state.taskJobId)
    throw new Error('The preview open did not verify its selected job.');
  requireDevice(data);
  if (!state.deviceId) throw new Error('The preview worker could not be identified.');
  state.availability = null;
  state.selectionLost = false;
  state.haveOpenResult = true;
  state.unboundResultReceived = false;
  const selected = Array.isArray(data.sessions) && data.sessions.find(item => item?.session_id === state.sessionId);
  state.resizeEnabled = state.sessionId.startsWith('window-') && selected?.resize_to_view === true;
  if (state.setupProblem) state.blockedFrames.delete(state.sessionId);
  const setup = selected?.setup_status && 'mobile_' + selected.setup_status;
  state.setupProblem = captureErrors.has(setup) ? setup : null;
  if (state.setupProblem) { captureProblem(state.setupProblem); return; }
  if (!state.frame) empty('Waiting for the live view', 'The preview connects to this session as work continues.');
  status(data.paused ? 'Input paused' : 'Connecting');
}
const captureErrors = new Map([
  ['window_required', ['Select the task window', 'Open a native window binding for this task. Full-desktop previews are disabled.']],
  ['screen_permission_required', ['Window capture unavailable', 'The native helper needs macOS Screen Recording permission. Work keeps running.']],
  ['accessibility_permission_required', ['Allow window resizing', 'Enable macOS Accessibility for RDC Window Preview, then retry this preview. Work keeps running.']],
  ['window_capture_unavailable', ['Window capture unavailable', 'The selected window could not be captured. No desktop fallback was used.']],
  ['session_not_found', ['Session ended', 'This session is no longer available. Open a new preview for your next task.']],
  ['mobile_session_gone', ['Session ended', 'This device session has ended. Inspect the same session before starting a replacement.']],
  ['mobile_cleanup_required', ['Session unavailable', 'This device session needs cleanup.']],
  ['mobile_creation_unknown', ['Session unavailable', 'The device session could not be verified.']],
  ['screenshot_redaction_required', ['Preview hidden for privacy', 'The current screen cannot be shown safely.']],
  ['screenshot_failed', ['Preview unavailable', 'A verified image could not be captured.']],
]);
function captureProblem(code) {
  const message = captureErrors.get(code);
  if (!message) return false;
  state.selectionLost = code === 'session_not_found';
  state.blockedFrames.set(state.sessionId, code);
  empty(...message, !state.selectionLost);
  status(message[0], 'error');
  return true;
}
function reportFailure(error) {
  if (error.code === 'session_required') { state.pendingOpen = null; unbound(); return; }
  if (captureProblem(error.code)) return;
  empty('Preview unavailable', error.message || 'The live view could not be confirmed.', Boolean(state.sessionId || state.pendingOpen));
  status('Preview unavailable', 'error');
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
  if (state.resizeEnabled && Number.isFinite(data.window_width) && Number.isFinite(data.window_height) &&
      data.window_width>0 && data.window_height>0 && data.window_width<=32768 && data.window_height<=32768) {
    // The app or owner may resize independently after our last response.
    // Draw current window proportions; never stretch to obsolete dimensions.
    state.resizeActual = {width:data.window_width,height:data.window_height};
  }
  const actual = state.resizeActual;
  const windowSized = state.resizeEnabled && !state.resizeBlocked && actual;
  el('screen').classList.toggle('window-sized', Boolean(windowSized));
  if (!windowSized) { el('frame').style.width=''; el('frame').style.height=''; }
  if (windowSized) {
    el('frame').style.width = actual.width + 'px';
    el('frame').style.height = actual.height + 'px';
  }
  // Never attach the next cursor position to the previous decoded frame.
  el('cursor').hidden = true;
  el('frame').src = 'data:' + image.mimeType + ';base64,' + image.data;
  el('frame').hidden = false;
  el('empty').hidden = true;
  status(data.paused ? 'Input paused' : 'Live', 'live');
  updateCursor();
}
function updateCursor() {
  const marker = el('cursor');
  marker.hidden = true;
  const image = el('frame');
  const frame = state.frame;
  const cursor = frame?.cursor;
  if (image.hidden || !image.complete || !image.naturalWidth || !image.naturalHeight ||
      state.hidden || state.disposed || frame?.cursor_in_image === true ||
      frame?.session_id !== state.sessionId || frame?.device_id !== state.deviceId ||
      !cursor || cursor.visible === false ||
      (cursor.visible !== true && cursor.x === 0 && cursor.y === 0) ||
      !Number.isFinite(cursor.x) || !Number.isFinite(cursor.y)) return;
  const sourceWidth = frame?.viewport?.width || frame?.width || image.naturalWidth;
  const sourceHeight = frame?.viewport?.height || frame?.height || image.naturalHeight;
  if (!Number.isFinite(sourceWidth) || !Number.isFinite(sourceHeight) ||
      sourceWidth <= 0 || sourceHeight <= 0 ||
      cursor.x < 0 || cursor.y < 0 || cursor.x >= sourceWidth || cursor.y >= sourceHeight) return;

  const imageBox = image.getBoundingClientRect();
  const screen = el('screen'), screenBox = screen.getBoundingClientRect();
  const fit = getComputedStyle(image).objectFit;
  let drawWidth = imageBox.width, drawHeight = imageBox.height;
  let drawLeft = imageBox.left, drawTop = imageBox.top;
  if (fit === 'contain') {
    // The image is top-centered inside its IMG box, with possible side bars.
    // Calculate from actual decoded pixels rather than the preview container.
    const scale = Math.min(imageBox.width / image.naturalWidth, imageBox.height / image.naturalHeight);
    drawWidth = image.naturalWidth * scale;
    drawHeight = image.naturalHeight * scale;
    drawLeft += (imageBox.width - drawWidth) / 2;
  } else if (fit !== 'fill') return;
  if (!drawWidth || !drawHeight) return;

  // Convert the actual rendered pixels to scroll-content coordinates for
  // native windows larger than the preview. Do not use global desktop coords.
  const left = drawLeft - screenBox.left + screen.scrollLeft;
  const top = drawTop - screenBox.top + screen.scrollTop;
  const markerLeft = left + cursor.x / sourceWidth * drawWidth - 3;
  const markerTop = top + cursor.y / sourceHeight * drawHeight - 2;
  marker.style.left = markerLeft + 'px';
  marker.style.top = markerTop + 'px';
  // Clip the entire marker glyph to the selected source, including at edges.
  const clipTop = Math.max(0, top - markerTop);
  const clipRight = Math.max(0, markerLeft + 23 - (left + drawWidth));
  const clipBottom = Math.max(0, markerTop + 29 - (top + drawHeight));
  const clipLeft = Math.max(0, left - markerLeft);
  marker.style.clipPath = 'inset(' + clipTop + 'px ' + clipRight + 'px ' + clipBottom + 'px ' + clipLeft + 'px)';
  marker.hidden = false;
}
async function fitNativeWindow(sessionId, generation) {
  if (!state.resizeEnabled || state.resizeBlocked) return true;
  const width = Math.max(240, Math.min(2560, Math.round(el('screen').clientWidth)));
  const height = Math.max(180, Math.min(1600, Math.round(el('screen').clientHeight)));
  const sizeKey = `${width}x${height}`;
  if (!state.pendingResize && state.resizedFor === sizeKey) return true;
  // Retain exact mutation arguments before dispatch. A lost response is retried
  // only with this same key; a queued operation is recovered by its original ID.
  const pending = state.pendingResize ||= {sizeKey, arguments:{session_id:sessionId,width,height,
    _rdc_request_id:crypto.randomUUID()}, operation_id:null};
  let data;
  try {
    const result = pending.operation_id ?
      await callPreviewTool('rdc_operation_status', {operation_id:pending.operation_id}) :
      await callPreviewTool('rdc_preview_resize', pending.arguments);
    data = checkResult(result);
  }
  catch (error) {
    // These typed failures guarantee no native resize was attempted. Manual
    // Retry may make a fresh request after permission/selection is repaired.
    // Every uncertain outcome retains its original key or operation ID.
    if (['screen_permission_required','accessibility_permission_required','window_ambiguous'].includes(error.code)) state.pendingResize=null;
    if (error.code === 'accessibility_permission_required') {
      state.resizeBlocked = true;
      text('mode-note', 'Showing this window at its current size. Resizing needs macOS Accessibility.');
      el('mode-note').classList.add('size-note');
      el('resize-retry').hidden = false;
      return visibleGeneration(generation);
    }
    if (captureErrors.has(error.code)) throw error;
    // Resize and capture are independent. A host may not expose a newly
    // published resize tool yet, or its mutation result may be uncertain.
    // Keep its original key/operation for explicit recovery; never resubmit
    // on the frame timer. Read the same bound source through normal capture
    // checks, which still enforce permission, privacy and source identity.
    state.resizeBlocked = true;
    text('mode-note', 'Window resizing is unconfirmed. Showing this window at its current size.');
    el('mode-note').classList.add('size-note');
    el('resize-retry').hidden = false;
    return visibleGeneration(generation);
  }
  if (data.pending === true && operationId(data.operation_id)) {
    if (pending.operation_id && pending.operation_id !== data.operation_id) throw new Error('Resize recovery changed operation identity.');
    pending.operation_id = data.operation_id;
    status('Resizing');
    return false;
  }
  if (data.session_id !== sessionId || data.device_id !== state.deviceId ||
      !Number.isFinite(data.width) || !Number.isFinite(data.height) || data.width<=0 || data.height<=0) {
    throw new Error('The window resize could not be confirmed. Retry checks the original request.');
  }
  state.resizedFor = pending.sizeKey;
  state.resizeActual = {width:data.width,height:data.height};
  state.pendingResize = null;
  el('resize-retry').hidden = true;
  text('mode-note', data.size_constrained ? `App size limit: ${data.width} × ${data.height}. Scroll to see the whole window.` : '');
  el('mode-note').classList.toggle('size-note', data.size_constrained === true);
  return visibleGeneration(generation);
}
async function refreshFrame(manual = false) {
  if (!visibleConnected() || state.busy || state.selectionLost) return;
  stopPolling();
  if (manual) {
    state.blockedFrames.delete(state.sessionId);
    resumePending(state.pendingFrames.get(state.sessionId));
  }
  if (!canPoll()) return;
  const generation = state.generation, sessionId = state.sessionId;
  const started = performance.now();
  let nextDelay = POLL_MS;
  setBusy(true);
  try {
    if (!await fitNativeWindow(sessionId,generation) || !visibleGeneration(generation)) return;
    const first = state.pendingFrames.has(sessionId) ? null :
      await callPreviewTool('rdc_preview_frame', {session_id: sessionId,
        ...(state.taskJobId ? {job_id:state.taskJobId} : {})});
    const result = await resolvePreview('frame', first, sessionId, generation);
    if (!result || !visibleGeneration(generation)) return;
    const data = checkResult(result);
    if (data.session_id !== sessionId) throw new Error('The preview response belongs to a different session.');
    if (data.device_id !== state.deviceId) throw new Error('The preview response belongs to a different worker.');
    if (state.taskJobId) {
      const task=data.task;
      if (!task || task.job_id!==state.taskJobId || typeof task.status!=='string' ||
          typeof task.complete!=='boolean') throw new Error('The preview task belongs to a different job.');
      if (task.complete) {
        if (!['completed','failed','cancelled','timed_out'].includes(task.status))
          throw new Error('The task result cannot confirm safe viewer completion.');
        await clearCompletedFloatingView(sessionId, task.job_id, generation);
        return;
      }
    }
    renderFrame(result, data);
    // Fast local reads should not inherit cloud-sized idle waits. Slow reads
    // retain backpressure; requests remain single flight with a 250ms floor.
    nextDelay = Math.max(250, Math.min(POLL_MS, performance.now() - started));
  } catch (error) {
    if (visibleGeneration(generation)) {
      const pending = state.pendingFrames.get(sessionId);
      if (pending) pending.halted = true;
      state.blockedFrames.set(sessionId, 'preview_request_unconfirmed');
      reportFailure(error);
    }
  } finally { setBusy(false); schedule(nextDelay); }
}
async function refreshSessions(manual = false) {
  if (!visibleConnected() || state.busy || state.selectionLost) return;
  if (manual) resumePending(state.pendingOpen);
  if (state.pendingOpen?.halted || (!state.pendingOpen && !state.sessionId)) return;
  stopPolling(); setBusy(true);
  // Consume the late-binding recovery once. A failed open needs explicit retry.
  state.unboundResultReceived = false;
  const generation = state.generation;
  const requested = state.pendingOpen?.sessionId || state.sessionId;
  try {
    const first = state.pendingOpen ? null : await callPreviewTool('rdc_preview_open', {session_id: requested,
      ...(state.taskJobId ? {job_id:state.taskJobId} : {})});
    const result = await resolvePreview('open', first, requested, generation);
    if (result && visibleGeneration(generation)) {
      acceptOpen(checkResult(result));
      requestAutomaticFloat();
    }
  } catch (error) {
    if (visibleGeneration(generation)) {
      if (state.pendingOpen) state.pendingOpen.halted = true;
      state.haveOpenResult = false;
      reportFailure(error);
    }
  } finally { setBusy(false); schedule(0); }
}
async function retryPreview() {
  if (state.pendingOpen || state.availability || state.setupProblem || !state.haveOpenResult) await refreshSessions(true);
  else await refreshFrame(true);
}
async function clearCompletedFloatingView(sessionId, completedJobId, generation) {
  if (!visibleGeneration(generation) || sessionId!==state.sessionId ||
      completedJobId!==state.taskJobId || state.taskClosed) return;
  // Hide and stop this viewer first. The underlying job and visual session
  // are never closed or cancelled by a floating-window lifecycle transition.
  const floating=state.mode==='pip';
  state.taskClosed=true;
  hidePreview();
  text('closed-note', 'Task finished. Floating preview cleared. Work remains available.');
  if (floating) {
    try { await app.requestTeardown(); }
    catch { /* Host-owned floating mode can refuse teardown; hidden state remains safe. */ }
  }
}

function hidePreview() {
  state.modeRequest += 1; state.floatPending = false; state.autoFloatAttempted = false; state.openPresentationRequested = false;
  state.hidden = true; state.generation += 1; stopPolling(); interruptRecovery();
  if (state.frame) {
    empty('Waiting for the live view', 'The preview reconnects to this session when you reopen it.');
    status('Connecting');
  }
  el('panel').hidden = true; el('closed-card').hidden = false;
  void retainSelection();
  el('reopen').focus();
}
function reopenPreview() {
  state.hidden = false; state.generation += 1; state.autoFloatAttempted = false;
  el('closed-card').hidden = true; el('panel').hidden = false;
  setBusy(state.busy);
  schedule(0);
  void retainSelection();
  el('hide').focus();
  requestAutomaticFloat();
}
function applyLayout() {
  el('canvas').dataset.mode = state.mode;
  el('expand').hidden = state.mode === 'fullscreen' || !state.modes.includes('fullscreen');
  el('float').hidden = state.mode === 'pip' || !canFloatInHost();
  el('float').disabled = state.floatPending;
  el('inline').hidden = state.mode === 'inline' || !state.modes.includes('inline');
  updateCursor();
}
function canFloatInHost() {
  // The documented OpenAI bridge allows a user-initiated request even when
  // the separate MCP transport omits PiP. Its returned mode still decides.
  return state.modes.includes('pip') || typeof window.openai?.requestDisplayMode === 'function';
}
function floatingNotice(message = '') {
  text('float-note', message);
  el('float-note').hidden = !message;
}
const FLOAT_UNAVAILABLE = 'Floating is unavailable in this host.';
function requestAutomaticFloat() {
  if (!visibleConnected() || !state.haveOpenResult || state.taskClosed || state.availability ||
      state.selectionLost || state.setupProblem || !sourceId(state.sessionId) ||
      state.autoFloatAttempted || state.floatPending) return;
  if (state.mode === 'pip') { state.autoFloatAttempted = true; floatingNotice(); return; }
  if (!state.modes.includes('pip')) {
    floatingNotice(canFloatInHost() ? 'Choose Float to request a floating view.' : FLOAT_UNAVAILABLE);
    return;
  }
  state.autoFloatAttempted = true;
  void requestMode('pip');
}
function hostContextChanged(context = {}) {
  if (state.disposed) return;
  const current = app.getHostContext() || context;
  if (current.theme) document.documentElement.dataset.theme = current.theme;
  if (Array.isArray(current.availableDisplayModes)) state.modes = current.availableDisplayModes;
  if (current.displayMode) state.mode = current.displayMode;
  if (state.presentationBridge === 'openai' && ['inline','fullscreen','pip'].includes(window.openai?.displayMode)) {
    state.mode = window.openai.displayMode;
    text('mode-note', '');
  }
  if (state.mode === 'pip') floatingNotice();
  applyLayout();
  requestAutomaticFloat();
}
async function requestMode(mode) {
  if (!state.connected || state.disposed || (!state.modes.includes(mode) && !(mode === 'pip' && canFloatInHost()))) return;
  const request = ++state.modeRequest;
  const currentRequest = () => !state.disposed && request === state.modeRequest;
  const legacy = typeof window.openai?.requestDisplayMode === 'function' &&
    (state.presentationBridge === 'openai' || (mode === 'pip' && !state.modes.includes('pip')));
  if (legacy) state.presentationBridge = 'openai';
  if (mode === 'pip') { state.autoFloatAttempted = true; state.floatPending = true; floatingNotice(); applyLayout(); }
  async function change(requested) {
    let timeout;
    try {
      // Request only an in-host presentation; never create an OS window.
      return legacy ? await Promise.race([
        window.openai.requestDisplayMode({mode: requested}),
        new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('Host timeout')), 10000); }),
      ]) : await app.requestDisplayMode({mode: requested}, {timeout: 10000});
    } finally { clearTimeout(timeout); }
  }
  const actualMode = result => result?.mode || (legacy ? window.openai?.displayMode : null);
  try {
    let actual = actualMode(await change(mode));
    if (!currentRequest()) return;
    if (!['inline','fullscreen','pip'].includes(actual)) {
      if (mode === 'pip') floatingNotice(FLOAT_UNAVAILABLE);
      else text('mode-note', 'The app did not confirm the display mode.');
      return;
    }
    state.presentationBridge = legacy ? 'openai' : 'mcp';
    if (mode === 'pip' && actual !== 'pip') {
      floatingNotice(FLOAT_UNAVAILABLE);
      if (actual === 'fullscreen') {
        // A fullscreen substitution is never accepted as floating. Ask once
        // to return inline, without a retry loop if the host refuses that too.
        const restored = actualMode(await change('inline'));
        if (!currentRequest()) return;
        if (['inline','fullscreen','pip'].includes(restored)) actual = restored;
        if (actual !== 'inline') floatingNotice('Floating is unavailable. This host did not return inline.');
      }
    } else {
      if (mode === 'pip') floatingNotice();
      text('mode-note', mode === actual ? '' : 'The app kept its current display mode.');
    }
    state.mode = actual;
    applyLayout();
  } catch {
    if (currentRequest()) {
      if (mode === 'pip') floatingNotice(FLOAT_UNAVAILABLE);
      else text('mode-note', 'The app could not change the display mode.');
    }
  } finally {
    if (mode === 'pip' && request === state.modeRequest) state.floatPending = false;
    if (currentRequest()) { applyLayout(); requestAutomaticFloat(); }
  }
}
function dispose() {
  state.disposed = true; state.generation += 1; state.modeRequest += 1; stopPolling(); interruptRecovery();
  clearFrame();
  // A discarded viewer never changes its source or the worker.
}
app.ontoolinput = ({arguments: args}) => {
  if (state.disposed || !sourceId(args?.session_id)) return;
  if (args.job_id !== undefined && !jobId(args.job_id)) return;
  if (state.sessionId) {
    if (args.session_id === state.sessionId) {
      state.openPresentationRequested = true;
      if (args.job_id && (!state.taskJobId || state.taskClosed)) {
        state.taskJobId=args.job_id;
        state.taskClosed=false;
      }
    }
    return;
  }
  state.sessionId = args.session_id;
  state.taskJobId = args.job_id || null;
  if (state.pendingOpen) state.pendingOpen.sessionId ||= state.sessionId;
  // Some hosts deliver source input after the unbound result. Recover only
  // that explicit source; never select a worker's last-used session.
  if (state.unboundResultReceived) schedule(0);
  requestAutomaticFloat();
};
app.ontoolresult = result => {
  if (state.disposed || (state.connected && !state.bridgeReady)) return;
  try {
    const wasOpen = state.haveOpenResult;
    const data = dataOf(result);
    const metaId = result?._meta?.['rdc/operation_id'];
    if (operationId(data.operation_id) && operationId(metaId) && data.operation_id !== metaId) {
      throw new Error('The preview recovery response could not be verified.');
    }
    const id = operationId(data.operation_id) ? data.operation_id : operationId(metaId) ? metaId : null;
    if (id && state.retiredOpens.has(id)) return;
    const pending = pendingFrom(result);
    if (pending) {
      if (state.pendingOpen && state.pendingOpen.operation_id !== pending.operation_id) return;
      if (!state.pendingOpen) state.pendingOpen = {...pending, sessionId:state.sessionId};
    } else if (refreshRequired(result, state.pendingOpen, 'rdc_preview_open') ||
               expiredObservation(previewError(data), {operation_id:id})) {
      if (state.pendingOpen && state.pendingOpen.operation_id !== id) return;
      state.pendingOpen ||= {operation_id:id,sessionId:state.sessionId,deadline:performance.now()+120000,replacements:0};
      state.pendingOpen.terminal = true; state.pendingOpen.halted = false;
    } else {
      if (state.pendingOpen && state.pendingOpen.operation_id !== id && !data.preview_unavailable) return;
      // An availability notification can supersede the paint while the
      // original request remains available for explicit inspection.
      if (!data.preview_unavailable && state.pendingOpen) { state.pendingOpen = null; retireOpen(id); }
      acceptOpen(checkResult(result));
      if (!data.preview_unavailable && state.haveOpenResult && Array.isArray(data.sessions)) {
        const explicitOpen = state.openPresentationRequested;
        state.openPresentationRequested = false;
        if (state.hidden) { if (explicitOpen) reopenPreview(); }
        else {
          if (wasOpen) state.autoFloatAttempted = false;
          requestAutomaticFloat();
        }
      }
      if (id && !data.preview_unavailable) retireOpen(id);
    }
    schedule(0);
  } catch (error) {
    state.generation += 1;
    stopPolling(); interruptRecovery();
    if (state.pendingOpen) state.pendingOpen.halted = true;
    state.haveOpenResult = false;
    reportFailure(error);
  }
};
app.onhostcontextchanged = hostContextChanged;
window.addEventListener('openai:set_globals', () => hostContextChanged());
app.onteardown = async () => { dispose(); return {}; };
el('hide').addEventListener('click', hidePreview);
el('reopen').addEventListener('click', reopenPreview);
el('dismiss').addEventListener('click', async () => {
  if (!state.connected || state.disposed) return;
  try { await retainSelection(); await app.requestTeardown(); }
  catch { text('closed-note', 'The app could not dismiss this view. Work keeps running.'); }
});
el('expand').addEventListener('click', () => requestMode('fullscreen'));
el('float').addEventListener('click', () => requestMode('pip'));
el('inline').addEventListener('click', () => requestMode('inline'));
el('preview-retry').addEventListener('click', retryPreview);
el('resize-retry').addEventListener('click', () => { state.resizeBlocked=false; void refreshFrame(true); });
el('connection-retry').addEventListener('click', () => connect());
el('frame').addEventListener('load', updateCursor);
el('screen').addEventListener('scroll', updateCursor, {passive: true});
if (typeof ResizeObserver !== 'undefined') {
  const cursorResizeObserver = new ResizeObserver(updateCursor);
  cursorResizeObserver.observe(el('screen'));
  cursorResizeObserver.observe(el('frame'));
}
el('frame').addEventListener('error', () => {
  if (!visibleConnected() || !state.frame) return;
  stopPolling();
  captureProblem('screenshot_failed');
});
document.addEventListener('visibilitychange', () => {
  state.generation += 1;
  setBusy(state.busy);
  if (document.hidden) { stopPolling(); interruptRecovery(); }
  else schedule(0);
});
window.addEventListener('resize', updateCursor);
const onPaneResize = () => { if (visibleConnected() && state.resizeEnabled) schedule(350); };
if (typeof ResizeObserver !== 'undefined') new ResizeObserver(onPaneResize).observe(el('screen'));
else window.addEventListener('resize', onPaneResize);
window.addEventListener('pagehide', dispose, {once: true});
async function connect() {
  if (state.connecting || state.connected || state.disposed) return;
  if (window.parent === window) {
    empty('Open this preview inside your AI app', 'This live view requires an MCP Apps connection.');
    status('Host required');
    return;
  }
  state.connecting = true;
  el('connection-retry').disabled = true;
  try {
    await app.connect(new PostMessageTransport(window.parent, window.parent), {timeout: 15000});
    if (state.disposed) return;
    state.connected = true;
    el('connection-retry').hidden = true;
    hostContextChanged(app.getHostContext());
    state.bridgeReady = !!app.getHostCapabilities()?.serverTools;
    if (!state.bridgeReady) {
      empty('Preview unavailable', 'This app does not provide the live preview connection.');
      status('Preview unavailable', 'error');
      return;
    }
    setBusy(false);
    requestAutomaticFloat();
    // The host already invoked preview_open. Wait for its result.
    schedule(0);
  } catch {
    if (state.disposed) return;
    try { await app.close(); } catch {}
    state.connected = false; state.bridgeReady = false;
    stopPolling(); interruptRecovery();
    el('connection-retry').hidden = false;
    empty('The preview could not connect', 'Work keeps running independently of this view.');
    status('Connection unavailable', 'error');
  } finally {
    state.connecting = false;
    el('connection-retry').disabled = state.disposed;
  }
}
connect();
