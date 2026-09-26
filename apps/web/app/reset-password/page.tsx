import { Suspense } from "react";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";

export default function ResetPasswordPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <Suspense fallback={<div className="text-sm text-slate-500">Loading...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </main>
  );
}
