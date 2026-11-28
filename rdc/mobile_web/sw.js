'use strict';
const CACHE = 'rdc-mobile-shell-v1';
const SHELL = ['/mobile/', '/mobile/app.js', '/mobile/style.css', '/mobile/manifest.webmanifest', '/mobile/icon-192.png', '/mobile/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key.startsWith('rdc-mobile-shell-') && key !== CACHE)
    .map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin ||
      url.search || !SHELL.includes(url.pathname)) return;
  event.respondWith(fetch(request).catch(() => caches.open(CACHE).then(cache => cache.match(request))));
});
