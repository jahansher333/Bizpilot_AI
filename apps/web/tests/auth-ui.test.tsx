import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider, useAuth } from "@/components/providers/auth-provider";
import { LoginForm } from "@/components/auth/login-form";
import { RegisterForm } from "@/components/auth/register-form";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { OrganizationSetup } from "@/components/auth/organization-setup";
import * as authApi from "@/lib/api/auth";
import * as orgApi from "@/lib/api/organizations";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: (key: string) => (key === "token" ? "valid-reset-token-32-chars-long-1234" : null),
  }),
}));

describe("Authentication & Organization UI (UX-001)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe("LoginForm", () => {
    it("renders email, password inputs, and submit button", () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <LoginForm />
          </AuthProvider>
        </QueryProvider>
      );

      expect(screen.getByRole("heading", { name: /sign in to bizpilot/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    });

    it("displays validation error when entering an invalid email", async () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <LoginForm />
          </AuthProvider>
        </QueryProvider>
      );

      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "invalid-email" },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: "Secret12345678" },
      });
      fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

      expect(await screen.findByRole("alert")).toHaveTextContent(/valid email/i);
    });

    it("displays error message on invalid credentials", async () => {
      vi.spyOn(authApi, "loginUser").mockRejectedValueOnce(
        new authApi.ApiError(401, "Invalid email or password")
      );

      render(
        <QueryProvider>
          <AuthProvider>
            <LoginForm />
          </AuthProvider>
        </QueryProvider>
      );

      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "user@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: "WrongPassword123" },
      });
      fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

      expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
    });

    it("successfully logs in, saves session, and routes to workspace", async () => {
      vi.spyOn(authApi, "loginUser").mockResolvedValueOnce({
        access_token: "mock-jwt-access-token",
        refresh_token: "mock-refresh-token-32-chars-long",
        token_type: "bearer",
        expires_in: 900,
      });

      vi.spyOn(authApi, "getCurrentUser").mockResolvedValueOnce({
        id: "user-123",
        email: "founder@example.com",
        display_name: "Founder User",
        status: "active",
      });

      vi.spyOn(orgApi, "listOrganizations").mockResolvedValueOnce([
        {
          id: "org-456",
          display_name: "Alpha Traders",
          currency_code: "PKR",
          timezone: "Asia/Karachi",
          status: "active",
          created_at: "2026-09-20T10:00:00Z",
          role: "owner",
        },
      ]);

      render(
        <QueryProvider>
          <AuthProvider>
            <LoginForm />
          </AuthProvider>
        </QueryProvider>
      );

      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "founder@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: "ValidPassword123" },
      });
      fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/workspace/org-456");
      });
      expect(localStorage.getItem("bizpilot_refresh_token")).toBe(
        "mock-refresh-token-32-chars-long"
      );
    });
  });

  describe("RegisterForm", () => {
    it("renders registration inputs and enforces 12-character minimum password policy", async () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <RegisterForm />
          </AuthProvider>
        </QueryProvider>
      );

      expect(screen.getByRole("heading", { name: /create your account/i })).toBeInTheDocument();

      fireEvent.change(screen.getByLabelText(/full name/i), {
        target: { value: "Bilal Khan" },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "bilal@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: "shortpwd" },
      });
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        /at least 12 characters/i
      );
    });

    it("submits valid registration and shows confirmation message", async () => {
      vi.spyOn(authApi, "registerUser").mockResolvedValueOnce({
        message: "Registration request accepted. Please proceed to login.",
      });

      render(
        <QueryProvider>
          <AuthProvider>
            <RegisterForm />
          </AuthProvider>
        </QueryProvider>
      );

      fireEvent.change(screen.getByLabelText(/full name/i), {
        target: { value: "Bilal Khan" },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "bilal@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: "SecurePassword123!" },
      });
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));

      expect(await screen.findByRole("status")).toHaveTextContent(
        "Registration request accepted. Please proceed to login."
      );
    });
  });

  describe("ForgotPasswordForm & ResetPasswordForm", () => {
    it("submits password recovery request and displays uniform non-enumerating message", async () => {
      vi.spyOn(authApi, "forgotPasswordRequest").mockResolvedValueOnce({
        status: "success",
        message:
          "If an eligible account exists for this email, password recovery instructions have been sent.",
      });

      render(
        <QueryProvider>
          <AuthProvider>
            <ForgotPasswordForm />
          </AuthProvider>
        </QueryProvider>
      );

      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "recovery@example.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /send recovery link/i }));

      expect(await screen.findByRole("status")).toHaveTextContent(
        "If an eligible account exists for this email, password recovery instructions have been sent."
      );
    });

    it("resets password with token and enforces password policy", async () => {
      vi.spyOn(authApi, "resetPasswordSubmit").mockResolvedValueOnce({
        status: "success",
        message: "Password reset successfully. Please log in with your new password.",
      });

      render(
        <QueryProvider>
          <AuthProvider>
            <ResetPasswordForm />
          </AuthProvider>
        </QueryProvider>
      );

      expect(screen.getByLabelText(/reset token/i)).toHaveValue(
        "valid-reset-token-32-chars-long-1234"
      );

      fireEvent.change(screen.getByLabelText(/new password/i), {
        target: { value: "BrandNewPassword123!" },
      });
      fireEvent.click(screen.getByRole("button", { name: /update password/i }));

      expect(await screen.findByRole("status")).toHaveTextContent(
        "Password reset successfully. Please log in with your new password."
      );
    });
  });

  describe("OrganizationSetup", () => {
    it("renders existing organizations and permits selection", async () => {
      const mockSelect = vi.fn();

      function SetupWithMockAuth() {
        const { selectOrg } = useAuth();
        return (
          <OrganizationSetup
            onOrgSelected={(org) => {
              selectOrg(org.id);
              mockSelect(org.id);
            }}
          />
        );
      }

      localStorage.setItem("bizpilot_refresh_token", "mock-token");
      vi.spyOn(authApi, "refreshSessionToken").mockResolvedValueOnce({
        access_token: "mock-access-token",
        refresh_token: "mock-refresh-token",
        token_type: "bearer",
        expires_in: 900,
      });
      vi.spyOn(authApi, "getCurrentUser").mockResolvedValueOnce({
        id: "user-1",
        email: "test@example.com",
        display_name: "Test User",
        status: "active",
      });
      vi.spyOn(orgApi, "listOrganizations").mockResolvedValueOnce([
        {
          id: "org-existing-1",
          display_name: "Karachi Store",
          currency_code: "PKR",
          timezone: "Asia/Karachi",
          status: "active",
          created_at: "2026-09-20T10:00:00Z",
          role: "owner",
        },
      ]);

      render(
        <QueryProvider>
          <AuthProvider>
            <SetupWithMockAuth />
          </AuthProvider>
        </QueryProvider>
      );

      expect(await screen.findByText("Karachi Store")).toBeInTheDocument();
      expect(screen.getByText("owner")).toBeInTheDocument();

      const enterBtn = screen.getByRole("button", { name: /enter workspace/i });
      fireEvent.click(enterBtn);

      expect(mockSelect).toHaveBeenCalledWith("org-existing-1");
    });

    it("creates a new workspace with PKR and Asia/Karachi defaults", async () => {
      const mockCreatedOrg = {
        id: "org-new-999",
        display_name: "Lahore Depot",
        currency_code: "PKR",
        timezone: "Asia/Karachi",
        status: "active",
        created_at: "2026-09-27T00:00:00Z",
        role: "owner",
      };

      vi.spyOn(orgApi, "createOrganization").mockResolvedValueOnce(mockCreatedOrg);

      localStorage.setItem("bizpilot_refresh_token", "mock-token");
      vi.spyOn(authApi, "refreshSessionToken").mockResolvedValueOnce({
        access_token: "mock-access-token",
        refresh_token: "mock-refresh-token",
        token_type: "bearer",
        expires_in: 900,
      });
      vi.spyOn(authApi, "getCurrentUser").mockResolvedValueOnce({
        id: "user-1",
        email: "test@example.com",
        display_name: "Test User",
        status: "active",
      });
      vi.spyOn(orgApi, "listOrganizations").mockResolvedValueOnce([]);

      render(
        <QueryProvider>
          <AuthProvider>
            <OrganizationSetup />
          </AuthProvider>
        </QueryProvider>
      );

      const nameInput = await screen.findByLabelText(/business name/i);
      fireEvent.change(nameInput, { target: { value: "Lahore Depot" } });

      const createBtn = screen.getByRole("button", { name: /create workspace/i });
      fireEvent.click(createBtn);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/workspace/org-new-999");
      });
    });
  });
});
