import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { format } from "date-fns";
import {
  CreditCard,
  Package,
  ArrowUpCircle,
  Calendar,
  Repeat,
  AlertCircle,
  CheckCircle2,
  Clock,
  XCircle,
  FileText,
  Receipt,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useSubscription, useInvoices, useMyUpgradeRequests } from "@/hooks/use-api";
import type { Invoice } from "@/lib/api";

const subStatusStyle: Record<string, string> = {
  trial: "bg-info/15 text-info border-info/30",
  active: "bg-success/15 text-success border-success/30",
  expired: "bg-warning/15 text-warning border-warning/30",
  blocked: "bg-danger/15 text-danger border-danger/30",
};

const invStatusStyle: Record<string, string> = {
  paid: "bg-success/15 text-success border-success/30",
  pending: "bg-warning/15 text-warning border-warning/30",
  overdue: "bg-danger/15 text-danger border-danger/30",
  cancelled: "bg-muted text-muted-foreground border-border",
};

const invStatusIcon: Record<string, typeof CheckCircle2> = {
  paid: CheckCircle2,
  pending: Clock,
  overdue: AlertCircle,
  cancelled: XCircle,
};

const safeFormat = (d?: string | null, fmt = "dd MMM yyyy") => {
  if (!d) return "—";
  try {
    return format(new Date(d), fmt);
  } catch {
    return "—";
  }
};

const Financial = () => {
  const { t } = useTranslation();
  const { data: subscription, isLoading: subLoading } = useSubscription();
  const { data: invoices, isLoading: invLoading } = useInvoices();
  const { data: upgradeRequests, isLoading: upgradeLoading } = useMyUpgradeRequests();

  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);

  const billingInfo = useMemo(() => {
    if (!subscription) return null;
    const next = subscription.next_billing_date || subscription.current_period_end;
    const billingDay = next ? new Date(next).getDate() : null;
    const last = subscription.current_period_start;
    return { next, last, billingDay };
  }, [subscription]);

  const openInvoice = useMemo(
    () => invoices?.find((inv) => inv.status === "pending" || inv.status === "overdue"),
    [invoices],
  );

  const getDaysRemaining = () => {
    if (!subscription) return null;
    const endDate = subscription.trial_end || subscription.current_period_end;
    if (!endDate) return null;
    const days = Math.ceil((new Date(endDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  };

  const currency = subscription?.plan_currency || "USD";
  const formatMoney = (val: number) =>
    new Intl.NumberFormat(currency === "BRL" ? "pt-BR" : "en-US", {
      style: "currency",
      currency,
    }).format(val);

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("financial.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("financial.subtitle")}</p>
      </div>

      {/* ── Subscription summary card ─────────────────── */}
      {subLoading ? (
        <Skeleton className="h-44" />
      ) : subscription ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="card-glass rounded-xl p-6"
        >
          <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <CreditCard className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-semibold text-base">{t("financial.currentSubscription")}</h2>
                <p className="text-xs text-muted-foreground">
                  {subscription.plan_name || t("financial.standard")}
                </p>
              </div>
            </div>
            <Badge className={subStatusStyle[subscription.status] || ""}>
              {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
            </Badge>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 text-sm">
            <div>
              <span className="text-muted-foreground text-xs uppercase tracking-wide block mb-1">
                {t("financial.plan")}
              </span>
              <div className="flex items-center gap-1.5">
                <Package className="w-3.5 h-3.5 text-primary" />
                <span className="font-medium">
                  {subscription.plan_name ||
                    (subscription.status === "trial"
                      ? t("financial.freeTrial")
                      : t("financial.standard"))}
                </span>
              </div>
            </div>
            <div>
              <span className="text-muted-foreground text-xs uppercase tracking-wide block mb-1">
                {t("financial.price")}
              </span>
              <span className="font-mono font-medium">
                {subscription.plan_price != null
                  ? `${formatMoney(subscription.plan_price)}/mo`
                  : "—"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground text-xs uppercase tracking-wide block mb-1">
                {subscription.status === "trial"
                  ? t("financial.trialEnds")
                  : t("financial.nextBilling")}
              </span>
              <span className="font-mono">
                {safeFormat(subscription.trial_end || subscription.current_period_end)}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground text-xs uppercase tracking-wide block mb-1">
                {t("financial.remaining")}
              </span>
              <span className="font-mono">
                {getDaysRemaining() !== null
                  ? t("financial.days", { count: getDaysRemaining()! })
                  : "—"}
              </span>
            </div>
          </div>

          {/* Recurrence band */}
          {billingInfo?.billingDay && (
            <div className="mt-5 pt-5 border-t border-border/50 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <Repeat className="w-4 h-4 text-primary" />
                <div>
                  <div className="text-xs text-muted-foreground">{t("financial.recurrence")}</div>
                  <div className="font-medium">
                    {t("financial.billingDayValue", { day: billingInfo.billingDay })}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-muted-foreground" />
                <div>
                  <div className="text-xs text-muted-foreground">{t("financial.lastIssue")}</div>
                  <div className="font-mono text-xs">{safeFormat(billingInfo.last)}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-primary" />
                <div>
                  <div className="text-xs text-muted-foreground">{t("financial.nextIssue")}</div>
                  <div className="font-mono text-xs">{safeFormat(billingInfo.next)}</div>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      ) : null}

      {/* ── Open invoice highlight ─────────────────── */}
      {openInvoice && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-warning/30 bg-warning/5 p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-sm">{t("financial.openInvoiceTitle")}</div>
              <div className="text-xs text-muted-foreground">
                {t("financial.openInvoiceDesc", { date: safeFormat(openInvoice.due_date) })}
              </div>
            </div>
          </div>
          <Button size="sm" variant="outline" onClick={() => setSelectedInvoice(openInvoice)}>
            {t("financial.viewDetails")}
          </Button>
        </motion.div>
      )}

      {/* ── Upgrade requests ─────────────────── */}
      {!upgradeLoading && upgradeRequests && upgradeRequests.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="card-glass rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-4">
            <ArrowUpCircle className="w-5 h-5 text-primary" />
            <h2 className="font-semibold">{t("financial.upgradeRequests")}</h2>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("financial.from")}</TableHead>
                <TableHead>{t("financial.to")}</TableHead>
                <TableHead>{t("financial.status")}</TableHead>
                <TableHead className="text-right">{t("financial.issueDate")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {upgradeRequests.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.current_plan_name || "—"}</TableCell>
                  <TableCell className="font-medium text-primary">{r.target_plan_name}</TableCell>
                  <TableCell>
                    <Badge className={invStatusStyle[r.status] || ""}>{r.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground font-mono text-xs">
                    {safeFormat(r.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </motion.div>
      )}

      {/* ── Invoice history ─────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="card-glass rounded-xl p-6"
      >
        <div className="flex items-center gap-3 mb-4">
          <Receipt className="w-5 h-5 text-primary" />
          <h2 className="font-semibold">{t("financial.invoices")}</h2>
        </div>

        {invLoading ? (
          <Skeleton className="h-48" />
        ) : invoices && invoices.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("financial.issueDate")}</TableHead>
                <TableHead>{t("financial.dueDate")}</TableHead>
                <TableHead>{t("financial.amount")}</TableHead>
                <TableHead>{t("financial.status")}</TableHead>
                <TableHead>{t("financial.paidAt")}</TableHead>
                <TableHead className="text-right">{t("common.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((inv) => {
                const Icon = invStatusIcon[inv.status] || Clock;
                return (
                  <TableRow key={inv.id} className="cursor-pointer" onClick={() => setSelectedInvoice(inv)}>
                    <TableCell className="text-muted-foreground font-mono text-xs">
                      {safeFormat(inv.issue_date)}
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs">
                      {safeFormat(inv.due_date)}
                    </TableCell>
                    <TableCell className="font-mono font-medium">
                      {new Intl.NumberFormat(inv.currency === "BRL" ? "pt-BR" : "en-US", {
                        style: "currency",
                        currency: inv.currency,
                      }).format(inv.amount)}
                    </TableCell>
                    <TableCell>
                      <Badge className={`${invStatusStyle[inv.status] || ""} gap-1`}>
                        <Icon className="w-3 h-3" />
                        {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs">
                      {safeFormat(inv.paid_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); setSelectedInvoice(inv); }}>
                        {t("financial.viewDetails")}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        ) : (
          <div className="text-center py-10 text-muted-foreground text-sm">
            <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
            {t("financial.noInvoices")}
          </div>
        )}
      </motion.div>

      {/* ── Invoice detail sheet ─────────────────── */}
      <Sheet open={!!selectedInvoice} onOpenChange={(o) => !o && setSelectedInvoice(null)}>
        <SheetContent className="w-full sm:max-w-md overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{t("financial.invoices")}</SheetTitle>
            <SheetDescription>
              {selectedInvoice?.id?.slice(0, 8)}…
            </SheetDescription>
          </SheetHeader>

          {selectedInvoice && (
            <div className="mt-6 space-y-5 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">{t("financial.amount")}</div>
                  <div className="font-mono font-semibold text-lg">
                    {new Intl.NumberFormat(selectedInvoice.currency === "BRL" ? "pt-BR" : "en-US", {
                      style: "currency",
                      currency: selectedInvoice.currency,
                    }).format(selectedInvoice.amount)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">{t("financial.status")}</div>
                  <Badge className={invStatusStyle[selectedInvoice.status] || ""}>
                    {selectedInvoice.status}
                  </Badge>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">{t("financial.issueDate")}</div>
                  <div className="font-mono text-xs">{safeFormat(selectedInvoice.issue_date, "dd MMM yyyy HH:mm")}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">{t("financial.dueDate")}</div>
                  <div className="font-mono text-xs">{safeFormat(selectedInvoice.due_date, "dd MMM yyyy")}</div>
                </div>
                {selectedInvoice.paid_at && (
                  <div className="col-span-2">
                    <div className="text-xs text-muted-foreground mb-1">{t("financial.paidAt")}</div>
                    <div className="font-mono text-xs">{safeFormat(selectedInvoice.paid_at, "dd MMM yyyy HH:mm")}</div>
                  </div>
                )}
                {selectedInvoice.provider && (
                  <div className="col-span-2">
                    <div className="text-xs text-muted-foreground mb-1">{t("financial.provider")}</div>
                    <Badge variant="outline" className="capitalize">{selectedInvoice.provider}</Badge>
                    {selectedInvoice.manual_payment && (
                      <Badge variant="outline" className="ml-2">{t("financial.manual")}</Badge>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
};

export default Financial;
