import { OrganizationSetup } from "@/components/auth/organization-setup";
import { PendingInvitations } from "@/components/team/pending-invitations";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

export default function OnboardingPage() {
  return (
    <div className="min-h-screen flex flex-col justify-between bg-surface font-body-md text-on-surface antialiased">
      {/* Top Navigation */}
      <header className="w-full max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between border-b border-surface-container-high/60 bg-surface/80 backdrop-blur-xl">
        <BizPilotLogo size="md" showText={true} />
      </header>

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center w-full px-4 sm:px-6 py-8">
        <PendingInvitations />
        <OrganizationSetup />
      </main>

      {/* Footer */}
      <footer className="w-full max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-center text-xs text-outline border-t border-surface-container-high/60 font-body-sm">
        <span>BizPilot AI · Business records for Pakistani small businesses</span>
      </footer>
    </div>
  );
}
