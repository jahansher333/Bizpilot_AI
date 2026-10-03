import { LoginForm } from "@/components/auth/login-form";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex flex-col justify-between bg-surface font-body-md text-on-surface antialiased">
      {/* Top Navigation Bar */}
      <header className="w-full max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between border-b border-surface-container-high/60 bg-surface/80 backdrop-blur-xl">
        <BizPilotLogo size="md" showText={true} />
        <div className="flex items-center gap-4 text-xs font-semibold text-on-surface-variant">
          <Link
            href="/register"
            className="hover:text-primary transition-colors hidden sm:inline font-body-sm"
          >
            Create Account
          </Link>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col items-center justify-center w-full px-4 sm:px-6 py-6">
        <LoginForm />
      </main>

      {/* Footer */}
      <footer className="w-full max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-center text-xs text-outline border-t border-surface-container-high/60 font-body-sm">
        <span>BizPilot AI · Business records for Pakistani small businesses</span>
      </footer>
    </div>
  );
}
