import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CreditCard, Package, ArrowUpCircle } from "lucide-react";
import { motion } from "framer-motion";
import { useSubscription, useInvoices, useMyUpgradeRequests } from "@/hooks/use-api";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";
import { useTranslation } from "react-i18next";

const statusStyle: Record<string, string> = {
  paid: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  pending: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  overdue: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  cancelled: "bg-muted text-muted-foreground border-border hover:bg-muted",
  approved: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  rejected: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
};

const subStatusStyle: Record<string, string> = {
  trial: "bg-info/15 text-info border-info/30 hover:bg-info/15",
  active: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  expired: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  blocked: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
};

const Financial = () => {
  const { t } = useTranslation();
  const { data: subscription, isLoading: subLoading } = useSubscription();
  const { data: invoices, isLoading: invLoading } = useInvoices();
  const { data: upgradeRequests, isLoading: upgradeLoading } = useMyUpgradeRequests();

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "—";
    try { return format(new Date(dateStr), "MMM dd, yyyy"); } catch { return dateStr; }
  };

  const getDaysRemaining = () => {
    if (!subscription) return null;
    const endDate = subscription.trial_end || subscription.current_period_end;
    if (!endDate) return null;
    const days = Math.ceil((new Date(endDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">{t("financial.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("financial.subtitle")}</p>
      </div>

      {subLoading ? (
        <Skeleton className="h-32" />
      ) : subscription ? (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <CreditCard className="w-5 h-5 text-primary" />
              <h2 className="font-semibold">{t("financial.currentSubscription")}</h2>
            </div>
            <Badge className={subStatusStyle[subscription.status] || ""}>
              {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
            </Badge>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground block">{t("financial.plan")}</span>
              <div className="flex items-center gap-1.5">
                <Package className="w-3.5 h-3.5 text-primary" />
                <span className="font-medium">
                  {subscription.plan_name || (subscription.status === "trial" ? t("financial.freeTrial") : t("financial.standard"))}
                </span>
              </div>
            </div>
            <div>
              <span className="text-muted-foreground block">{t("financial.price")}</span>
              <span className="font-mono font-medium">
                ${subscription.plan_price != null ? subscription.plan_price.toFixed(2) : "49.90"}/mo
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">
                {subscription.status === "trial" ? t("financial.trialEnds") : t("financial.nextBilling")}
              </span>
              <span className="font-mono">
                {formatDate(subscription.trial_end || subscription.current_period_end)}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">{t("financial.remaining")}</span>
              <span className="font-mono">
                {getDaysRemaining() !== null ? t("financial.days", { count: getDaysRemaining() }) : "—"}
              </span>
            </div>
          </div>
        </motion.div>
      ) : null}

      {!upgradeLoading && upgradeRequests && upgradeRequests.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="card-glass rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <ArrowUpCircle className="w-5 h-5 text-primary" />
            <h2 className="font-semibold">{t("financial.upgradeRequests")}</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-left border-b border-border">
                  <th className="pb-3 font-medium">{t("financial.from")}</th>
                  <th className="pb-3 font-medium">{t("financial.to")}</th>
                  <th className="pb-3 font-medium">{t("dashboard.balance")}</th>
                  <th className="pb-3 font-medium">{t("financial.status")}</th>
                  <th className="pb-3 font-medium">{t("admin.date")}</th>
                </tr>
              </thead>
              <tbody>
                {upgradeRequests.map((req) => (
                  <tr key={req.id} className="border-b border-border/50 last:border-0">
                    <td className="py-3">{req.current_plan_name || "—"}</td>
                    <td className="py-3 font-medium text-primary">{req.target_plan_name}</td>
                    <td className="py-3 font-mono">${req.mt5_balance.toFixed(2)}</td>
                    <td className="py-3">
                      <Badge className={statusStyle[req.status] || statusStyle.pending}>
                        {req.status.charAt(0).toUpperCase() + req.status.slice(1)}
                      </Badge>
                    </td>
                    <td className="py-3 text-muted-foreground">{formatDate(req.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {invLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card-glass rounded-lg p-6">
          <h2 className="font-semibold mb-4">{t("financial.invoices")}</h2>
          {invoices && invoices.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground text-left border-b border-border">
                    <th className="pb-3 font-medium">{t("financial.issueDate")}</th>
                    <th className="pb-3 font-medium">{t("financial.dueDate")}</th>
                    <th className="pb-3 font-medium">{t("financial.amount")}</th>
                    <th className="pb-3 font-medium">{t("financial.status")}</th>
                    <th className="pb-3 font-medium">{t("financial.paidAt")}</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="border-b border-border/50 last:border-0">
                      <td className="py-3 text-muted-foreground">{formatDate(inv.issue_date)}</td>
                      <td className="py-3 text-muted-foreground">{formatDate(inv.due_date)}</td>
                      <td className="py-3 font-mono">${inv.amount.toFixed(2)}</td>
                      <td className="py-3">
                        <Badge className={statusStyle[inv.status] || ""}>
                          {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="py-3 text-muted-foreground">{inv.paid_at ? formatDate(inv.paid_at) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">{t("financial.noInvoices")}</p>
          )}
        </motion.div>
      )}
    </div>
  );
};

export default Financial;
