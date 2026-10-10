import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthProvider";
import { createIntervention, fetchIntervention, updateIntervention } from "../lib/api";
import type { InterventionPayload, InterventionResponse } from "../types";

export function useIntervention(employeeNumber: number | null) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = ["intervention", user?.id, employeeNumber];
  const query = useQuery({
    queryKey,
    queryFn: () => fetchIntervention(employeeNumber!),
    enabled: Boolean(user && employeeNumber),
    staleTime: 15_000,
  });
  const mutation = useMutation({
    mutationFn: async (payload: InterventionPayload) => {
      const existing = query.data?.case;
      const saved = existing
        ? await updateIntervention(existing.id, payload)
        : await createIntervention(payload);
      return saved;
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<InterventionResponse>(queryKey, (current) => ({
        case: saved,
        events: current?.events ?? [],
      }));
      void queryClient.invalidateQueries({ queryKey });
    },
  });
  return { ...query, save: mutation.mutateAsync, isSaving: mutation.isPending, saveError: mutation.error };
}
