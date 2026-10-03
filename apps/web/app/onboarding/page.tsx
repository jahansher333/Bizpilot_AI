import { OrganizationSetup } from "@/components/auth/organization-setup";
import { PendingInvitations } from "@/components/team/pending-invitations";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

export default function OnboardingPage() {
  return (
    <div className="min-h-screen flex flex-col justify-between bg-surface font-body-md text-on-surface antialiased">
      {/* Top Navigation */}
      <header className="w-full max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between border-b border-surface-container-high/60 bg-surface/80 backdrop-blur-xl">
        <BizPilotLogo size="md" showText={true} />
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-on-surface-variant font-label-md text-xs">
            <span className="material-symbols-outlined text-[16px] text-tertiary">verified_user</span>
            <span className="hidden sm:inline">SOC-2 Type II Certified</span>
          </div>
          <div className="h-4 w-px bg-outline-variant/40 hidden sm:block"></div>
          <div className="flex items-center gap-1 text-xs text-outline font-data-badge">
            <span className="w-2 h-2 rounded-full bg-tertiary"></span> Multi-Tenant RLS
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center w-full px-4 sm:px-6 py-8">
        <PendingInvitations />
        <OrganizationSetup />
      </main>

      {/* Footer */}
      <footer className="w-full max-w-[1600px] mx-auto px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-outline border-t border-surface-container-high/60 font-body-sm">
        <div className="flex items-center gap-2 font-data-badge text-[11px]">
          <span>STATE BANK OF PAKISTAN &amp; FBR COMPLIANT</span>
          <span>•</span>
          <span>POSTGRES RLS &amp; TENANT ENFORCEMENT</span>
        </div>
        <div>BizPilot AI Operational OS v2.4</div>
      </footer>
    </div>
  );
}
