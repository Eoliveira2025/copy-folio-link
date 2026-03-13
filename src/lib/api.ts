/**
 * API client for CopyTrade Pro backend.
 * Handles JWT token management and request/response formatting.
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.accessToken = localStorage.getItem("access_token");
    this.refreshToken = localStorage.getItem("refresh_token");
  }

  setTokens(access: string, refresh: string) {
    this.accessToken = access;
    this.refreshToken = refresh;
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  }

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  getAccessToken() {
    return this.accessToken;
  }

  isAuthenticated() {
    return !!this.accessToken;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401 && this.refreshToken) {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        headers["Authorization"] = `Bearer ${this.accessToken}`;
        const retryResponse = await fetch(`${API_BASE}${path}`, {
          ...options,
          headers,
        });
        if (!retryResponse.ok) {
          throw new ApiError(retryResponse.status, await retryResponse.text());
        }
        return retryResponse.json();
      }
      this.clearTokens();
      window.location.href = "/login";
      throw new ApiError(401, "Session expired");
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new ApiError(response.status, errorBody.detail || "Request failed");
    }

    if (response.status === 204) return undefined as T;
    return response.json();
  }

  private async tryRefresh(): Promise<boolean> {
    try {
      const res = await fetch(
        `${API_BASE}/auth/refresh?refresh_token=${this.refreshToken}`,
        { method: "POST" }
      );
      if (!res.ok) return false;
      const data = await res.json();
      this.setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  // ── Auth ──────────────────────────────────────────────
  async login(email: string, password: string) {
    const data = await this.request<{
      access_token: string;
      refresh_token: string;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setTokens(data.access_token, data.refresh_token);
    return data;
  }

  async register(email: string, password: string, confirmPassword: string) {
    const data = await this.request<{
      access_token: string;
      refresh_token: string;
    }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        confirm_password: confirmPassword,
      }),
    });
    this.setTokens(data.access_token, data.refresh_token);
    return data;
  }

  async forgotPassword(email: string) {
    return this.request<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  }

  async resetPassword(token: string, newPassword: string) {
    return this.request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    });
  }

  async changePassword(currentPassword: string, newPassword: string) {
    return this.request<{ message: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
  }

  async getMe() {
    return this.request<UserProfile>("/auth/me");
  }

  // ── MT5 Accounts ─────────────────────────────────────
  async connectMT5(login: number, password: string, server: string) {
    return this.request<MT5Account>("/mt5/connect", {
      method: "POST",
      body: JSON.stringify({ login, password, server }),
    });
  }

  async listMT5Accounts() {
    return this.request<MT5Account[]>("/mt5/accounts");
  }

  async disconnectMT5(accountId: string) {
    return this.request<void>(`/mt5/accounts/${accountId}`, {
      method: "DELETE",
    });
  }

  // ── Strategies ────────────────────────────────────────
  async listStrategies() {
    return this.request<Strategy[]>("/strategies/");
  }

  async selectStrategy(strategyId: string) {
    return this.request<{ message: string }>("/strategies/select", {
      method: "POST",
      body: JSON.stringify({ strategy_id: strategyId }),
    });
  }

  // ── Billing ───────────────────────────────────────────
  async listPlans() {
    return this.request<PlanPublic[]>("/billing/plans");
  }

  async getSubscription() {
    return this.request<Subscription>("/billing/subscription");
  }

  async listInvoices() {
    return this.request<Invoice[]>("/billing/invoices");
  }

  async checkUpgradeEligibility() {
    return this.request<UpgradeEligibility>("/billing/upgrade-check");
  }

  async requestUpgrade(targetPlanId: string) {
    return this.request<{ message: string; request_id: string }>("/billing/upgrade-request", {
      method: "POST",
      body: JSON.stringify({ target_plan_id: targetPlanId }),
    });
  }

  async myUpgradeRequests() {
    return this.request<UpgradeRequestItem[]>("/billing/upgrade-requests");
  }

  // ── Admin ─────────────────────────────────────────────
  async adminSearchUsers(query: string = "") {
    return this.request<AdminUser[]>(`/admin/users?q=${encodeURIComponent(query)}`);
  }

  async adminUnlockStrategy(userId: string, strategyId: string) {
    return this.request<{ message: string }>(
      `/admin/users/${userId}/unlock-strategy/${strategyId}`,
      { method: "POST" }
    );
  }

  async adminResetPassword(userId: string, newPassword: string) {
    return this.request<{ message: string }>(
      `/admin/users/${userId}/reset-password?new_password=${encodeURIComponent(newPassword)}`,
      { method: "POST" }
    );
  }

  async adminUnblockUser(userId: string) {
    return this.request<{ message: string }>(
      `/admin/users/${userId}/unblock`,
      { method: "POST" }
    );
  }

  async adminDisconnectMT5(userId: string, accountId: string) {
    return this.request<{ message: string }>(
      `/admin/users/${userId}/disconnect-mt5/${accountId}`,
      { method: "POST" }
    );
  }

  async adminCheckPayments() {
    return this.request<{ message: string }>("/admin/check-payments", {
      method: "POST",
    });
  }

  async adminGetUserInvoices(userId: string) {
    return this.request<Invoice[]>(`/admin/users/${userId}/invoices`);
  }

  async adminGetDashboard() {
    return this.request<AdminDashboard>("/admin/dashboard");
  }

  // ── Admin Plans ───────────────────────────────────────
  async adminListPlans() {
    return this.request<AdminPlan[]>("/admin/plans");
  }

  async adminCreatePlan(data: CreatePlanData) {
    return this.request<AdminPlan>("/admin/plans", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async adminUpdatePlan(planId: string, data: Partial<CreatePlanData>) {
    return this.request<AdminPlan>(`/admin/plans/${planId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async adminDeletePlan(planId: string) {
    return this.request<{ message: string }>(`/admin/plans/${planId}`, {
      method: "DELETE",
    });
  }

  async adminChangeUserPlan(userId: string, planId: string) {
    return this.request<{ message: string }>(
      `/admin/users/${userId}/change-plan`,
      { method: "POST", body: JSON.stringify({ plan_id: planId }) }
    );
  }

  // ── Admin Subscriptions & Invoices ────────────────────
  async adminListSubscriptions(status?: string) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<AdminSubscription[]>(`/admin/subscriptions${qs}`);
  }

  async adminListInvoices(status?: string) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<AdminInvoice[]>(`/admin/invoices${qs}`);
  }

  // ── Admin Upgrade Requests ────────────────────────────
  async adminListUpgradeRequests(status?: string) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<UpgradeRequestItem[]>(`/admin/upgrade-requests${qs}`);
  }

  async adminHandleUpgradeRequest(requestId: string, action: "approve" | "reject", note?: string) {
    return this.request<{ message: string }>(`/admin/upgrade-requests/${requestId}`, {
      method: "POST",
      body: JSON.stringify({ action, note }),
    });
  }

  // ── Legal / Terms ────────────────────────────────────
  async getActiveTerms(lang?: string) {
    const langParam = lang || localStorage.getItem("i18n_language") || "en";
    return this.request<TermsPublic>(`/legal/terms?lang=${langParam}`);
  }

  async acceptTerms(termsId: string) {
    return this.request<{ message: string; acceptance_id: string }>("/legal/terms/accept", {
      method: "POST",
      body: JSON.stringify({ terms_id: termsId }),
    });
  }

  async checkTermsAcceptance() {
    return this.request<TermsCheckResult>("/legal/terms/check");
  }

  // ── Admin Terms ──────────────────────────────────────
  async adminListTerms() {
    return this.request<AdminTermsItem[]>("/admin/terms");
  }

  async adminCreateTerms(data: CreateTermsData) {
    return this.request<{ message: string; id: string }>("/admin/terms", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async adminUpdateTerms(termsId: string, data: UpdateTermsData) {
    return this.request<{ message: string }>(`/admin/terms/${termsId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async adminActivateTerms(termsId: string) {
    return this.request<{ message: string }>(`/admin/terms/${termsId}/activate`, {
      method: "POST",
    });
  }

  async adminGetTermsContent(termsId: string) {
    return this.request<AdminTermsDetail>(`/admin/terms/${termsId}/content`);
  }

  // ── Admin Operations ─────────────────────────────────
  async adminGetOperations() {
    return this.request<OperationsDashboard>("/admin/operations");
  }

  // ── Admin Dead Letter Queue ────────────────────────
  async adminGetDeadLetterTrades(status?: string) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<DeadLetterTrade[]>(`/admin/dead-letter${qs}`);
  }

  async adminRetryDeadLetter(tradeId: string) {
    return this.request<{ message: string }>(`/admin/dead-letter/${tradeId}/retry`, { method: "POST" });
  }

  async adminResolveDeadLetter(tradeId: string, note: string = "") {
    return this.request<{ message: string }>(`/admin/dead-letter/${tradeId}/resolve?note=${encodeURIComponent(note)}`, { method: "POST" });
  }

  // ── Admin Risk Protection ───────────────────────────
  async adminGetRiskSettings() {
    return this.request<RiskSettings>("/admin/risk/settings");
  }

  async adminUpdateRiskSettings(data: RiskSettingsUpdate) {
    return this.request<RiskSettings>("/admin/risk/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async adminGetRiskStatus() {
    return this.request<RiskStatus>("/admin/risk/status");
  }

  async adminGetRiskIncidents() {
    return this.request<RiskIncident[]>("/admin/risk/incidents");
  }

  async adminResetEmergency() {
    return this.request<{ message: string }>("/admin/risk/reset-emergency", {
      method: "POST",
    });
  }
}

// ── Error class ───────────────────────────────────────
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Types ─────────────────────────────────────────────
export interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
  role: string;
}

export interface MT5Account {
  id: string;
  login: number;
  server: string;
  status: string;
  balance: number | null;
  equity: number | null;
  last_connected_at: string | null;
}

export interface Strategy {
  id: string;
  level: string;
  name: string;
  description: string | null;
  risk_multiplier: number;
  requires_unlock: boolean;
  is_available: boolean;
}

export interface PlanPublic {
  id: string;
  name: string;
  price: number;
  allowed_strategies: string[];
  trial_days: number;
  max_accounts: number;
}

export interface Subscription {
  id: string;
  status: string;
  plan_name: string | null;
  plan_price: number | null;
  trial_start: string;
  trial_end: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  auto_renew: boolean;
}

export interface Invoice {
  id: string;
  amount: number;
  currency: string;
  status: string;
  issue_date: string;
  due_date: string;
  paid_at: string | null;
  provider: string | null;
}

export interface UpgradeEligibility {
  eligible: boolean;
  has_pending_request?: boolean;
  reason?: string;
  current_plan?: { id: string; name: string; price: number } | null;
  next_plan?: { id: string; name: string; price: number } | null;
  mt5_balance?: number;
  min_balance_required?: number;
}

export interface UpgradeRequestItem {
  id: string;
  user_id: string;
  user_email?: string;
  current_plan_name: string | null;
  target_plan_name: string | null;
  target_plan_price: number | null;
  mt5_balance: number;
  status: string;
  admin_note: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AdminUser {
  id: string;
  email: string;
  is_active: boolean;
  mt5_accounts: { id: string; login: number; server: string; status: string }[];
  subscription_status: string | null;
  plan_name: string | null;
  active_strategy: string | null;
}

export interface AdminDashboard {
  total_users: number;
  active_accounts: number;
  trial_accounts: number;
  blocked_accounts: number;
  total_revenue: number;
  pending_invoices: number;
  overdue_invoices: number;
}

export interface AdminPlan {
  id: string;
  name: string;
  price: number;
  allowed_strategies: string[];
  trial_days: number;
  max_accounts: number;
  active: boolean;
}

export interface CreatePlanData {
  name: string;
  price: number;
  allowed_strategies: string[];
  trial_days: number;
  max_accounts: number;
  active: boolean;
}

export interface AdminSubscription {
  id: string;
  user_email: string;
  user_id: string;
  plan_name: string | null;
  status: string;
  trial_start: string | null;
  trial_end: string | null;
  created_at: string;
}

export interface AdminInvoice {
  id: string;
  user_email: string;
  amount: number;
  currency: string;
  status: string;
  issue_date: string;
  due_date: string;
  paid_at: string | null;
  provider: string | null;
}

// ── Terms Types ───────────────────────────────────────
export interface TermsPublic {
  id: string;
  title: string;
  content: string;
  version: number;
  company_name: string;
  updated_at: string;
}

export interface TermsCheckResult {
  needs_acceptance: boolean;
  terms_id?: string;
  version?: number;
  title?: string;
}

export interface AdminTermsItem {
  id: string;
  title: string;
  version: number;
  company_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  acceptance_count: number;
}

export interface AdminTermsDetail {
  id: string;
  title: string;
  content: string;
  version: number;
  company_name: string;
  is_active: boolean;
}

export interface CreateTermsData {
  title: string;
  content: string;
  version: number;
  company_name: string;
}

export interface UpdateTermsData {
  title?: string;
  content?: string;
  company_name?: string;
}

// ── Risk Protection Types ────────────────────────────
export interface RiskSettings {
  global_max_drawdown_percent: number;
  protection_enabled: boolean;
  updated_at: string;
}

export interface RiskSettingsUpdate {
  global_max_drawdown_percent?: number;
  protection_enabled?: boolean;
}

export interface RiskStatus {
  total_balance: number;
  total_equity: number;
  current_drawdown_percent: number;
  protection_enabled: boolean;
  max_drawdown_percent: number;
  emergency_active: boolean;
  account_count: number;
}

export interface RiskIncident {
  id: string;
  incident_type: string;
  drawdown_percent: number;
  total_balance: number;
  total_equity: number;
  created_at: string;
}

// Singleton
export const api = new ApiClient();
