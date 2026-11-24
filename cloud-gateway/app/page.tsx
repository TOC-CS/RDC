export default function Home() {
  return (
    <main className="min-h-screen bg-[#0b1322] px-6 py-12 text-slate-100">
      <div className="mx-auto max-w-xl">
        <header className="mb-8 flex items-center gap-4">
          <img src="/rdc-logo.png" alt="RDC" width={64} height={64} className="rounded-xl" />
          <h1 className="text-2xl font-semibold">Remote Desktop Commander</h1>
        </header>
        <p className="leading-relaxed text-slate-300">
          RDC runs independently through its connected MCP worker. Use your compatible AI conversation to operate the authorized workspace and open an optional live preview.
        </p>
        <a className="mt-6 inline-block rounded-lg border border-slate-600 px-4 py-2" href="/signin-with-chatgpt?return_to=%2F">Connect with ChatGPT</a>
      </div>
    </main>
  );
}
