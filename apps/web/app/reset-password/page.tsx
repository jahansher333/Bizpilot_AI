import { Suspense } from "react";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";

export default function ResetPasswordPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-surface px-4 py-12 sm:px-6 lg:px-8 font-body-md text-on-surface antialiased">
      <Suspense fallback={<div className="text-sm text-on-surface-variant font-body-sm">Loading...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </main>
  );
}
