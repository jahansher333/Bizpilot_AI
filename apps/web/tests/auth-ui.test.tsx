import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider } from "@/components/providers/auth-provider";
import { LoginForm } from "@/components/auth/login-form";
import { RegisterForm } from "@/components/auth/register-form";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { OrganizationSetup } from "@/components/auth/organization-setup";
import { WorkspaceChooser } from "@/components/auth/workspace-chooser";
import * as httpApi from "@/lib/api/http";
import * as authApi from "@/lib/api/auth";
import * as orgApi from "@/lib/api/organizations";

const mockPush = vi.fn();
const mockReplace = vi.fn();
let resetToken: string | null = "valid-reset-token-32-chars-long-1234";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  usePathname: () => "/",
  useSearchParams: () => ({
    get: (key: string) => (key === "token" ? resetToken : null),
  }),
}));

function renderWithAuth(ui: React.ReactElement) {
  return render(
    <QueryProvider>
      <AuthProvider>{ui}</AuthProvider>
    </QueryProvider>
  );
}

const ORG = {
  id: "org-456",
  display_name: "Alpha Traders",
  currency_code: "PKR",
  timezone: "Asia/Karachi",
  status: "active",
  created_at: "2026-09-20T10:00:00Z",
  role: "owner",
};

function mockSignedInSession(orgs: (typeof ORG)[]) {
  localStorage.setItem("bizpilot_session", "1");
  vi.spyOn(httpApi, "refreshSession").mockResolvedValueOnce({ status: "ok", accessToken: "mock-access-token" });
  vi.spyOn(authApi, "getCurrentUser").mockResolvedValueOnce({
    id: "user-1",
    email: "asad@khantraders.pk",
    display_name: "Asad Khan",
    status: "active",
  });
  vi.spyOn(orgApi, "listOrganizations").mockResolvedValueOnce(orgs);
}

describe("Authentication & Organization UI (R2 design)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    localStorage.clear();
    resetToken = "valid-reset-token-32-chars-long-1234";
  });

  describe("LoginForm", () => {
    it("renders the design sign-in screen", () => {
      renderWithAuth(<LoginForm />);
      expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^sign in$/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /forgot password/i })).toHaveAttribute("href", "/forgot-password");
    });

    it("toggles password visibility", () => {
      renderWithAuth(<LoginForm />);
      const pw = screen.getByLabelText(/^password$/i);
      expect(pw).toHaveAttribute("type", "password");
      fireEvent.click(screen.getByRole("button", { name: /show password/i }));
      expect(pw).toHaveAttribute("type", "text");
    });

    it("shows a validation error for an invalid email", async () => {
      renderWithAuth(<LoginForm />);
      fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "invalid-email" } });
      fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "Secret12345678" } });
      fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/valid email/i);
    });

    it("shows the server message on invalid credentials and marks fields invalid", async () => {
      vi.spyOn(authApi, "loginUser").mockRejectedValueOnce(new authApi.ApiError(401, "Invalid email or password"));
      renderWithAuth(<LoginForm />);
      fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "user@example.com" } });
      fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "WrongPassword123" } });
      fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
      expect(screen.getByLabelText(/email address/i)).toHaveAttribute("aria-invalid", "true");
    });

    it("shows the session-expired notice", () => {
      renderWithAuth(<LoginForm sessionExpired />);
      expect(screen.getByRole("status")).toHaveTextContent(/session expired/i);
    });

    it("goes straight to the only workspace after sign-in", async () => {
      vi.spyOn(authApi, "loginUser").mockResolvedValueOnce({
        access_token: "mock-jwt-access-token",
        token_type: "bearer",
        expires_in: 900,
      });
      vi.spyOn(authApi, "getCurrentUser").mockResolvedValueOnce({ id: "user-123", email: "founder@example.com", display_name: "Founder User", status: "active" });
      vi.spyOn(orgApi, "listOrganizations").mockResolvedValueOnce([ORG]);

      renderWithAuth(<LoginForm />);
      fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "founder@example.com" } });
      fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "ValidPassword123" } });
      fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

      await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/workspace/org-456"));
      // The refresh token is an HttpOnly cookie; only the non-secret session hint is stored.
      expect(localStorage.getItem("bizpilot_session")).toBe("1");
      expect(JSON.stringify({ ...localStorage })).not.toContain("mock-jwt-access-token");
    });

    it("opens the workspace chooser when the user has several workspaces", async () => {
      vi.spyOn(authApi, "loginUser").mockResolvedValueOnce({ access_token: "a", token_type: "bearer", expires_in: 900 });
      vi.spyOn(authApi, "getCurrentUser").mockResolvedValueOnce({ id: "u", email: "a@b.pk", display_name: "A", status: "active" });
      vi.spyOn(orgApi, "listOrganizations").mockResolvedValueOnce([ORG, { ...ORG, id: "org-2", display_name: "Second" }]);

      renderWithAuth(<LoginForm />);
      fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "a@b.pk" } });
      fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "ValidPassword123" } });
      fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
      await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/workspaces"));
    });
  });

  describe("RegisterForm", () => {
    function fill(password: string, confirm = password) {
      fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Bilal Khan" } });
      fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "bilal@example.com" } });
      fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: password } });
      fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: confirm } });
    }

    it("enforces the 12-character backend minimum", async () => {
      renderWithAuth(<RegisterForm />);
      expect(screen.getByRole("heading", { name: /create your account/i })).toBeInTheDocument();
      fill("shortpwd");
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/at least 12 characters/i);
    });

    it("shows live password checks and a mismatch error", () => {
      renderWithAuth(<RegisterForm />);
      fill("karachi-ledger-7", "karachi-led");
      expect(screen.getByText("At least 12 characters").closest("li")).toHaveTextContent("(met)");
      expect(screen.getByText(/passwords don’t match yet/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toHaveAttribute("aria-invalid", "true");
    });

    it("registers, signs in and opens onboarding for a new account", async () => {
      vi.spyOn(authApi, "registerUser").mockResolvedValueOnce({ message: "Registration request accepted. Please proceed to login." });
      vi.spyOn(authApi, "loginUser").mockResolvedValueOnce({ access_token: "a", token_type: "bearer", expires_in: 900 });
      vi.spyOn(authApi, "getCurrentUser").mockResolvedValueOnce({ id: "u", email: "bilal@example.com", display_name: "Bilal Khan", status: "active" });
      vi.spyOn(orgApi, "listOrganizations").mockResolvedValueOnce([]);

      renderWithAuth(<RegisterForm />);
      fill("karachi-ledger-7");
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
      await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/onboarding"));
    });

    it("stays non-enumerating when the follow-up sign-in fails", async () => {
      vi.spyOn(authApi, "registerUser").mockResolvedValueOnce({ message: "Registration request accepted. Please proceed to login." });
      vi.spyOn(authApi, "loginUser").mockRejectedValueOnce(new authApi.ApiError(401, "Invalid email or password"));

      renderWithAuth(<RegisterForm />);
      fill("karachi-ledger-7");
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
      expect(await screen.findByRole("status")).toHaveTextContent(/if this email is new, your account is ready/i);
      expect(mockPush).not.toHaveBeenCalled();
    });
  });

  describe("ForgotPasswordForm & ResetPasswordForm", () => {
    it("shows the same confirmation for any email", async () => {
      vi.spyOn(authApi, "forgotPasswordRequest").mockResolvedValueOnce({ status: "success", message: "ok" });
      renderWithAuth(<ForgotPasswordForm />);
      fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "recovery@example.com" } });
      fireEvent.click(screen.getByRole("button", { name: /send recovery link/i }));
      const status = await screen.findByRole("status");
      expect(status).toHaveTextContent(/if an account exists for recovery@example.com/i);
      expect(screen.getByRole("button", { name: /resend in/i })).toBeDisabled();
    });

    it("keeps the email and offers retry when the request fails", async () => {
      vi.spyOn(authApi, "forgotPasswordRequest").mockRejectedValueOnce(new Error("network"));
      renderWithAuth(<ForgotPasswordForm />);
      fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "recovery@example.com" } });
      fireEvent.click(screen.getByRole("button", { name: /send recovery link/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/couldn’t send that request/i);
      expect(screen.getByLabelText(/email address/i)).toHaveValue("recovery@example.com");
      expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    });

    it("updates the password using the token from the link", async () => {
      const submit = vi.spyOn(authApi, "resetPasswordSubmit").mockResolvedValueOnce({ status: "success", message: "ok" });
      renderWithAuth(<ResetPasswordForm />);
      expect(screen.queryByLabelText(/reset token/i)).not.toBeInTheDocument();
      fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "BrandNewPassword123!" } });
      fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "BrandNewPassword123!" } });
      fireEvent.click(screen.getByRole("button", { name: /update password/i }));
      expect(await screen.findByRole("status")).toHaveTextContent(/password updated/i);
      expect(submit).toHaveBeenCalledWith({ token: "valid-reset-token-32-chars-long-1234", new_password: "BrandNewPassword123!" });
    });

    it("shows the expired-link state when the token is rejected", async () => {
      vi.spyOn(authApi, "resetPasswordSubmit").mockRejectedValueOnce(new authApi.ApiError(401, "Invalid or expired password reset token"));
      renderWithAuth(<ResetPasswordForm />);
      fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "BrandNewPassword123!" } });
      fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "BrandNewPassword123!" } });
      fireEvent.click(screen.getByRole("button", { name: /update password/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/this link has expired/i);
      expect(screen.getByRole("link", { name: /request a new link/i })).toHaveAttribute("href", "/forgot-password");
    });

    it("asks for the token when the page is opened without one", () => {
      resetToken = null;
      renderWithAuth(<ResetPasswordForm />);
      expect(screen.getByLabelText(/reset token/i)).toBeInTheDocument();
    });
  });

  describe("OrganizationSetup wizard", () => {
    it("walks through the steps and creates a PKR / Asia/Karachi workspace", async () => {
      mockSignedInSession([]);
      const create = vi.spyOn(orgApi, "createOrganization").mockResolvedValueOnce({ ...ORG, id: "org-new-999", display_name: "Lahore Depot" });

      renderWithAuth(<OrganizationSetup />);
      expect(await screen.findByRole("heading", { name: /welcome to bizpilot, asad/i })).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: /get started/i }));

      fireEvent.click(screen.getByRole("button", { name: /continue/i }));
      expect(await screen.findByText(/enter a business name to continue/i)).toBeInTheDocument();

      fireEvent.change(screen.getByLabelText(/business name/i), { target: { value: "Lahore Depot" } });
      fireEvent.click(screen.getByRole("button", { name: /continue/i }));
      expect(screen.getByRole("heading", { name: /currency and time zone/i })).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /create workspace/i }));
      expect(await screen.findByRole("heading", { name: /lahore depot is ready/i })).toBeInTheDocument();
      expect(create).toHaveBeenCalledWith({ display_name: "Lahore Depot", currency_code: "PKR", timezone: "Asia/Karachi" }, "mock-access-token");
      expect(screen.getByRole("link", { name: /go to dashboard/i })).toHaveAttribute("href", "/workspace/org-new-999");
    });
  });

  describe("WorkspaceChooser", () => {
    it("lists workspaces with roles and a create option", async () => {
      vi.spyOn(orgApi, "listMyInvitations").mockResolvedValue([]);
      mockSignedInSession([ORG, { ...ORG, id: "org-2", display_name: "Raza Cloth House", role: "staff" }]);

      renderWithAuth(<WorkspaceChooser />);
      expect(await screen.findByText("Alpha Traders")).toBeInTheDocument();
      expect(screen.getByText(/you have access to 2 businesses/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /open workspace raza cloth house/i })).toHaveAttribute("href", "/workspace/org-2");
      expect(screen.getByRole("link", { name: /create new organization/i })).toHaveAttribute("href", "/onboarding");
    });

    it("sends signed-out visitors to login", async () => {
      renderWithAuth(<WorkspaceChooser />);
      await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
    });
  });
});
