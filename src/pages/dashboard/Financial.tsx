import { Badge } from "@/components/ui/badge";
import { CreditCard } from "lucide-react";
import { motion } from "framer-motion";
import { useSubscription, useInvoices } from "@/hooks/use-api";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";

const statusStyle: Record<string, string> = {
  paid: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  pending: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  overdue: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  cancelled: "bg-muted text-muted-foreground border-border hover:bg-muted",
};

const subStatusStyle: Record<string, string> = {
  trial: "bg-info/15 text-info border-info/30 hover:bg-info/15",
  active: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  expired: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  blocked: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
};

const Financial = () => {
  const { data: subscription, isLoading: subLoading } = useSubscription();
  const { data: invoices, isLoading: invLoading } = useInvoices();

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "—";
    try {
      return format(new Date(dateStr), "MMM dd, yyyy");
    } catch {
      return dateStr;
    }
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
        <h1 className="text-2xl font-bold">Financial</h1>
        <p className="text-muted-foreground text-sm">Manage your subscription and invoices</p>
      </div>

      {/* Subscription Card */}
      {subLoading ? (
        <Skeleton className="h-32" />
      ) : subscription ? (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <CreditCard className="w-5 h-5 text-primary" />
              <h2 className="font-semibold">Current Subscription</h2>
            </div>
            <Badge className={subStatusStyle[subscription.status] || ""}>
              {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
            </Badge>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground block">Plan</span>
              <span className="font-medium">
                {subscription.status === "trial" ? "Free Trial" : "Professional"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">Price</span>
              <span className="font-mono font-medium">$49.90/mo</span>
            </div>
            <div>
              <span className="text-muted-foreground block">
                {subscription.status === "trial" ? "Trial Ends" : "Next Billing"}
              </span>
              <span className="font-mono">
                {formatDate(subscription.trial_end || subscription.current_period_end)}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">Remaining</span>
              <span className="font-mono">
                {getDaysRemaining() !== null ? `${getDaysRemaining()} days` : "—"}
              </span>
            </div>
          </div>
        </motion.div>
      ) : null}

      {/* Invoices */}
      {invLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card-glass rounded-lg p-6">
          <h2 className="font-semibold mb-4">Invoices</h2>
          {invoices && invoices.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground text-left border-b border-border">
                    <th className="pb-3 font-medium">Issue Date</th>
                    <th className="pb-3 font-medium">Due Date</th>
                    <th className="pb-3 font-medium">Amount</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Paid At</th>
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
            <p className="text-muted-foreground text-sm">No invoices yet. Your first invoice will be generated before your trial ends.</p>
          )}
        </motion.div>
      )}
    </div>
  );
};

export default Financial;
