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
} from "@/hooks/use-api";
import { StatCard } from "@/components/StatCard";
import type { AdminPlan, CreatePlanData } from "@/lib/api";

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

  const { data: users, isLoading: usersLoading } = useAdminUsers(debouncedSearch);
  const { data: dashboard, isLoading: dashLoading } = useAdminDashboard();
  const { data: plans, isLoading: plansLoading } = useAdminPlans();
  const { data: subscriptions, isLoading: subsLoading } = useAdminSubscriptions(subStatusFilter || undefined);
  const { data: invoices, isLoading: invsLoading } = useAdminInvoices(invStatusFilter || undefined);
  const { data: upgradeRequests, isLoading: upgradesLoading } = useAdminUpgradeRequests(upgradeStatusFilter || undefined);
  const checkPayments = useAdminCheckPayments();
  const unblockUser = useAdminUnblockUser();
  const deletePlan = useAdminDeletePlan();
  const handleUpgrade = useAdminHandleUpgradeRequest();

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
