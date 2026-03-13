/**
 * React Query hooks for all API endpoints.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";

// ── MT5 Accounts ────────────────────────────────────
export function useMT5Accounts() {
  return useQuery({
    queryKey: ["mt5-accounts"],
    queryFn: () => api.listMT5Accounts(),
  });
}

export function useConnectMT5() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { login: number; password: string; server: string }) =>
      api.connectMT5(data.login, data.password, data.server),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mt5-accounts"] });
      toast.success("MT5 account connected successfully!");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useDisconnectMT5() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) => api.disconnectMT5(accountId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mt5-accounts"] });
      toast.success("MT5 account disconnected");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

// ── Strategies ──────────────────────────────────────
export function useStrategies() {
  return useQuery({
    queryKey: ["strategies"],
    queryFn: () => api.listStrategies(),
  });
}

export function useSelectStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (strategyId: string) => api.selectStrategy(strategyId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["strategies"] });
      toast.success(data.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

// ── Billing ─────────────────────────────────────────
export function useSubscription() {
  return useQuery({
    queryKey: ["subscription"],
    queryFn: () => api.getSubscription(),
  });
}

export function useInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: () => api.listInvoices(),
  });
}

// ── Admin ───────────────────────────────────────────
export function useAdminUsers(search: string) {
  return useQuery({
    queryKey: ["admin-users", search],
    queryFn: () => api.adminSearchUsers(search),
  });
}

export function useAdminDashboard() {
  return useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => api.adminGetDashboard(),
  });
}

export function useAdminCheckPayments() {
  return useMutation({
    mutationFn: () => api.adminCheckPayments(),
    onSuccess: () => toast.success("Payment check dispatched"),
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminUnblockUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.adminUnblockUser(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User unblocked");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminUnlockStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { userId: string; strategyId: string }) =>
      api.adminUnlockStrategy(data.userId, data.strategyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("Strategy unlocked");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { currentPassword: string; newPassword: string }) =>
      api.changePassword(data.currentPassword, data.newPassword),
    onSuccess: () => toast.success("Password updated successfully"),
    onError: (err: Error) => toast.error(err.message),
  });
}
