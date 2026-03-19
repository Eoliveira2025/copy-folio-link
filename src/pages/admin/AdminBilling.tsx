import { useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { DollarSign, Users, FileText, AlertTriangle, CreditCard, TrendingUp, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAdminBillingStats,
  useAdminSubscriptions,
  useAdminInvoices,
  useAdminCancelSubscription,
  useAdminRefundInvoice,
} from "@/hooks/use-api";
import { format } from "date-fns";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const statusStyle: Record<string, string> = {
  paid: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  pending: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  overdue: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  cancelled: "bg-muted text-muted-foreground border-border hover:bg-muted",
  active: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  trial: "bg-info/15 text-info border-info/30 hover:bg-info/15",
  blocked: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  expired: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
};

const formatDate = (d: string | null) => {
  if (!d) return "—";
  try { return format(new Date(d), "MMM dd, yyyy"); } catch { return d; }
};

const AdminBilling = () => {
  const { t } = useTranslation();
  const { data: stats, isLoading: statsLoading } = useAdminBillingStats();
  const [subFilter, setSubFilter] = useState<string>("");
  const [invFilter, setInvFilter] = useState<string>("");
  const { data: subs, isLoading: subsLoading } = useAdminSubscriptions(subFilter || undefined);
  const { data: invoices, isLoading: invLoading } = useAdminInvoices(invFilter || undefined);
  const cancelSub = useAdminCancelSubscription();
  const refundInv = useAdminRefundInvoice();

  const [cancelTarget, setCancelTarget] = useState<string | null>(null);
  const [refundTarget, setRefundTarget] = useState<string | null>(null);

  const statCards = [
    { label: t("adminBilling.totalRevenue"), value: stats ? `R$ ${stats.total_revenue.toFixed(2)}` : "—", icon: DollarSign, color: "text-primary" },
    { label: t("adminBilling.activeSubs"), value: stats?.active_subscriptions ?? 0, icon: Users, color: "text-[hsl(var(--success))]" },
    { label: t("adminBilling.trialSubs"), value: stats?.trial_subscriptions ?? 0, icon: Clock, color: "text-[hsl(var(--info))]" },
    { label: t("adminBilling.blockedSubs"), value: stats?.blocked_subscriptions ?? 0, icon: AlertTriangle, color: "text-[hsl(var(--danger))]" },
    { label: t("adminBilling.pendingInvoices"), value: stats?.pending_invoices ?? 0, icon: FileText, color: "text-[hsl(var(--warning))]" },
    { label: t("adminBilling.paidThisMonth"), value: stats?.paid_invoices_this_month ?? 0, icon: TrendingUp, color: "text-primary" },
  ];

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold">{t("adminBilling.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("adminBilling.subtitle")}</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {statCards.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
            <Card className="card-glass">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <s.icon className={`w-4 h-4 ${s.color}`} />
                  <span className="text-xs text-muted-foreground truncate">{s.label}</span>
                </div>
                {statsLoading ? (
                  <Skeleton className="h-7 w-16" />
                ) : (
                  <div className="text-xl font-bold font-mono">{s.value}</div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="subscriptions">
        <TabsList>
          <TabsTrigger value="subscriptions">{t("admin.subscriptions")}</TabsTrigger>
          <TabsTrigger value="invoices">{t("admin.invoices")}</TabsTrigger>
        </TabsList>

        <TabsContent value="subscriptions" className="space-y-4">
          <div className="flex justify-end">
            <Select value={subFilter} onValueChange={setSubFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder={t("common.all")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("common.all")}</SelectItem>
                <SelectItem value="active">{t("common.active")}</SelectItem>
                <SelectItem value="trial">{t("adminBilling.trial")}</SelectItem>
                <SelectItem value="blocked">{t("adminBilling.blocked")}</SelectItem>
                <SelectItem value="expired">{t("adminBilling.expired")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {subsLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground text-left border-b border-border">
                    <th className="pb-3 font-medium">{t("admin.user")}</th>
                    <th className="pb-3 font-medium">{t("financial.plan")}</th>
                    <th className="pb-3 font-medium">{t("financial.status")}</th>
                    <th className="pb-3 font-medium">{t("admin.trialEnd")}</th>
                    <th className="pb-3 font-medium">{t("admin.created")}</th>
                    <th className="pb-3 font-medium">{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {subs && subs.length > 0 ? subs.map((s) => (
                    <tr key={s.id} className="border-b border-border/50 last:border-0">
                      <td className="py-3 text-sm">{s.user_email}</td>
                      <td className="py-3 font-medium">{s.plan_name || "—"}</td>
                      <td className="py-3">
                        <Badge className={statusStyle[s.status] || ""}>{s.status}</Badge>
                      </td>
                      <td className="py-3 text-muted-foreground font-mono text-xs">{formatDate(s.trial_end)}</td>
                      <td className="py-3 text-muted-foreground font-mono text-xs">{formatDate(s.created_at)}</td>
                      <td className="py-3">
                        {s.status !== "cancelled" && (
                          <Button size="sm" variant="destructive" onClick={() => setCancelTarget(s.id)}>
                            {t("adminBilling.cancel")}
                          </Button>
                        )}
                      </td>
                    </tr>
                  )) : (
                    <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">{t("admin.noSubscriptions")}</td></tr>
                  )}
                </tbody>
              </table>
            </motion.div>
          )}
        </TabsContent>

        <TabsContent value="invoices" className="space-y-4">
          <div className="flex justify-end">
            <Select value={invFilter} onValueChange={setInvFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder={t("common.all")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("common.all")}</SelectItem>
                <SelectItem value="paid">{t("adminBilling.paid")}</SelectItem>
                <SelectItem value="pending">{t("adminBilling.pendingStatus")}</SelectItem>
                <SelectItem value="overdue">{t("adminBilling.overdueStatus")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {invLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground text-left border-b border-border">
                    <th className="pb-3 font-medium">{t("admin.user")}</th>
                    <th className="pb-3 font-medium">{t("financial.plan")}</th>
                    <th className="pb-3 font-medium">{t("financial.amount")}</th>
                    <th className="pb-3 font-medium">{t("financial.status")}</th>
                    <th className="pb-3 font-medium">{t("financial.dueDate")}</th>
                    <th className="pb-3 font-medium">{t("financial.paidAt")}</th>
                    <th className="pb-3 font-medium">{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices && invoices.length > 0 ? invoices.map((inv) => (
                    <tr key={inv.id} className="border-b border-border/50 last:border-0">
                      <td className="py-3 text-sm">{inv.user_email || "—"}</td>
                      <td className="py-3">{inv.plan_name || "—"}</td>
                      <td className="py-3 font-mono">R$ {inv.amount.toFixed(2)}</td>
                      <td className="py-3">
                        <Badge className={statusStyle[inv.status] || ""}>{inv.status}</Badge>
                      </td>
                      <td className="py-3 text-muted-foreground font-mono text-xs">{formatDate(inv.due_date)}</td>
                      <td className="py-3 text-muted-foreground font-mono text-xs">{inv.paid_at ? formatDate(inv.paid_at) : "—"}</td>
                      <td className="py-3">
                        {inv.status === "paid" && (
                          <Button size="sm" variant="outline" onClick={() => setRefundTarget(inv.id)}>
                            {t("adminBilling.refund")}
                          </Button>
                        )}
                      </td>
                    </tr>
                  )) : (
                    <tr><td colSpan={7} className="py-8 text-center text-muted-foreground">{t("admin.noInvoices")}</td></tr>
                  )}
                </tbody>
              </table>
            </motion.div>
          )}
        </TabsContent>
      </Tabs>

      {/* Cancel Dialog */}
      <AlertDialog open={!!cancelTarget} onOpenChange={(open) => !open && setCancelTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("adminBilling.cancelTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("adminBilling.cancelDesc")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => { if (cancelTarget) cancelSub.mutate(cancelTarget); setCancelTarget(null); }}
            >
              {t("common.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Refund Dialog */}
      <AlertDialog open={!!refundTarget} onOpenChange={(open) => !open && setRefundTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("adminBilling.refundTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("adminBilling.refundDesc")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => { if (refundTarget) refundInv.mutate({ invoice_id: refundTarget }); setRefundTarget(null); }}
            >
              {t("adminBilling.confirmRefund")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default AdminBilling;
