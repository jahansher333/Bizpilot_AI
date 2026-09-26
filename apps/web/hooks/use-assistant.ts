import { useMutation } from "@tanstack/react-query";
import { sendAssistantQuery } from "@/lib/api/assistant";
import { AssistantRequest, AssistantResponse } from "@/lib/schemas/assistant";

export function useAssistantQuery(orgId: string, token?: string) {
  return useMutation<AssistantResponse, Error, AssistantRequest>({
    mutationFn: (payload: AssistantRequest) => sendAssistantQuery(orgId, payload, token),
  });
}
