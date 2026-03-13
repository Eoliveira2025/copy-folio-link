import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Search,
  RefreshCw,
  Users,
  BarChart3,
  Server,
  Shield,
  CreditCard,
  FileText,
  Package,
  Plus,
  Pencil,
  Trash2,
  ArrowUpDown,
  AlertTriangle,
  ArrowUpCircle,
  Check,
  X,
  Scale,
  Power,
  Eye,
} from "lucide-react";
import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  useAdminUsers,
  useAdminCheckPayments,
  useAdminUnblockUser,
  useAdminDashboard,
  useAdminPlans,
  useAdminCreatePlan,
  useAdminUpdatePlan,
  useAdminDeletePlan,
  useAdminChangeUserPlan,
  useAdminSubscriptions,
  useAdminInvoices,
  useAdminUpgradeRequests,
  useAdminHandleUpgradeRequest,
  useAdminTerms,
  useAdminCreateTerms,
  useAdminUpdateTerms,
  useAdminActivateTerms,
} from "@/hooks/use-api";
import { StatCard } from "@/components/StatCard";
import type { AdminPlan, CreatePlanData, AdminTermsItem } from "@/lib/api";
import { api } from "@/lib/api";
import { RiskProtectionTab } from "@/components/admin/RiskProtectionTab";

const statusStyle: Record<string, string> = {
  active: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  trial: "bg-info/15 text-info border-info/30 hover:bg-info/15",
  blocked: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  expired: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  connected: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  disconnected: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  paid: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  pending: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  overdue: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  cancelled: "bg-muted text-muted-foreground border-border hover:bg-muted",
};

const STRATEGY_OPTIONS = ["low", "medium", "high", "pro", "expert", "expert_pro"];

// ── Plan Form ────────────────────────────────────────
function PlanFormDialog({
  plan,
  onClose,
}: {
  plan?: AdminPlan;
  onClose: () => void;
}) {
  const createPlan = useAdminCreatePlan();
  const updatePlan = useAdminUpdatePlan();

  const [name, setName] = useState(plan?.name || "");
  const [price, setPrice] = useState(String(plan?.price || ""));
  const [trialDays, setTrialDays] = useState(String(plan?.trial_days ?? 30));
  const [maxAccounts, setMaxAccounts] = useState(String(plan?.max_accounts ?? 1));
  const [active, setActive] = useState(plan?.active ?? true);
  const [strategies, setStrategies] = useState<string[]>(plan?.allowed_strategies || []);

  const toggleStrategy = (s: string) => {
    setStrategies((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  };

  const handleSubmit = () => {
    const data: CreatePlanData = {
      name,
      price: parseFloat(price),
      allowed_strategies: strategies,
      trial_days: parseInt(trialDays),
      max_accounts: parseInt(maxAccounts),
      active,
    };

    if (plan) {
      updatePlan.mutate({ planId: plan.id, updates: data }, { onSuccess: onClose });
    } else {
      createPlan.mutate(data, { onSuccess: onClose });
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Plan Name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Starter" className="bg-secondary" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-2">
          <Label>Price ($/mo)</Label>
          <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} className="bg-secondary" />
        </div>
        <div className="space-y-2">
          <Label>Trial Days</Label>
          <Input type="number" value={trialDays} onChange={(e) => setTrialDays(e.target.value)} className="bg-secondary" />
        </div>
        <div className="space-y-2">
          <Label>Max Accounts</Label>
          <Input type="number" value={maxAccounts} onChange={(e) => setMaxAccounts(e.target.value)} className="bg-secondary" />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Allowed Strategies</Label>
        <div className="flex flex-wrap gap-2">
          {STRATEGY_OPTIONS.map((s) => (
            <Badge
              key={s}
              variant="outline"
              className={`cursor-pointer transition-colors ${
                strategies.includes(s)
                  ? "bg-primary/20 text-primary border-primary/40"
                  : "bg-secondary text-muted-foreground border-border"
              }`}
              onClick={() => toggleStrategy(s)}
            >
              {s.toUpperCase()}
            </Badge>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Switch checked={active} onCheckedChange={setActive} />
        <Label>Active</Label>
      </div>
      <Button onClick={handleSubmit} disabled={createPlan.isPending || updatePlan.isPending} className="w-full">
        {plan ? "Update Plan" : "Create Plan"}
      </Button>
    </div>
  );
}

// ── Change Plan Dialog ───────────────────────────────
function ChangePlanDialog({
  userId,
  userName,
  plans,
  onClose,
}: {
  userId: string;
  userName: string;
  plans: AdminPlan[];
  onClose: () => void;
}) {
  const changePlan = useAdminChangeUserPlan();
  const [selectedPlan, setSelectedPlan] = useState("");

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Change plan for <span className="text-foreground font-medium">{userName}</span></p>
      <Select value={selectedPlan} onValueChange={setSelectedPlan}>
        <SelectTrigger className="bg-secondary">
          <SelectValue placeholder="Select a plan" />
        </SelectTrigger>
        <SelectContent>
          {plans.filter((p) => p.active).map((p) => (
            <SelectItem key={p.id} value={p.id}>
              {p.name} — ${p.price}/mo
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        onClick={() => changePlan.mutate({ userId, planId: selectedPlan }, { onSuccess: onClose })}
        disabled={!selectedPlan || changePlan.isPending}
        className="w-full"
      >
        {changePlan.isPending ? "Changing..." : "Change Plan"}
      </Button>
    </div>
  );
}

// ── Main Admin Panel ─────────────────────────────────
const AdminPanel = () => {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [subStatusFilter, setSubStatusFilter] = useState("");
  const [invStatusFilter, setInvStatusFilter] = useState("");
  const [upgradeStatusFilter, setUpgradeStatusFilter] = useState("");
  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<AdminPlan | undefined>();
  const [changePlanUser, setChangePlanUser] = useState<{ id: string; email: string } | null>(null);
  const [upgradeNote, setUpgradeNote] = useState("");
  const [termsDialogOpen, setTermsDialogOpen] = useState(false);
  const [editingTerms, setEditingTerms] = useState<AdminTermsItem | undefined>();
  const [termsTitle, setTermsTitle] = useState("");
  const [termsContent, setTermsContent] = useState("");
  const [termsVersion, setTermsVersion] = useState("1");
  const [termsCompany, setTermsCompany] = useState("CopyTrade Pro");

  const { data: users, isLoading: usersLoading } = useAdminUsers(debouncedSearch);
  const { data: dashboard, isLoading: dashLoading } = useAdminDashboard();
  const { data: plans, isLoading: plansLoading } = useAdminPlans();
  const { data: subscriptions, isLoading: subsLoading } = useAdminSubscriptions(subStatusFilter || undefined);
  const { data: invoices, isLoading: invsLoading } = useAdminInvoices(invStatusFilter || undefined);
  const { data: upgradeRequests, isLoading: upgradesLoading } = useAdminUpgradeRequests(upgradeStatusFilter || undefined);
  const { data: termsDocuments, isLoading: termsLoading } = useAdminTerms();
  const checkPayments = useAdminCheckPayments();
  const unblockUser = useAdminUnblockUser();
  const deletePlan = useAdminDeletePlan();
  const handleUpgrade = useAdminHandleUpgradeRequest();
  const createTerms = useAdminCreateTerms();
  const updateTerms = useAdminUpdateTerms();
  const activateTerms = useAdminActivateTerms();

  const handleSearch = (val: string) => {
    setSearch(val);
    setTimeout(() => setDebouncedSearch(val), 300);
  };

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    try {
      return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return d;
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin Panel</h1>
          <p className="text-muted-foreground text-sm">Manage users, plans, subscriptions, and billing</p>
        </div>
        <Button
          variant="outline"
          onClick={() => checkPayments.mutate()}
          disabled={checkPayments.isPending}
          className="gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${checkPayments.isPending ? "animate-spin" : ""}`} />
          {checkPayments.isPending ? "Checking..." : "Check Payments"}
        </Button>
      </div>

      {/* Dashboard Stats */}
      {dashLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : dashboard ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Total Users" value={String(dashboard.total_users)} icon={Users} delay={0} />
          <StatCard title="Active" value={String(dashboard.active_accounts)} icon={Shield} trend="up" delay={0.05} />
          <StatCard title="Trial" value={String(dashboard.trial_accounts)} icon={BarChart3} trend="neutral" subtitle="Free trial" delay={0.1} />
          <StatCard title="Blocked" value={String(dashboard.blocked_accounts)} icon={AlertTriangle} trend="down" subtitle={`${dashboard.pending_invoices} pending · ${dashboard.overdue_invoices} overdue`} delay={0.15} />
        </div>
      ) : null}

      <Tabs defaultValue="users">
        <TabsList className="bg-secondary">
          <TabsTrigger value="users" className="gap-2"><Users className="w-4 h-4" /> Users</TabsTrigger>
          <TabsTrigger value="plans" className="gap-2"><Package className="w-4 h-4" /> Plans</TabsTrigger>
          <TabsTrigger value="subscriptions" className="gap-2"><CreditCard className="w-4 h-4" /> Subscriptions</TabsTrigger>
          <TabsTrigger value="invoices" className="gap-2"><FileText className="w-4 h-4" /> Invoices</TabsTrigger>
          <TabsTrigger value="upgrades" className="gap-2"><ArrowUpCircle className="w-4 h-4" /> Upgrades</TabsTrigger>
          <TabsTrigger value="risk" className="gap-2"><AlertTriangle className="w-4 h-4" /> Risk</TabsTrigger>
          <TabsTrigger value="legal" className="gap-2"><Scale className="w-4 h-4" /> Legal</TabsTrigger>
          <TabsTrigger value="servers" className="gap-2"><Server className="w-4 h-4" /> Servers</TabsTrigger>
        </TabsList>

        {/* ── Users Tab ────────────────────────────────── */}
        <TabsContent value="users" className="mt-4 space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search by email or MT5 login..."
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-9 h-10 bg-secondary border-border"
            />
          </div>

          {usersLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                      <th className="p-3 font-medium">Email</th>
                      <th className="p-3 font-medium">Plan</th>
                      <th className="p-3 font-medium">MT5 Login</th>
                      <th className="p-3 font-medium">MT5 Status</th>
                      <th className="p-3 font-medium">Subscription</th>
                      <th className="p-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users?.map((user) => (
                      <tr key={user.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                        <td className="p-3">{user.email}</td>
                        <td className="p-3">
                          {user.plan_name ? (
                            <Badge variant="outline" className="bg-accent/10 text-accent-foreground border-accent/30">
                              {user.plan_name}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground text-xs">No plan</span>
                          )}
                        </td>
                        <td className="p-3 font-mono">
                          {user.mt5_accounts.length > 0
                            ? user.mt5_accounts.map((a) => a.login).join(", ")
                            : "—"}
                        </td>
                        <td className="p-3">
                          {user.mt5_accounts.length > 0 ? (
                            user.mt5_accounts.map((a) => (
                              <Badge key={a.login} className={statusStyle[a.status] || ""}>
                                {a.status}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-muted-foreground">No account</span>
                          )}
                        </td>
                        <td className="p-3">
                          {user.subscription_status ? (
                            <Badge className={statusStyle[user.subscription_status] || ""}>
                              {user.subscription_status}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="p-3">
                          <div className="flex gap-1">
                            <Dialog open={changePlanUser?.id === user.id} onOpenChange={(open) => !open && setChangePlanUser(null)}>
                              <DialogTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 text-xs gap-1"
                                  onClick={() => setChangePlanUser({ id: user.id, email: user.email })}
                                >
                                  <ArrowUpDown className="w-3 h-3" /> Plan
                                </Button>
                              </DialogTrigger>
                              <DialogContent>
                                <DialogHeader>
                                  <DialogTitle>Change User Plan</DialogTitle>
                                </DialogHeader>
                                {plans && (
                                  <ChangePlanDialog
                                    userId={user.id}
                                    userName={user.email}
                                    plans={plans}
                                    onClose={() => setChangePlanUser(null)}
                                  />
                                )}
                              </DialogContent>
                            </Dialog>
                            {user.subscription_status === "blocked" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => unblockUser.mutate(user.id)}
                                disabled={unblockUser.isPending}
                              >
                                Unblock
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {(!users || users.length === 0) && (
                      <tr>
                        <td colSpan={6} className="p-6 text-center text-muted-foreground">
                          No users found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </TabsContent>

        {/* ── Plans Tab ────────────────────────────────── */}
        <TabsContent value="plans" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <Dialog open={planDialogOpen} onOpenChange={(open) => { setPlanDialogOpen(open); if (!open) setEditingPlan(undefined); }}>
              <DialogTrigger asChild>
                <Button className="gap-2" onClick={() => { setEditingPlan(undefined); setPlanDialogOpen(true); }}>
                  <Plus className="w-4 h-4" /> Create Plan
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{editingPlan ? "Edit Plan" : "Create Plan"}</DialogTitle>
                </DialogHeader>
                <PlanFormDialog plan={editingPlan} onClose={() => setPlanDialogOpen(false)} />
              </DialogContent>
            </Dialog>
          </div>

          {plansLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {plans?.map((plan) => (
                <motion.div
                  key={plan.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="card-glass rounded-lg p-5 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-lg">{plan.name}</h3>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => { setEditingPlan(plan); setPlanDialogOpen(true); }}
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-danger hover:text-danger"
                        onClick={() => deletePlan.mutate(plan.id)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-mono font-bold text-primary">${plan.price}</span>
                    <span className="text-muted-foreground text-sm">/mo</span>
                  </div>
                  <div className="text-sm space-y-1 text-muted-foreground">
                    <div>Trial: <span className="text-foreground">{plan.trial_days} days</span></div>
                    <div>Max accounts: <span className="text-foreground">{plan.max_accounts}</span></div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {plan.allowed_strategies.map((s) => (
                      <Badge key={s} variant="outline" className="text-xs bg-primary/10 text-primary border-primary/30">
                        {s.toUpperCase()}
                      </Badge>
                    ))}
                  </div>
                  <Badge className={plan.active ? statusStyle.active : statusStyle.expired}>
                    {plan.active ? "Active" : "Inactive"}
                  </Badge>
                </motion.div>
              ))}
              {(!plans || plans.length === 0) && (
                <div className="col-span-full p-6 text-center text-muted-foreground card-glass rounded-lg">
                  No plans created yet. Click "Create Plan" to add one.
                </div>
              )}
            </div>
          )}
        </TabsContent>

        {/* ── Subscriptions Tab ────────────────────────── */}
        <TabsContent value="subscriptions" className="mt-4 space-y-4">
          <div className="flex gap-2">
            {["", "trial", "active", "blocked", "expired"].map((s) => (
              <Button
                key={s}
                variant={subStatusFilter === s ? "default" : "outline"}
                size="sm"
                onClick={() => setSubStatusFilter(s)}
                className="text-xs"
              >
                {s || "All"}
              </Button>
            ))}
          </div>

          {subsLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                      <th className="p-3 font-medium">User</th>
                      <th className="p-3 font-medium">Plan</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Trial Start</th>
                      <th className="p-3 font-medium">Trial End</th>
                      <th className="p-3 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subscriptions?.map((sub) => (
                      <tr key={sub.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                        <td className="p-3">{sub.user_email}</td>
                        <td className="p-3">{sub.plan_name || <span className="text-muted-foreground">—</span>}</td>
                        <td className="p-3">
                          <Badge className={statusStyle[sub.status] || ""}>{sub.status}</Badge>
                        </td>
                        <td className="p-3 text-muted-foreground">{formatDate(sub.trial_start)}</td>
                        <td className="p-3 text-muted-foreground">{formatDate(sub.trial_end)}</td>
                        <td className="p-3 text-muted-foreground">{formatDate(sub.created_at)}</td>
                      </tr>
                    ))}
                    {(!subscriptions || subscriptions.length === 0) && (
                      <tr>
                        <td colSpan={6} className="p-6 text-center text-muted-foreground">No subscriptions found</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </TabsContent>

        {/* ── Invoices Tab ─────────────────────────────── */}
        <TabsContent value="invoices" className="mt-4 space-y-4">
          <div className="flex gap-2">
            {["", "pending", "paid", "overdue", "cancelled"].map((s) => (
              <Button
                key={s}
                variant={invStatusFilter === s ? "default" : "outline"}
                size="sm"
                onClick={() => setInvStatusFilter(s)}
                className="text-xs"
              >
                {s || "All"}
              </Button>
            ))}
          </div>

          {invsLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                      <th className="p-3 font-medium">User</th>
                      <th className="p-3 font-medium">Amount</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Issue Date</th>
                      <th className="p-3 font-medium">Due Date</th>
                      <th className="p-3 font-medium">Paid At</th>
                      <th className="p-3 font-medium">Provider</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices?.map((inv) => (
                      <tr key={inv.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                        <td className="p-3">{inv.user_email}</td>
                        <td className="p-3 font-mono">${inv.amount.toFixed(2)} {inv.currency}</td>
                        <td className="p-3">
                          <Badge className={statusStyle[inv.status] || ""}>{inv.status}</Badge>
                        </td>
                        <td className="p-3 text-muted-foreground">{formatDate(inv.issue_date)}</td>
                        <td className="p-3 text-muted-foreground">{formatDate(inv.due_date)}</td>
                        <td className="p-3 text-muted-foreground">{formatDate(inv.paid_at)}</td>
                        <td className="p-3 text-muted-foreground">{inv.provider || "—"}</td>
                      </tr>
                    ))}
                    {(!invoices || invoices.length === 0) && (
                      <tr>
                        <td colSpan={7} className="p-6 text-center text-muted-foreground">No invoices found</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </TabsContent>

        {/* ── Upgrade Requests Tab ──────────────────────── */}
        <TabsContent value="upgrades" className="mt-4 space-y-4">
          <div className="flex gap-2">
            {["", "pending", "approved", "rejected"].map((s) => (
              <Button
                key={s}
                variant={upgradeStatusFilter === s ? "default" : "outline"}
                size="sm"
                onClick={() => setUpgradeStatusFilter(s)}
                className="text-xs"
              >
                {s || "All"}
              </Button>
            ))}
          </div>

          {upgradesLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                      <th className="p-3 font-medium">User</th>
                      <th className="p-3 font-medium">Current Plan</th>
                      <th className="p-3 font-medium">Target Plan</th>
                      <th className="p-3 font-medium">Balance</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Date</th>
                      <th className="p-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {upgradeRequests?.map((req) => (
                      <tr key={req.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                        <td className="p-3">{req.user_email || "—"}</td>
                        <td className="p-3">{req.current_plan_name || "—"}</td>
                        <td className="p-3 font-medium text-primary">{req.target_plan_name}</td>
                        <td className="p-3 font-mono">${req.mt5_balance.toFixed(2)}</td>
                        <td className="p-3">
                          <Badge className={
                            req.status === "approved" ? "bg-success/15 text-success border-success/30 hover:bg-success/15" :
                            req.status === "rejected" ? "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15" :
                            "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15"
                          }>
                            {req.status.charAt(0).toUpperCase() + req.status.slice(1)}
                          </Badge>
                        </td>
                        <td className="p-3 text-muted-foreground">{formatDate(req.created_at)}</td>
                        <td className="p-3">
                          {req.status === "pending" ? (
                            <div className="flex gap-1">
                              <Dialog>
                                <DialogTrigger asChild>
                                  <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 text-success hover:text-success">
                                    <Check className="w-3 h-3" /> Approve
                                  </Button>
                                </DialogTrigger>
                                <DialogContent>
                                  <DialogHeader>
                                    <DialogTitle>Approve Upgrade</DialogTitle>
                                  </DialogHeader>
                                  <div className="space-y-3">
                                    <p className="text-sm text-muted-foreground">
                                      Approve <span className="text-foreground font-medium">{req.user_email}</span> upgrade to{" "}
                                      <span className="text-primary font-medium">{req.target_plan_name}</span> (${req.target_plan_price}/mo)?
                                    </p>
                                    <p className="text-xs text-muted-foreground">This will update their plan, generate a new invoice, and start billing immediately.</p>
                                    <Textarea
                                      placeholder="Optional note..."
                                      value={upgradeNote}
                                      onChange={(e) => setUpgradeNote(e.target.value)}
                                      className="bg-secondary"
                                    />
                                    <Button
                                      onClick={() => {
                                        handleUpgrade.mutate({ requestId: req.id, action: "approve", note: upgradeNote || undefined });
                                        setUpgradeNote("");
                                      }}
                                      disabled={handleUpgrade.isPending}
                                      className="w-full"
                                    >
                                      {handleUpgrade.isPending ? "Approving..." : "Confirm Approval"}
                                    </Button>
                                  </div>
                                </DialogContent>
                              </Dialog>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs gap-1 text-danger hover:text-danger"
                                onClick={() => handleUpgrade.mutate({ requestId: req.id, action: "reject" })}
                                disabled={handleUpgrade.isPending}
                              >
                                <X className="w-3 h-3" /> Reject
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">{req.admin_note || "—"}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {(!upgradeRequests || upgradeRequests.length === 0) && (
                      <tr>
                        <td colSpan={7} className="p-6 text-center text-muted-foreground">No upgrade requests found</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </TabsContent>

        {/* ── Risk Protection Tab ──────────────────────── */}
        <TabsContent value="risk" className="mt-4 space-y-4">
          <RiskProtectionTab />
        </TabsContent>

        {/* ── Legal / Terms Tab ─────────────────────────── */}
        <TabsContent value="legal" className="mt-4 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="font-semibold text-lg">Terms & Conditions</h3>
            <Dialog open={termsDialogOpen} onOpenChange={(open) => { setTermsDialogOpen(open); if (!open) setEditingTerms(undefined); }}>
              <DialogTrigger asChild>
                <Button className="gap-2" onClick={() => {
                  setEditingTerms(undefined);
                  setTermsTitle("");
                  setTermsContent("");
                  setTermsVersion(String((termsDocuments?.length || 0) + 1));
                  setTermsCompany("CopyTrade Pro");
                  setTermsDialogOpen(true);
                }}>
                  <Plus className="w-4 h-4" /> New Version
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>{editingTerms ? "Edit Terms" : "Create Terms Version"}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label>Title</Label>
                      <Input value={termsTitle} onChange={(e) => setTermsTitle(e.target.value)} placeholder="Terms and Conditions" className="bg-secondary" />
                    </div>
                    <div className="space-y-2">
                      <Label>Company Name</Label>
                      <Input value={termsCompany} onChange={(e) => setTermsCompany(e.target.value)} placeholder="CopyTrade Pro" className="bg-secondary" />
                    </div>
                  </div>
                  {!editingTerms && (
                    <div className="space-y-2">
                      <Label>Version Number</Label>
                      <Input type="number" value={termsVersion} onChange={(e) => setTermsVersion(e.target.value)} className="bg-secondary w-32" />
                    </div>
                  )}
                  <div className="space-y-2">
                    <Label>Content (HTML)</Label>
                    <Textarea
                      value={termsContent}
                      onChange={(e) => setTermsContent(e.target.value)}
                      placeholder="<h2>1. General Terms</h2><p>...</p>"
                      className="bg-secondary min-h-[300px] font-mono text-xs"
                    />
                  </div>
                  <Button
                    onClick={() => {
                      if (editingTerms) {
                        updateTerms.mutate(
                          { termsId: editingTerms.id, updates: { title: termsTitle, content: termsContent, company_name: termsCompany } },
                          { onSuccess: () => setTermsDialogOpen(false) }
                        );
                      } else {
                        createTerms.mutate(
                          { title: termsTitle, content: termsContent, version: parseInt(termsVersion), company_name: termsCompany },
                          { onSuccess: () => setTermsDialogOpen(false) }
                        );
                      }
                    }}
                    disabled={createTerms.isPending || updateTerms.isPending || !termsTitle || !termsContent}
                    className="w-full"
                  >
                    {editingTerms ? "Update Terms" : "Create Terms"}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {termsLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <div className="space-y-3">
              {termsDocuments?.map((doc) => (
                <motion.div
                  key={doc.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="card-glass rounded-lg p-5"
                >
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <h4 className="font-semibold">{doc.title}</h4>
                        <Badge variant="outline" className="text-xs">v{doc.version}</Badge>
                        {doc.is_active && (
                          <Badge className="bg-success/15 text-success border-success/30 hover:bg-success/15 text-xs">Active</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {doc.company_name} · {doc.acceptance_count} acceptance{doc.acceptance_count !== 1 ? "s" : ""} · Updated {formatDate(doc.updated_at)}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs gap-1"
                        onClick={async () => {
                          try {
                            const detail = await api.adminGetTermsContent(doc.id);
                            setEditingTerms(doc);
                            setTermsTitle(detail.title);
                            setTermsContent(detail.content);
                            setTermsCompany(detail.company_name);
                            setTermsDialogOpen(true);
                          } catch {}
                        }}
                      >
                        <Pencil className="w-3 h-3" /> Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs gap-1"
                        onClick={() => window.open("/terms-of-service", "_blank")}
                      >
                        <Eye className="w-3 h-3" /> Preview
                      </Button>
                      {!doc.is_active && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 text-xs gap-1 text-primary hover:text-primary"
                          onClick={() => activateTerms.mutate(doc.id)}
                          disabled={activateTerms.isPending}
                        >
                          <Power className="w-3 h-3" /> Activate
                        </Button>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
              {(!termsDocuments || termsDocuments.length === 0) && (
                <div className="card-glass rounded-lg p-8 text-center text-muted-foreground">
                  No terms documents yet. Click "New Version" to create one.
                </div>
              )}
            </div>
          )}
        </TabsContent>

        {/* ── Servers Tab ──────────────────────────────── */}
        <TabsContent value="servers" className="mt-4">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-6 space-y-4">
            <h3 className="font-semibold">MT5 Servers</h3>
            <div className="space-y-2">
              {["Exness-MT5Real", "Exness-MT5Real2", "Exness-MT5Real3", "Exness-MT5Trial"].map((s) => (
                <div key={s} className="flex items-center justify-between p-3 rounded-md bg-muted/30">
                  <span className="font-mono text-sm">{s}</span>
                  <Badge className="bg-success/15 text-success border-success/30 hover:bg-success/15">Active</Badge>
                </div>
              ))}
            </div>
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminPanel;
