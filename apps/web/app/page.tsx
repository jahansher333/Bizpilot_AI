import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-8 lg:px-12">
      <section
        aria-labelledby="workspace-title"
        className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-6xl flex-col rounded-2xl border border-slate-200 bg-white shadow-sm"
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4 sm:px-8">
          <div>
            <p className="text-sm font-semibold text-emerald-700">BizPilot AI</p>
            <h1 id="workspace-title" className="mt-1 text-2xl font-bold text-slate-950">
              Business workspace
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-lg border border-slate-300 px-3.5 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-emerald-700 px-3.5 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800"
            >
              Sign up
            </Link>
          </div>
        </header>
        <div className="grid flex-1 place-items-center px-5 py-12 text-center">
          <div className="max-w-lg">
            <h2 className="text-xl font-semibold text-slate-900">
              Your authenticated workspace is being prepared
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
              Access your Pakistani SME operations copilot. Sign in or register to manage
              catalog, inventory, customers, orders, expenses, and AI operational insights.
            </p>
            <div className="mt-6 flex items-center justify-center gap-4">
              <Link
                href="/login"
                className="rounded-lg bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800"
              >
                Sign in to Workspace
              </Link>
              <Link
                href="/register"
                className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Create Account
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}