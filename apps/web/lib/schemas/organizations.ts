import { z } from "zod";

export const CreateOrganizationSchema = z.object({
  display_name: z
    .string()
    .trim()
    .min(2, "Business name must be at least 2 characters")
    .max(255, "Business name cannot exceed 255 characters"),
  currency_code: z
    .string()
    .trim()
    .length(3, "Currency code must be 3 letters")
    .default("PKR"),
  timezone: z.string().trim().min(3).default("Asia/Karachi"),
});

export type CreateOrganizationInput = z.infer<typeof CreateOrganizationSchema>;

export interface Organization {
  id: string;
  display_name: string;
  currency_code: string;
  timezone: string;
  status: string;
  created_at: string;
  role: "owner" | "manager" | "staff" | string;
}

export const InviteMemberSchema = z.object({
  email: z.string().trim().email("Please enter a valid email address"),
  role: z.enum(["manager", "staff"], {
    message: "Role must be manager or staff",
  }),
});

export type InviteMemberInput = z.infer<typeof InviteMemberSchema>;

export type MemberRole = "owner" | "manager" | "staff";

export const MEMBER_ROLES: MemberRole[] = ["owner", "manager", "staff"];

export interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string;
  role: MemberRole;
  status: "active" | "invited" | "revoked" | string;
  invited_by_user_id?: string | null;
  created_at: string;
  updated_at?: string;
  revoked_at?: string | null;
  email: string;
  display_name: string;
}

export interface PendingInvitation {
  membership_id: string;
  organization_id: string;
  organization_display_name: string;
  role: MemberRole;
  invited_at: string;
}
