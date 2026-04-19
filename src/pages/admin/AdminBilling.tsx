import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { format } from "date-fns";
import {
  DollarSign,
  Users,
  FileText,
  AlertTriangle,
  TrendingUp,
  Clock,
  Search,
  MoreHorizontal,
  CheckCircle2,
  XCircle,
  CalendarPlus,
  StickyNote,
  Eye,
  AlertCircle,
  Receipt,
  Repeat,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  useAdminBillingStats,
  useAdminSubscriptions,
  useAdminInvoices,
  useAdminCancelSubscription,
  useAdminMarkInvoicePaid,
  useAdminCancelInvoice,
  useAdminExtendInvoiceDueDate,
  useAdminAddInvoiceNote,
} from "@/hooks/use-api";
import type { AdminInvoice } from "@/lib/api";

const statusStyle: Record<string, string> = {
  paid: "bg-success/15 text-success border-success/30",
  pending: "bg-warning/15 text-warning border-warning/30",
  overdue: "bg-danger/15 text-danger border-danger/30",
  cancelled: "bg-muted text-muted-foreground border-border",
  active: "bg-success/15 text-success border-success/30",
  trial: "bg-info/15 text-info border-info/30",
  blocked: "bg-danger/15 text-danger border-danger/30",
  expired: "bg-warning/15 text-warning border-warning/30",
};

const safeFormat = (d?: string | null, fmt = "dd MMM yyyy") => {
  if (!d) return "—";
  try {
    return format(new Date(d), fmt);
  } catch {
    return "—";
  }
};

const fmtMoney = (val: number, currency = "BRL") =>
  new Intl.NumberFormat(currency === "BRL" ? "pt-BR" : "en-US", {
    style: "currency",
    currency,
  }).format(val);

const AdminBilling = () => {
  const { t } = useTranslation();

  // ── Data ──
  const { data: stats, isLoading: statsLoading } = useAdminBillingStats();
  const [subFilter, setSubFilter] = useState<string>("");
  const [invStatusFilter, setInvStatusFilter] = useState<string>("");
  const [invProviderFilter, setInvProviderFilter] = useState<string>("");
  const [invPaymentTypeFilter, setInvPaymentTypeFilter] = useState<string>("");
  const [emailSearch, setEmailSearch] = useState<string>("");

  const { data: subs, isLoading: subsLoading } = useAdminSubscriptions(subFilter || undefined);
  const { data: invoices, isLoading: invLoading } = useAdminInvoices(invStatusFilter || undefined);

  // ── Mutations ──
  const cancelSub = useAdminCancelSubscription();
  const markPaid = useAdminMarkInvoicePaid();
  const cancelInv = useAdminCancelInvoice();
  const extendDue = useAdminExtendInvoiceDueDate();
  const addNote = useAdminAddInvoiceNote();

  // ── Local UI state ──
  const [cancelSubTarget, setCancelSubTarget] = useState<string | null>(null);
  const [detailInvoice, setDetailInvoice] = useState<AdminInvoice | null>(null);

  const [markPaidTarget, setMarkPaidTarget] = useState<AdminInvoice | null>(null);
  const [markPaidNote, setMarkPaidNote] = useState("");

  const [cancelInvTarget, setCancelInvTarget] = useState<AdminInvoice | null>(null);
  const [cancelInvNote, setCancelInvNote] = useState("");

  const [extendTarget, setExtendTarget] = useState<AdminInvoice | null>(null);
  const [extendDate, setExtendDate] = useState("");
  const [extendNote, setExtendNote] = useState("");

  const [noteTarget, setNoteTarget] = useState<AdminInvoice | null>(null);
  const [noteText, setNoteText] = useState("");

  // ── Derived ──
  const filteredInvoices = useMemo(() => {
    if (!invoices) return [];
    return invoices.filter((inv) => {
      if (invProviderFilter && inv.provider !== invProviderFilter) return false;
      if (invPaymentTypeFilter === "manual" && !inv.manual_payment) return false;
      if (invPaymentTypeFilter === "auto" && inv.manual_payment) return false;
      if (emailSearch && !(inv.user_email || "").toLowerCase().includes(emailSearch.toLowerCase()))
        return false;
      return true;
    });
  }, [invoices, invProviderFilter, invPaymentTypeFilter, emailSearch]);

  const filteredSubs = useMemo(() => {
    if (!subs) return [];
    return subs.filter((s) =>
      emailSearch ? (s.user_email || "").toLowerCase().includes(emailSearch.toLowerCase()) : true,
    );
  }, [subs, emailSearch]);

  const statCards = [
    { label: t("adminBilling.totalRevenue"), value: stats ? fmtMoney(stats.total_revenue) : "—", icon: DollarSign, color: "text-primary" },
    { label: t("adminBilling.activeSubs"), value: stats?.active_subscriptions ?? 0, icon: Users, color: "text-[hsl(var(--success))]" },
    { label: t("adminBilling.trialSubs"), value: stats?.trial_subscriptions ?? 0, icon: Clock, color: "text-[hsl(var(--info))]" },
    { label: t("adminBilling.blockedSubs"), value: stats?.blocked_subscriptions ?? 0, icon: AlertTriangle, color: "text-[hsl(var(--danger))]" },
    { label: t("adminBilling.pendingInvoices"), value: stats?.pending_invoices ?? 0, icon: FileText, color: "text-[hsl(var(--warning))]" },
    { label: t("adminBilling.overdueInvoices"), value: stats?.overdue_invoices ?? 0, icon: AlertCircle, color: "text-[hsl(var(--danger))]" },
    { label: t("adminBilling.paidThisMonth"), value: stats?.paid_invoices_this_month ?? 0, icon: TrendingUp, color: "text-primary" },
  ];

  const billingDayFromSub = (sub: { next_billing_date?: string | null; current_period_end?: string | null }) => {
    const d = sub.next_billing_date || sub.current_period_end;
    return d ? new Date(d).getDate() : null;
  };

  // ── Action handlers ──
  const handleMarkPaid = () => {
    if (!markPaidTarget) return;
    markPaid.mutate(
      { invoiceId: markPaidTarget.id, note: markPaidNote || undefined },
      {
        onSuccess: () => {
          setMarkPaidTarget(null);
          setMarkPaidNote("");
        },
      },
    );
  };

  const handleCancelInv = () => {
    if (!cancelInvTarget || !cancelInvNote.trim()) return;
    cancelInv.mutate(
      { invoiceId: cancelInvTarget.id, note: cancelInvNote },
      {
        onSuccess: () => {
          setCancelInvTarget(null);
          setCancelInvNote("");
        },
      },
    );
  };

  const handleExtend = () => {
    if (!extendTarget || !extendDate) return;
    const iso = new Date(extendDate).toISOString();
    extendDue.mutate(
      { invoiceId: extendTarget.id, newDueDate: iso, note: extendNote || undefined },
      {
        onSuccess: () => {
          setExtendTarget(null);
          setExtendDate("");
          setExtendNote("");
        },
      },
    );
  };

  const handleAddNote = () => {
    if (!noteTarget || !noteText.trim()) return;
    addNote.mutate(
      { invoiceId: noteTarget.id, note: noteText },
      {
        onSuccess: () => {
          setNoteTarget(null);
          setNoteText("");
        },
      },
    );
  };

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("adminBilling.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("adminBilling.subtitle")}</p>
      </div>

      {/* ── Stats ─────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {statCards.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.03 }}
          >
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

      {/* ── Tabs ─────────────────────────── */}
      <Tabs defaultValue="invoices">
        <TabsList>
          <TabsTrigger value="invoices">{t("adminBilling.invoicesTab")}</TabsTrigger>
          <TabsTrigger value="subscriptions">{t("adminBilling.subsTab")}</TabsTrigger>
        </TabsList>

        {/* ── Invoices tab ─────── */}
        <TabsContent value="invoices" className="space-y-4">
          <Card className="card-glass">
            <CardContent className="p-4 flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder={t("adminBilling.searchByEmail")}
                  value={emailSearch}
                  onChange={(e) => setEmailSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={invStatusFilter || "all"} onValueChange={(v) => setInvStatusFilter(v === "all" ? "" : v)}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder={t("adminBilling.filterByStatus")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("adminBilling.all")}</SelectItem>
                  <SelectItem value="paid">{t("adminBilling.paid")}</SelectItem>
                  <SelectItem value="pending">{t("adminBilling.pendingStatus")}</SelectItem>
                  <SelectItem value="overdue">{t("adminBilling.overdueStatus")}</SelectItem>
                  <SelectItem value="cancelled">{t("adminBilling.cancel")}</SelectItem>
                </SelectContent>
              </Select>
              <Select value={invProviderFilter || "all"} onValueChange={(v) => setInvProviderFilter(v === "all" ? "" : v)}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder={t("adminBilling.filterByProvider")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("adminBilling.all")}</SelectItem>
                  <SelectItem value="asaas">Asaas</SelectItem>
                  <SelectItem value="stripe">Stripe</SelectItem>
                  <SelectItem value="mercadopago">MercadoPago</SelectItem>
                  <SelectItem value="celcoin">Celcoin</SelectItem>
                </SelectContent>
              </Select>
              <Select value={invPaymentTypeFilter || "all"} onValueChange={(v) => setInvPaymentTypeFilter(v === "all" ? "" : v)}>
                <SelectTrigger className="w-44">
                  <SelectValue placeholder={t("adminBilling.filterByPayment")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("adminBilling.all")}</SelectItem>
                  <SelectItem value="auto">{t("adminBilling.automatic")}</SelectItem>
                  <SelectItem value="manual">{t("adminBilling.manualPayment")}</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {invLoading ? (
            <Skeleton className="h-64" />
          ) : (
            <Card className="card-glass">
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("adminBilling.client")}</TableHead>
                      <TableHead>{t("financial.plan")}</TableHead>
                      <TableHead>{t("adminBilling.amountColumn")}</TableHead>
                      <TableHead>{t("adminBilling.statusColumn")}</TableHead>
                      <TableHead>{t("adminBilling.issueColumn")}</TableHead>
                      <TableHead>{t("adminBilling.dueColumn")}</TableHead>
                      <TableHead>{t("adminBilling.payColumn")}</TableHead>
                      <TableHead>{t("adminBilling.providerColumn")}</TableHead>
                      <TableHead className="text-right">{t("adminBilling.actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredInvoices.length > 0 ? (
                      filteredInvoices.map((inv) => (
                        <TableRow key={inv.id}>
                          <TableCell className="text-sm">{inv.user_email || "—"}</TableCell>
                          <TableCell className="text-sm">{inv.plan_name || "—"}</TableCell>
                          <TableCell className="font-mono">{fmtMoney(inv.amount, inv.currency)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Badge className={statusStyle[inv.status] || ""}>{inv.status}</Badge>
                              {inv.manual_payment && (
                                <Badge variant="outline" className="text-xs">
                                  {t("adminBilling.manualPayment")}
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-muted-foreground font-mono text-xs">
                            {safeFormat(inv.issue_date)}
                          </TableCell>
                          <TableCell className="text-muted-foreground font-mono text-xs">
                            {safeFormat(inv.due_date)}
                          </TableCell>
                          <TableCell className="text-muted-foreground font-mono text-xs">
                            {safeFormat(inv.paid_at)}
                          </TableCell>
                          <TableCell className="text-xs capitalize">{inv.provider || "—"}</TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <MoreHorizontal className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-56">
                                <DropdownMenuItem onClick={() => setDetailInvoice(inv)}>
                                  <Eye className="w-4 h-4 mr-2" />
                                  {t("adminBilling.viewDetails")}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {(inv.status === "pending" || inv.status === "overdue") && (
                                  <>
                                    <DropdownMenuItem onClick={() => setMarkPaidTarget(inv)}>
                                      <CheckCircle2 className="w-4 h-4 mr-2 text-success" />
                                      {t("adminBilling.markAsPaid")}
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => { setExtendTarget(inv); setExtendDate(inv.due_date.slice(0, 10)); }}>
                                      <CalendarPlus className="w-4 h-4 mr-2" />
                                      {t("adminBilling.extendDueDate")}
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => setCancelInvTarget(inv)} className="text-destructive">
                                      <XCircle className="w-4 h-4 mr-2" />
                                      {t("adminBilling.cancelInvoice")}
                                    </DropdownMenuItem>
                                  </>
                                )}
                                <DropdownMenuItem onClick={() => setNoteTarget(inv)}>
                                  <StickyNote className="w-4 h-4 mr-2" />
                                  {t("adminBilling.addNote")}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={9} className="py-10 text-center text-muted-foreground text-sm">
                          {t("admin.noInvoices")}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ── Subscriptions tab ─────── */}
        <TabsContent value="subscriptions" className="space-y-4">
          <Card className="card-glass">
            <CardContent className="p-4 flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder={t("adminBilling.searchByEmail")}
                  value={emailSearch}
                  onChange={(e) => setEmailSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={subFilter || "all"} onValueChange={(v) => setSubFilter(v === "all" ? "" : v)}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder={t("adminBilling.filterByStatus")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("adminBilling.all")}</SelectItem>
                  <SelectItem value="active">{t("common.active")}</SelectItem>
                  <SelectItem value="trial">{t("adminBilling.trial")}</SelectItem>
                  <SelectItem value="blocked">{t("adminBilling.blocked")}</SelectItem>
                  <SelectItem value="expired">{t("adminBilling.expired")}</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {subsLoading ? (
            <Skeleton className="h-64" />
          ) : (
            <Card className="card-glass">
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("admin.user")}</TableHead>
                      <TableHead>{t("financial.plan")}</TableHead>
                      <TableHead>{t("financial.status")}</TableHead>
                      <TableHead>{t("adminBilling.billingDay")}</TableHead>
                      <TableHead>{t("financial.nextBilling")}</TableHead>
                      <TableHead>{t("admin.created")}</TableHead>
                      <TableHead className="text-right">{t("common.actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredSubs.length > 0 ? (
                      filteredSubs.map((s) => {
                        const day = billingDayFromSub(s);
                        return (
                          <TableRow key={s.id}>
                            <TableCell className="text-sm">{s.user_email}</TableCell>
                            <TableCell className="font-medium">{s.plan_name || "—"}</TableCell>
                            <TableCell>
                              <Badge className={statusStyle[s.status] || ""}>{s.status}</Badge>
                            </TableCell>
                            <TableCell className="text-xs">
                              {day ? (
                                <span className="inline-flex items-center gap-1">
                                  <Repeat className="w-3 h-3 text-primary" />
                                  {t("financial.billingDayValue", { day })}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </TableCell>
                            <TableCell className="text-muted-foreground font-mono text-xs">
                              {safeFormat(s.next_billing_date || s.current_period_end)}
                            </TableCell>
                            <TableCell className="text-muted-foreground font-mono text-xs">
                              {safeFormat(s.created_at)}
                            </TableCell>
                            <TableCell className="text-right">
                              {s.status !== "blocked" && (
                                <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setCancelSubTarget(s.id)}>
                                  {t("adminBilling.cancel")}
                                </Button>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })
                    ) : (
                      <TableRow>
                        <TableCell colSpan={7} className="py-10 text-center text-muted-foreground text-sm">
                          {t("admin.noSubscriptions")}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* ── Cancel subscription confirm ─── */}
      <AlertDialog open={!!cancelSubTarget} onOpenChange={(o) => !o && setCancelSubTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("adminBilling.cancelTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("adminBilling.cancelDesc")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (cancelSubTarget) cancelSub.mutate(cancelSubTarget);
                setCancelSubTarget(null);
              }}
            >
              {t("common.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── Mark as paid dialog ─── */}
      <Dialog open={!!markPaidTarget} onOpenChange={(o) => !o && setMarkPaidTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("adminBilling.markAsPaid")}</DialogTitle>
            <DialogDescription>{markPaidTarget?.user_email}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>{t("adminBilling.internalNote")}</Label>
            <Textarea
              placeholder={t("adminBilling.notePlaceholder")}
              value={markPaidNote}
              onChange={(e) => setMarkPaidNote(e.target.value)}
              rows={4}
            />
            <p className="text-xs text-muted-foreground">{t("adminBilling.notePlaceholderOptional")}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMarkPaidTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleMarkPaid} disabled={markPaid.isPending}>
              {t("adminBilling.confirmMarkPaid")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Cancel invoice dialog ─── */}
      <Dialog open={!!cancelInvTarget} onOpenChange={(o) => !o && setCancelInvTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("adminBilling.cancelInvoice")}</DialogTitle>
            <DialogDescription>{cancelInvTarget?.user_email}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>
              {t("adminBilling.internalNote")} <span className="text-destructive">*</span>
            </Label>
            <Textarea
              placeholder={t("adminBilling.notePlaceholder")}
              value={cancelInvNote}
              onChange={(e) => setCancelInvNote(e.target.value)}
              rows={4}
            />
            <p className="text-xs text-muted-foreground">{t("adminBilling.addNoteRequired")}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelInvTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleCancelInv}
              disabled={cancelInv.isPending || !cancelInvNote.trim()}
            >
              {t("adminBilling.confirmCancel")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Extend due date dialog ─── */}
      <Dialog open={!!extendTarget} onOpenChange={(o) => !o && setExtendTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("adminBilling.extendDueDate")}</DialogTitle>
            <DialogDescription>{extendTarget?.user_email}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>{t("adminBilling.newDueDate")}</Label>
            <Input type="date" value={extendDate} onChange={(e) => setExtendDate(e.target.value)} />
            <Label>{t("adminBilling.internalNote")}</Label>
            <Textarea
              placeholder={t("adminBilling.notePlaceholderOptional")}
              value={extendNote}
              onChange={(e) => setExtendNote(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExtendTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleExtend} disabled={extendDue.isPending || !extendDate}>
              {t("adminBilling.confirmExtend")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Add note dialog ─── */}
      <Dialog open={!!noteTarget} onOpenChange={(o) => !o && setNoteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("adminBilling.addNote")}</DialogTitle>
            <DialogDescription>{noteTarget?.user_email}</DialogDescription>
          </DialogHeader>
          <Textarea
            placeholder={t("adminBilling.notePlaceholder")}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={5}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoteTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleAddNote} disabled={addNote.isPending || !noteText.trim()}>
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Invoice detail sheet ─── */}
      <Sheet open={!!detailInvoice} onOpenChange={(o) => !o && setDetailInvoice(null)}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Receipt className="w-5 h-5 text-primary" />
              {t("adminBilling.invoiceDetails")}
            </SheetTitle>
            <SheetDescription className="font-mono text-xs">
              {detailInvoice?.id}
            </SheetDescription>
          </SheetHeader>

          {detailInvoice && (
            <div className="mt-6 space-y-6 text-sm">
              {/* Header summary */}
              <div className="flex items-start justify-between gap-3 pb-4 border-b border-border/50">
                <div>
                  <div className="text-xs text-muted-foreground">{t("adminBilling.client")}</div>
                  <div className="font-medium">{detailInvoice.user_email}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {detailInvoice.plan_name || "—"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono font-bold text-xl">
                    {fmtMoney(detailInvoice.amount, detailInvoice.currency)}
                  </div>
                  <Badge className={`${statusStyle[detailInvoice.status]} mt-1`}>
                    {detailInvoice.status}
                  </Badge>
                </div>
              </div>

              {/* Origin badge */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{t("adminBilling.originBadge")}:</span>
                {detailInvoice.manual_payment ? (
                  <Badge variant="outline" className="bg-warning/10 border-warning/30 text-warning">
                    {t("adminBilling.manualBaixa")}
                  </Badge>
                ) : (
                  <Badge variant="outline">{t("adminBilling.autoBaixa")}</Badge>
                )}
              </div>

              {/* Grid info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">{t("adminBilling.issueColumn")}</div>
                  <div className="font-mono text-xs">{safeFormat(detailInvoice.issue_date, "dd MMM yyyy HH:mm")}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">{t("adminBilling.dueColumn")}</div>
                  <div className="font-mono text-xs">{safeFormat(detailInvoice.due_date)}</div>
                  {detailInvoice.original_due_date && (
                    <div className="text-[10px] text-muted-foreground mt-0.5">
                      orig: {safeFormat(detailInvoice.original_due_date)}
                    </div>
                  )}
                </div>
                {detailInvoice.paid_at && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">{t("adminBilling.paidOn")}</div>
                    <div className="font-mono text-xs">{safeFormat(detailInvoice.paid_at, "dd MMM yyyy HH:mm")}</div>
                  </div>
                )}
                {detailInvoice.cancelled_at && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">{t("adminBilling.cancelledOn")}</div>
                    <div className="font-mono text-xs">{safeFormat(detailInvoice.cancelled_at, "dd MMM yyyy HH:mm")}</div>
                  </div>
                )}
                <div>
                  <div className="text-xs text-muted-foreground mb-1">{t("adminBilling.providerColumn")}</div>
                  <div className="text-xs capitalize">{detailInvoice.provider || "—"}</div>
                </div>
                {detailInvoice.external_id && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">External ID</div>
                    <div className="font-mono text-[10px] break-all">{detailInvoice.external_id}</div>
                  </div>
                )}
              </div>

              {/* Timeline */}
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wide mb-3">
                  {t("adminBilling.timeline")}
                </div>
                <div className="space-y-3 border-l-2 border-border pl-4 ml-2">
                  <div className="relative">
                    <div className="absolute -left-[22px] top-1 w-3 h-3 rounded-full bg-info" />
                    <div className="text-xs">
                      <span className="font-medium">{t("adminBilling.issued")}</span>
                      <span className="text-muted-foreground ml-2 font-mono">
                        {safeFormat(detailInvoice.issue_date, "dd MMM yyyy HH:mm")}
                      </span>
                    </div>
                  </div>

                  <div className="relative">
                    <div className="absolute -left-[22px] top-1 w-3 h-3 rounded-full bg-warning" />
                    <div className="text-xs">
                      <span className="font-medium">{t("adminBilling.due")}</span>
                      <span className="text-muted-foreground ml-2 font-mono">
                        {safeFormat(detailInvoice.due_date)}
                      </span>
                    </div>
                  </div>

                  {detailInvoice.original_due_date && (
                    <div className="relative">
                      <div className="absolute -left-[22px] top-1 w-3 h-3 rounded-full bg-primary" />
                      <div className="text-xs">
                        <span className="font-medium">{t("adminBilling.extendedDue")}</span>
                      </div>
                    </div>
                  )}

                  {detailInvoice.paid_at && (
                    <div className="relative">
                      <div className="absolute -left-[22px] top-1 w-3 h-3 rounded-full bg-success" />
                      <div className="text-xs">
                        <span className="font-medium">{t("adminBilling.paidOn")}</span>
                        <span className="text-muted-foreground ml-2 font-mono">
                          {safeFormat(detailInvoice.paid_at, "dd MMM yyyy HH:mm")}
                        </span>
                        {detailInvoice.manual_payment && detailInvoice.manual_payment_by && (
                          <div className="text-[10px] text-muted-foreground mt-0.5">
                            {t("adminBilling.manualMarkBy", { by: detailInvoice.manual_payment_by })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {detailInvoice.cancelled_at && (
                    <div className="relative">
                      <div className="absolute -left-[22px] top-1 w-3 h-3 rounded-full bg-destructive" />
                      <div className="text-xs">
                        <span className="font-medium">{t("adminBilling.cancelledOn")}</span>
                        <span className="text-muted-foreground ml-2 font-mono">
                          {safeFormat(detailInvoice.cancelled_at, "dd MMM yyyy HH:mm")}
                        </span>
                        {detailInvoice.cancelled_by && (
                          <div className="text-[10px] text-muted-foreground mt-0.5">
                            by {detailInvoice.cancelled_by}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Internal notes */}
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                  {t("adminBilling.internalNote")}
                </div>
                {detailInvoice.admin_notes ? (
                  <pre className="text-xs whitespace-pre-wrap rounded-md bg-muted/30 border border-border/50 p-3 font-mono">
                    {detailInvoice.admin_notes}
                  </pre>
                ) : (
                  <p className="text-xs text-muted-foreground italic">{t("adminBilling.noNotes")}</p>
                )}
              </div>

              {/* Quick actions */}
              <div className="flex flex-wrap gap-2 pt-2 border-t border-border/50">
                {(detailInvoice.status === "pending" || detailInvoice.status === "overdue") && (
                  <>
                    <Button size="sm" variant="outline" onClick={() => { setDetailInvoice(null); setMarkPaidTarget(detailInvoice); }}>
                      <CheckCircle2 className="w-4 h-4 mr-1.5" />
                      {t("adminBilling.markAsPaid")}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => { setDetailInvoice(null); setExtendTarget(detailInvoice); setExtendDate(detailInvoice.due_date.slice(0, 10)); }}>
                      <CalendarPlus className="w-4 h-4 mr-1.5" />
                      {t("adminBilling.extendDueDate")}
                    </Button>
                    <Button size="sm" variant="outline" className="text-destructive" onClick={() => { setDetailInvoice(null); setCancelInvTarget(detailInvoice); }}>
                      <XCircle className="w-4 h-4 mr-1.5" />
                      {t("adminBilling.cancelInvoice")}
                    </Button>
                  </>
                )}
                <Button size="sm" variant="outline" onClick={() => { setDetailInvoice(null); setNoteTarget(detailInvoice); }}>
                  <StickyNote className="w-4 h-4 mr-1.5" />
                  {t("adminBilling.addNote")}
                </Button>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
};

export default AdminBilling;
