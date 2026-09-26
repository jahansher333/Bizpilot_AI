import { OrganizationSetup } from "@/components/auth/organization-setup";

export default function OnboardingPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <OrganizationSetup />
    </main>
  );
}
