export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-8 lg:px-12">
      <section
        aria-labelledby="workspace-title"
        className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-6xl flex-col rounded-2xl border border-slate-200 bg-white shadow-sm"
      >
        <header className="border-b border-slate-200 px-5 py-4 sm:px-8">
          <p className="text-sm font-semibold text-emerald-700">BizPilot AI</p>
          <h1 id="workspace-title" className="mt-1 text-2xl font-bold text-slate-950">
            Business workspace
          </h1>
        </header>
        <div className="grid flex-1 place-items-center px-5 py-12 text-center">
          <div className="max-w-lg">
            <h2 className="text-xl font-semibold text-slate-900">
              Your authenticated workspace is being prepared
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
              Foundation setup is complete when the application shell can host approved
              product workflows. Authentication and business features arrive in later tasks.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}