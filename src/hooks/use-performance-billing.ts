import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";

// ── Admin Performance Billing ────────────────────────
export function usePerformanceUsers() {
  return useQuery({
    queryKey: ["admin-performance-users"],
    queryFn: () => api.adminPerformanceGetUsers(),
  });
}

export function useSetPerformanceMethod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { user_id: string; method: string; performance_percentage: number }) =>
      api.adminPerformanceSetMethod(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-performance-users"] });
      toast.success("Billing method updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function usePerformanceCycles(userId?: string, status?: string) {
  return useQuery({
    queryKey: ["admin-performance-cycles", userId, status],
    queryFn: () => api.adminPerformanceListCycles(userId, status),
  });
}

export function useStartPerformanceCycle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.adminPerformanceStartCycle(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-performance-cycles"] });
      toast.success("Cycle started successfully");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useClosePerformanceCycle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cycleId: string) => api.adminPerformanceCloseCycle(cycleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-performance-cycles"] });
      qc.invalidateQueries({ queryKey: ["admin-performance-summary"] });
      toast.success("Cycle closed successfully");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useGeneratePerformanceInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cycleId: string) => api.adminPerformanceGenerateInvoice(cycleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-performance-cycles"] });
      qc.invalidateQueries({ queryKey: ["admin-performance-summary"] });
      toast.success("Invoice generated successfully");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function usePerformanceSummary() {
  return useQuery({
    queryKey: ["admin-performance-summary"],
    queryFn: () => api.adminPerformanceGetSummary(),
  });
}
