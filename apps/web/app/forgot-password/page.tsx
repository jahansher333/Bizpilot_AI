import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";
import Link from "next/link";

export default function ForgotPasswordPage() {
  return (
    <div className="min-h-screen flex flex-col justify-between bg-surface font-body-md text-on-surface antialiased">
      {/* Header */}
      <header className="w-full max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between border-b border-surface-container-high/60 bg-surface/80 backdrop-blur-xl">
        <BizPilotLogo size="md" showText={true} />
        <Link href="/login" className="text-xs font-semibold text-on-surface-variant hover:text-primary transition-colors font-body-sm">
          Return to Sign in
        </Link>
      </header>

      {/* Main Form */}
      <main className="flex-1 flex flex-col items-center justify-center w-full px-4 sm:px-6 py-6">
        <ForgotPasswordForm />
      </main>

      {/* Footer */}
      <footer className="w-full max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-center text-xs text-outline border-t border-surface-container-high/60 font-body-sm">
        <span>BizPilot AI · Business records for Pakistani small businesses</span>
      </footer>
    </div>
  );
}
