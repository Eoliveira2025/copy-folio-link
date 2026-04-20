import { useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ShieldCheck, RefreshCcw, AlertCircle, CheckCircle2, XCircle, Info } from "lucide-react";
import { useAdminRecoveries, useAdminRecoveriesSummary } from "@/hooks/use-api";
import type { CopyRecovery } from "@/lib/api";

const statusStyle: Record<string, string> = {
  failed_retryable: "bg-warning/15 text-warning border-warning/30",
  retried_success: "bg-success/15 text-success border-success/30",
  retried_rejected: "bg-danger/15 text-danger border-danger/30",
  close_retrying: "bg-info/15 text-info border-info/30",
  close_retry_success: "bg-success/15 text-success border-success/30",
  close_retry_failed: "bg-danger/15 text-danger border-danger/30",
  no_position_to_close: "bg-muted text-muted-foreground border-border",
};

const statusKey: Record<string, string> = {
  failed_retryable: "operations.statusFailedRetryable",
  retried_success: "operations.statusRetriedSuccess",
  retried_rejected: "operations.statusRetriedRejected",
  close_retrying: "operations.statusCloseRetrying",
  close_retry_success: "operations.statusCloseRetrySuccess",
  close_retry_failed: "operations.statusCloseRetryFailed",
  no_position_to_close: "operations.statusNoPosition",
};

const RecoveriesPanel = () => {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<"" | "open_recovery" | "close_recovery">("");
  const { data: rows, isLoading } = useAdminRecoveries({ recovery_type: filter || undefined, limit: 200 });
  const { data: summary } = useAdminRecoveriesSummary();

  const renderReason = (r: CopyRecovery) => {
    if (r.reason_code === "no_position_to_close") return t("operations.msgNoPosition");
    if (r.reason_code === "manually_closed_by_user_possible") return t("operations.msgManualClose");
    if (r.reason_code === "retry_rejected_favorable_move") return t("operations.msgFavorableMove");
    if (r.reason_code === "retry_success" && r.recovery_type === "open_recovery")
      return t("operations.msgRetrySuccess");
    if (r.reason_code === "close_retry_success") return t("operations.msgCloseSuccess");
    if (r.reason_code === "insufficient_margin") return t("operations.msgInsufficientMargin");
    return r.reason_code || "—";
  };

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <ShieldCheck className="w-5 h-5 text-primary" /> {t("operations.recoveriesTitle")}
      </h2>
      <p className="text-muted-foreground text-sm mb-3">{t("operations.recoveriesSubtitle")}</p>

      {/* KPIs */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4">
          <KpiCard icon={<RefreshCcw className="w-4 h-4 text-warning" />} label={t("operations.kpiReprocessing")} value={summary.reprocessing} />
          <KpiCard icon={<CheckCircle2 className="w-4 h-4 text-success" />} label={t("operations.kpiSuccess")} value={summary.retried_success + summary.close_retry_success} />
          <KpiCard icon={<XCircle className="w-4 h-4 text-danger" />} label={t("operations.kpiRejected")} value={summary.retried_rejected + summary.close_retry_failed} />
          <KpiCard icon={<RefreshCcw className="w-4 h-4 text-info" />} label={t("operations.kpiCloseRetrying")} value={summary.close_retrying} />
          <KpiCard icon={<Info className="w-4 h-4 text-muted-foreground" />} label={t("operations.kpiNoPosition")} value={summary.no_position} />
          <KpiCard icon={<AlertCircle className="w-4 h-4 text-primary" />} label={t("operations.kpiLast24h")} value={summary.last_24h} />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-3">
        <Button size="sm" variant={filter === "" ? "default" : "outline"} onClick={() => setFilter("")}>
          {t("operations.filterAll")}
        </Button>
        <Button size="sm" variant={filter === "open_recovery" ? "default" : "outline"} onClick={() => setFilter("open_recovery")}>
          {t("operations.filterOpen")}
        </Button>
        <Button size="sm" variant={filter === "close_recovery" ? "default" : "outline"} onClick={() => setFilter("close_recovery")}>
          {t("operations.filterClose")}
        </Button>
      </div>

      {isLoading ? (
        <Skeleton className="h-64" />
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                  <th className="p-3 font-medium">{t("financial.date") || "Data"}</th>
                  <th className="p-3 font-medium">{t("operations.userColumn")}</th>
                  <th className="p-3 font-medium">{t("operations.accountColumn")}</th>
                  <th className="p-3 font-medium">{t("operations.symbol")}</th>
                  <th className="p-3 font-medium">{t("operations.recoveryType")}</th>
                  <th className="p-3 font-medium">{t("operations.action")}</th>
                  <th className="p-3 font-medium text-right">{t("operations.originalPrice")}</th>
                  <th className="p-3 font-medium text-right">{t("operations.currentPrice")}</th>
                  <th className="p-3 font-medium text-center">{t("operations.attempt")}</th>
                  <th className="p-3 font-medium">{t("financial.status")}</th>
                  <th className="p-3 font-medium">{t("operations.reason")}</th>
                  <th className="p-3 font-medium">{t("operations.retcode")}</th>
                </tr>
              </thead>
              <tbody>
                {rows?.map((r) => (
                  <tr key={r.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                    <td className="p-3 font-mono text-xs whitespace-nowrap">
                      {new Date(r.decided_at).toLocaleString()}
                    </td>
                    <td className="p-3 text-xs">{r.user_email || "—"}</td>
                    <td className="p-3 font-mono text-xs">
                      {r.account_login || "—"}
                      <div className="text-muted-foreground">{r.account_server || ""}</div>
                    </td>
                    <td className="p-3 font-semibold">{r.symbol}</td>
                    <td className="p-3">
                      <Badge variant="outline" className="text-xs">
                        {r.recovery_type === "open_recovery" ? t("operations.openRecovery") : t("operations.closeRecovery")}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <Badge variant="outline">{r.action.toUpperCase()} {r.direction}</Badge>
                      <div className="text-xs text-muted-foreground mt-1">{r.volume.toFixed(2)} lots</div>
                    </td>
                    <td className="p-3 text-right font-mono text-xs">{r.original_price ?? "—"}</td>
                    <td className="p-3 text-right font-mono text-xs">
                      {r.current_price ?? "—"}
                      {r.price_delta_points !== null && (
                        <div className={`text-[10px] ${r.price_delta_points > 0 ? "text-success" : "text-danger"}`}>
                          Δ {r.price_delta_points.toFixed(1)}pts
                        </div>
                      )}
                    </td>
                    <td className="p-3 text-center font-mono">
                      {r.attempt_number}/{r.max_attempts}
                    </td>
                    <td className="p-3">
                      <Badge className={statusStyle[r.status] || ""}>
                        {t(statusKey[r.status] || r.status)}
                      </Badge>
                    </td>
                    <td className="p-3 text-xs max-w-[260px]">
                      {renderReason(r)}
                      {r.error_message && (
                        <div className="text-[10px] text-muted-foreground truncate mt-1" title={r.error_message}>
                          {r.error_message}
                        </div>
                      )}
                    </td>
                    <td className="p-3 font-mono text-xs">
                      {r.mt5_retcode ?? "—"}
                      {r.mt5_retcode_comment && (
                        <div className="text-[10px] text-muted-foreground truncate" title={r.mt5_retcode_comment}>
                          {r.mt5_retcode_comment}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {(!rows || rows.length === 0) && (
                  <tr>
                    <td colSpan={12} className="p-6 text-center text-muted-foreground">
                      {t("operations.noRecoveries")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  );
};

const KpiCard = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) => (
  <div className="card-glass rounded-lg p-3 flex items-center gap-3">
    <div className="p-2 rounded-md bg-muted/40">{icon}</div>
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  </div>
);

export default RecoveriesPanel;
