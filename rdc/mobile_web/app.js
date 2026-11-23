'use strict';
const status = document.getElementById('status');
const tokenInput = document.getElementById('token');
const check = document.getElementById('check');
const install = document.getElementById('install');
let installPrompt = null;
let active = null;
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  installPrompt = event;
  install.hidden = false;
});
install.addEventListener('click', async () => {
  if (!installPrompt) return;
  const prompt = installPrompt;
  installPrompt = null;
  install.hidden = true;
  try { await prompt.prompt(); } catch { /* Browser menu remains available. */ }
});
if (!window.isSecureContext) {
  document.getElementById('install-note').textContent = 'A trusted HTTPS connection is required on physical phones.';
  check.disabled = true;
}
if (window.isSecureContext && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/mobile/sw.js', {scope: '/mobile/'}).catch(() => {
    document.getElementById('install-note').textContent = 'Offline installation is unavailable. Use the browser menu or try again.';
  });
}
document.getElementById('status-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!window.isSecureContext || active) return;
  const token = tokenInput.value.trim();
  tokenInput.value = '';
  if (!/^[A-Za-z0-9_-]{40,1024}$/.test(token)) {
    status.textContent = 'Enter a valid read-only mobile status token.';
    return;
  }
  const controller = new AbortController();
  active = controller;
  check.disabled = true;
  status.textContent = 'Checking your gateway…';
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch('/mobile/status', {
      method: 'POST', headers: {Authorization: 'Bearer ' + token},
      credentials: 'omit', cache: 'no-store', redirect: 'error', signal: controller.signal
    });
    if (active !== controller) return;
    if (response.status === 401) { status.textContent = 'Status is disabled or the token is invalid.'; return; }
    if (!response.ok) throw new Error('unavailable');
    const data = await response.json();
    if (active !== controller) return;
    if (data.ok !== true || typeof data.online !== 'boolean' ||
        !Number.isSafeInteger(data.pending_operations) || data.pending_operations < 0) throw new Error('invalid');
    status.textContent = (data.online ? 'Paired host connected' : 'Paired host offline') +
      ' · ' + data.pending_operations + ' active operations.';
  } catch {
    if (active === controller) status.textContent = 'Connection unavailable. Check your gateway and try again.';
  } finally {
    clearTimeout(timeout);
    if (active === controller) { active = null; check.disabled = false; }
  }
});
document.getElementById('clear').addEventListener('click', () => {
  if (active) active.abort();
  active = null;
  tokenInput.value = '';
  status.textContent = 'Connection not checked.';
  check.disabled = !window.isSecureContext;
});
window.addEventListener('pagehide', () => {
  if (active) active.abort();
  active = null;
  tokenInput.value = '';
  status.textContent = 'Connection not checked.';
  check.disabled = !window.isSecureContext;
});
