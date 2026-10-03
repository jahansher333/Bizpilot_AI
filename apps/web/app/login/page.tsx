"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { LoginForm } from "@/components/auth/login-form";

function LoginPageContent() {
  const searchParams = useSearchParams();
  return <LoginForm sessionExpired={searchParams?.get("expired") === "1"} />;
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  );
}
