import "./zod-config";
import { z } from "zod";

export const toolCallMetadataSchema = z.object({
  tool_name: z.string(),
  arguments: z.record(z.string(), z.any()).optional().default({}),
  latency_ms: z.number(),
  status: z.enum(["success", "denied", "error"]),
});

export type ToolCallMetadata = z.infer<typeof toolCallMetadataSchema>;

export const provenanceMetaSchema = z.object({
  source_tool: z.string(),
  period_applied: z.string().nullable().optional(),
  freshness_timestamp: z.string().optional(),
  calculation_method: z.string().default("deterministic_service"),
  caveats: z.array(z.string()).optional().default([]),
  source_refs: z.array(z.string()).optional().default([]),
});

export type ProvenanceMeta = z.infer<typeof provenanceMetaSchema>;

export const assistantMessageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
  created_at: z.string().optional(),
});

export type AssistantMessage = z.infer<typeof assistantMessageSchema>;

export const assistantRequestSchema = z.object({
  message: z.string().min(1).max(2000),
  conversation_history: z.array(assistantMessageSchema).default([]),
});

export type AssistantRequest = z.infer<typeof assistantRequestSchema>;

export const assistantResponseSchema = z.object({
  content: z.string(),
  tool_calls: z.array(toolCallMetadataSchema).default([]),
  provenance: z.array(provenanceMetaSchema).default([]),
  model: z.string(),
  latency_ms: z.number(),
  trace_id: z.string().nullable().optional(),
  interaction_id: z.string().nullable().optional(),
});

export type AssistantResponse = z.infer<typeof assistantResponseSchema>;
