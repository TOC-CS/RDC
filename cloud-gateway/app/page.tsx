"use client";

import { useEffect, useState } from "react";

type Connection = { ok: boolean; online?: boolean; device_id?: string; last_seen_ms?: number | null;
  pending_operations?: number; error?: { code: string; message: string } };

export default function Home() {
  const [connection, setConnection] = useState<Connection | null>(null);
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const response = await fetch("/api/status", { cache: "no-store" });
        const next: Connection = await response.json();
        if (active) setConnection(next);
      } catch {
        if (active) setConnection({ ok: false, error: { code: "connection_unavailable", message: "The connection could not be checked. Try again shortly." } });
      }
    };
    void refresh();
    const timer = setInterval(() => void refresh(), 10_000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const online = connection?.ok && connection.online;
  return (
    <main className="min-h-screen bg-[#0b1322] px-6 py-12 text-slate-100 sm:py-20">
      <div className="mx-auto max-w-3xl">
        <header className="mb-12 flex items-center gap-4">
          <img src="/rdc-logo.png" alt="RDC" width={72} height={72} className="rounded-2xl" />
          <div><p className="text-sm font-medium tracking-[.18em] text-cyan-300">RDC</p><h1 className="text-2xl font-semibold">Your independent agent workspace</h1></div>
        </header>
        <section className="rounded-3xl border border-slate-700 bg-[#111e32] p-7 sm:p-10" aria-live="polite">
          <div className="mb-6 flex items-center gap-3"><span className={"h-3 w-3 rounded-full " + (online ? "bg-emerald-400" : "bg-amber-300")} /><h2 className="text-xl font-semibold">{connection === null ? "Checking connection" : online ? "Device connected" : connection.ok ? "Waiting for your device" : "Connection needs attention"}</h2></div>
          <p className="leading-relaxed text-slate-300">Open RDC from your AI conversation to control the paired workspace and see its live preview inside the app. Expanding or hiding that preview keeps active work running.</p>
          {connection?.error && <p className="mt-5 rounded-xl bg-amber-500/10 p-4 text-amber-100">{connection.error.message}</p>}
          {connection?.error?.code === "sign_in_required" && <a className="mt-5 inline-block rounded-xl bg-cyan-300 px-5 py-3 font-semibold text-slate-950" href="/signin-with-chatgpt?return_to=%2F" target="_top">Sign in with ChatGPT</a>}
          {connection?.ok && <dl className="mt-8 grid gap-5 border-t border-slate-700 pt-6 sm:grid-cols-2"><div><dt className="text-sm text-slate-400">Paired device</dt><dd className="mt-1 break-all font-mono text-sm">{connection.device_id}</dd></div><div><dt className="text-sm text-slate-400">Active relay operations</dt><dd className="mt-1">{connection.pending_operations ?? 0}</dd></div></dl>}
        </section>
        <section className="mt-10 grid gap-7 text-sm text-slate-300 sm:grid-cols-3">
          <div><h3 className="mb-2 font-semibold text-white">Inside your conversation</h3><p>The live view uses your AI app’s embedded preview controls.</p></div>
          <div><h3 className="mb-2 font-semibold text-white">Independent work</h3><p>The device worker owns browser sessions and background jobs.</p></div>
          <div><h3 className="mb-2 font-semibold text-white">Your device permissions</h3><p>File access, command execution, and approvals follow your local RDC configuration.</p></div>
        </section>
        <footer className="mt-14 border-t border-slate-800 pt-6 text-sm text-slate-500">RDC · Tribe of Christians · Free open-source agent tooling</footer>
      </div>
    </main>
  );
}
