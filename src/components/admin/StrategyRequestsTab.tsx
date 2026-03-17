import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Check, X } from "lucide-react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  useAdminStrategyRequests,
  useAdminApproveStrategyRequest,
  useAdminRejectStrategyRequest,
} from "@/hooks/use-api";

const statusStyle: Record<string, string> = {
  pending: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  approved: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  rejected: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
};

export function StrategyRequestsTab() {
  const { t } = useTranslation();
  const [statusFilter, setStatusFilter] = useState("");
  const { data: requests, isLoading } = useAdminStrategyRequests(statusFilter || undefined);
  const approveMutation = useAdminApproveStrategyRequest();
  const rejectMutation = useAdminRejectStrategyRequest();
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectNote, setRejectNote] = useState("");

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    try { return new Date(d).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); } catch { return d; }
  };

  if (isLoading) return <Skeleton className="h-48" />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("strategyRequests.subtitle")}</p>

      <div className="flex gap-2">
        {["", "pending", "approved", "rejected"].map((s) => (
          <Button key={s} variant={statusFilter === s ? "default" : "outline"} size="sm" onClick={() => setStatusFilter(s)} className="text-xs">
            {s ? t(`strategyRequests.${s}`) : t("common.all")}
          </Button>
        ))}
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                <th className="p-3 font-medium">{t("strategyRequests.user")}</th>
                <th className="p-3 font-medium">{t("strategyRequests.mt5Account")}</th>
                <th className="p-3 font-medium">{t("strategyRequests.currentStrategy")}</th>
                <th className="p-3 font-medium">{t("strategyRequests.targetStrategy")}</th>
                <th className="p-3 font-medium">{t("strategyRequests.capital")}</th>
                <th className="p-3 font-medium">{t("financial.status")}</th>
                <th className="p-3 font-medium">{t("strategyRequests.date")}</th>
                <th className="p-3 font-medium">{t("common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {requests?.map((req) => (
                <tr key={req.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                  <td className="p-3">{req.user_email}</td>
                  <td className="p-3 font-mono text-xs">{req.mt5_logins.join(", ") || "—"}</td>
                  <td className="p-3">{req.current_strategy || <span className="text-muted-foreground">—</span>}</td>
                  <td className="p-3 font-medium text-primary">{req.target_strategy}</td>
                  <td className="p-3 font-mono">R$ {req.mt5_balance.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3"><Badge className={statusStyle[req.status] || ""}>{t(`strategyRequests.${req.status}`)}</Badge></td>
                  <td className="p-3 text-muted-foreground text-xs">{formatDate(req.created_at)}</td>
                  <td className="p-3">
                    {req.status === "pending" ? (
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs gap-1 text-success hover:text-success"
                          onClick={() => approveMutation.mutate(req.id)}
                          disabled={approveMutation.isPending}
                        >
                          <Check className="w-3 h-3" /> {t("admin.approve")}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs gap-1 text-danger hover:text-danger"
                          onClick={() => { setRejectingId(req.id); setRejectNote(""); }}
                          disabled={rejectMutation.isPending}
                        >
                          <X className="w-3 h-3" /> {t("admin.reject")}
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">{req.admin_note || "—"}</span>
                    )}
                  </td>
                </tr>
              ))}
              {(!requests || requests.length === 0) && (
                <tr><td colSpan={8} className="p-6 text-center text-muted-foreground">{t("strategyRequests.noRequests")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Reject modal */}
      <Dialog open={!!rejectingId} onOpenChange={(open) => !open && setRejectingId(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{t("strategyRequests.rejectTitle")}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{t("strategyRequests.rejectDescription")}</p>
            <Textarea
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
              placeholder={t("strategyRequests.rejectPlaceholder")}
              className="bg-secondary min-h-[80px]"
            />
            <Button
              onClick={() => {
                if (rejectingId) {
                  rejectMutation.mutate({ requestId: rejectingId, note: rejectNote }, {
                    onSuccess: () => setRejectingId(null),
                  });
                }
              }}
              disabled={rejectMutation.isPending}
              variant="destructive"
              className="w-full"
            >
              {rejectMutation.isPending ? t("common.loading") : t("strategyRequests.confirmReject")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
