/**
 * React Query hooks for all API endpoints.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CreatePlanData, CreateTermsData, UpdateTermsData, RiskSettingsUpdate, PublicSettings } from "@/lib/api";
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
export function usePlans() {
  return useQuery({
    queryKey: ["plans"],
    queryFn: () => api.listPlans(),
  });
}

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

export function useUpgradeEligibility() {
  return useQuery({
    queryKey: ["upgrade-eligibility"],
    queryFn: () => api.checkUpgradeEligibility(),
    refetchInterval: 60000,
  });
}

export function useRequestUpgrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (targetPlanId: string) => api.requestUpgrade(targetPlanId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["upgrade-eligibility"] });
      qc.invalidateQueries({ queryKey: ["my-upgrade-requests"] });
      toast.success("Upgrade request submitted!");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useMyUpgradeRequests() {
  return useQuery({
    queryKey: ["my-upgrade-requests"],
    queryFn: () => api.myUpgradeRequests(),
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

// ── Admin Plans ─────────────────────────────────────
export function useAdminPlans() {
  return useQuery({
    queryKey: ["admin-plans"],
    queryFn: () => api.adminListPlans(),
  });
}

export function useAdminCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePlanData) => api.adminCreatePlan(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-plans"] });
      toast.success("Plan created");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminUpdatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { planId: string; updates: Partial<CreatePlanData> }) =>
      api.adminUpdatePlan(data.planId, data.updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-plans"] });
      toast.success("Plan updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminDeletePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => api.adminDeletePlan(planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-plans"] });
      toast.success("Plan deleted");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminChangeUserPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { userId: string; planId: string }) =>
      api.adminChangeUserPlan(data.userId, data.planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User plan changed");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

// ── Admin Subscriptions & Invoices ──────────────────
export function useAdminSubscriptions(status?: string) {
  return useQuery({
    queryKey: ["admin-subscriptions", status],
    queryFn: () => api.adminListSubscriptions(status),
  });
}

export function useAdminInvoices(status?: string) {
  return useQuery({
    queryKey: ["admin-invoices", status],
    queryFn: () => api.adminListInvoices(status),
  });
}

// ── Admin Upgrade Requests ─────────────────────────
export function useAdminUpgradeRequests(status?: string) {
  return useQuery({
    queryKey: ["admin-upgrade-requests", status],
    queryFn: () => api.adminListUpgradeRequests(status),
  });
}

export function useAdminHandleUpgradeRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { requestId: string; action: "approve" | "reject"; note?: string }) =>
      api.adminHandleUpgradeRequest(data.requestId, data.action, data.note),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["admin-upgrade-requests"] });
      toast.success(data.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

// ── Admin Terms ────────────────────────────────────────
export function useAdminTerms() {
  return useQuery({
    queryKey: ["admin-terms"],
    queryFn: () => api.adminListTerms(),
  });
}

export function useAdminCreateTerms() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateTermsData) => api.adminCreateTerms(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-terms"] });
      toast.success("Terms created");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminUpdateTerms() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { termsId: string; updates: UpdateTermsData }) =>
      api.adminUpdateTerms(data.termsId, data.updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-terms"] });
      toast.success("Terms updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminActivateTerms() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (termsId: string) => api.adminActivateTerms(termsId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-terms"] });
      toast.success("Terms activated");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

// ── Admin Risk Protection ──────────────────────────
export function useAdminRiskSettings() {
  return useQuery({
    queryKey: ["admin-risk-settings"],
    queryFn: () => api.adminGetRiskSettings(),
  });
}

export function useAdminRiskStatus() {
  return useQuery({
    queryKey: ["admin-risk-status"],
    queryFn: () => api.adminGetRiskStatus(),
    refetchInterval: 5000,
  });
}

export function useAdminRiskIncidents() {
  return useQuery({
    queryKey: ["admin-risk-incidents"],
    queryFn: () => api.adminGetRiskIncidents(),
  });
}

export function useAdminUpdateRiskSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RiskSettingsUpdate) => api.adminUpdateRiskSettings(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-risk-settings"] });
      qc.invalidateQueries({ queryKey: ["admin-risk-status"] });
      toast.success("Risk settings updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminResetEmergency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.adminResetEmergency(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-risk-status"] });
      qc.invalidateQueries({ queryKey: ["admin-risk-settings"] });
      toast.success("Emergency state reset — trading re-enabled");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

// ── Admin Operations ───────────────────────────────
export function useAdminOperations() {
  return useQuery({
    queryKey: ["admin-operations"],
    queryFn: () => api.adminGetOperations(),
    refetchInterval: 10000,
  });
}

// ── Admin Dead Letter Queue ────────────────────────
export function useAdminDeadLetterTrades(status?: string) {
  return useQuery({
    queryKey: ["admin-dead-letter", status],
    queryFn: () => api.adminGetDeadLetterTrades(status),
    refetchInterval: 15000,
  });
}

export function useAdminRetryDeadLetter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tradeId: string) => api.adminRetryDeadLetter(tradeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-dead-letter"] });
      qc.invalidateQueries({ queryKey: ["admin-operations"] });
      toast.success("Trade re-enqueued for execution");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAdminResolveDeadLetter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { tradeId: string; note: string }) =>
      api.adminResolveDeadLetter(data.tradeId, data.note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-dead-letter"] });
      qc.invalidateQueries({ queryKey: ["admin-operations"] });
      toast.success("Trade marked as resolved");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}
