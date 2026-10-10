import { useQuery } from "@tanstack/react-query";
import { fetchDashboard } from "../lib/api";
import { useAuth } from "../auth/AuthProvider";

export function useDashboard() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["dashboard", user?.id],
    queryFn: fetchDashboard,
    enabled: Boolean(user),
    staleTime: 60_000,
    retry: 2,
  });
}
