import "./zod-config";
import { z } from "zod";

export const LoginSchema = z.object({
  email: z.string().trim().email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required").max(128, "Password is too long"),
});

export type LoginInput = z.infer<typeof LoginSchema>;

export const RegisterSchema = z.object({
  email: z.string().trim().email("Please enter a valid email address"),
  display_name: z.string().trim().min(1, "Display name is required").max(255),
  password: z
    .string()
    .min(12, "Password must be at least 12 characters")
    .max(128, "Password cannot exceed 128 characters"),
});

export type RegisterInput = z.infer<typeof RegisterSchema>;

export const ForgotPasswordSchema = z.object({
  email: z.string().trim().email("Please enter a valid email address"),
});

export type ForgotPasswordInput = z.infer<typeof ForgotPasswordSchema>;

export const ResetPasswordSchema = z.object({
  token: z.string().min(32, "Reset token must be at least 32 characters"),
  new_password: z
    .string()
    .min(12, "Password must be at least 12 characters")
    .max(128, "Password cannot exceed 128 characters"),
});

export type ResetPasswordInput = z.infer<typeof ResetPasswordSchema>;

/** Login/refresh body. The refresh token is an HttpOnly cookie and never reaches scripts. */
export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserMe {
  id: string;
  email: string;
  display_name: string;
  status: string;
}

export interface RegisterResponse {
  message: string;
}

export interface AuthMessageResponse {
  status: string;
  message: string;
}
