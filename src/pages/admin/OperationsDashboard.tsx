import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/StatCard";
import {
  Activity, Server, Users, CreditCard, AlertTriangle, Zap,
  Database, Radio, RefreshCw, Clock, TrendingDown, Shield, Inbox,
} from "lucide-react";
import { motion } from "framer-motion";
import { useAdminOperations, useAdminDeadLetterTrades, useAdminRetryDeadLetter, useAdminResolveDeadLetter } from "@/hooks/use-api";

const statusColor: Record<string, string> = {
  healthy: "bg-success/15 text-success border-success/30",
  down: "bg-danger/15 text-danger border-danger/30",
  pending: "bg-warning/15 text-warning border-warning/30",
  retried: "bg-info/15 text-info border-info/30",
  resolved: "bg-success/15 text-success border-success/30",
};

const OperationsDashboard = () => {
  const { t } = useTranslation();
  const { data: ops, isLoading } = useAdminOperations();
  const { data: dlqTrades, isLoading: dlqLoading } = useAdminDeadLetterTrades();
  const retryTrade = useAdminRetryDeadLetter();
  const resolveTrade = useAdminResolveDeadLetter();

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-6xl">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold">{t("operations.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("operations.subtitle")}</p>
      </div>

      {/* Trading Metrics */}
      <div>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary" /> {t("operations.tradingMetrics")}
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title={t("operations.connectedMT5")} value={`${ops?.connected_mt5_accounts || 0} / ${ops?.total_mt5_accounts || 0}`} icon={Server} delay={0} />
          <StatCard title={t("operations.masterAccounts")} value={String(ops?.master_accounts || 0)} icon={Users} delay={0.05} />
          <StatCard title={t("operations.copiedToday")} value={String(ops?.copied_trades_today || 0)} icon={Zap} trend="up" delay={0.1} />
          <StatCard title={t("operations.failedToday")} value={String(ops?.failed_trades_today || 0)} icon={AlertTriangle} trend={ops?.failed_trades_today ? "down" : "neutral"} delay={0.15} />
        </div>
      </div>

      {/* Performance */}
      <div>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Clock className="w-5 h-5 text-primary" /> {t("operations.performance")}
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title={t("operations.avgLatency")} value={`${ops?.avg_latency_ms || 0}ms`} icon={Clock} delay={0} />
          <StatCard title={t("operations.dlqPending")} value={String(ops?.dlq_pending || 0)} icon={Inbox} trend={ops?.dlq_pending ? "down" : "neutral"} delay={0.05} />
          <StatCard title={t("operations.activeSubs")} value={String(ops?.active_subscriptions || 0)} icon={CreditCard} delay={0.1} />
          <StatCard title={t("operations.overdueInvoices")} value={String(ops?.overdue_invoices || 0)} icon={AlertTriangle} trend={ops?.overdue_invoices ? "down" : "neutral"} delay={0.15} />
        </div>
      </div>

      {/* Equity & Risk */}
      <div>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <TrendingDown className="w-5 h-5 text-primary" /> {t("operations.equityRisk")}
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title={t("risk.totalBalance")} value={`$${(ops?.total_balance || 0).toLocaleString()}`} icon={Database} delay={0} />
          <StatCard title={t("risk.totalEquity")} value={`$${(ops?.total_equity || 0).toLocaleString()}`} icon={Database} delay={0.05} />
          <StatCard title={t("risk.drawdown")} value={`${ops?.global_drawdown_percent || 0}%`} icon={TrendingDown} trend={ops?.global_drawdown_percent && ops.global_drawdown_percent > 10 ? "down" : "neutral"} delay={0.1} />
          <StatCard title={t("risk.protectionEnabled")} value={ops?.protection_enabled ? t("common.yes") : t("common.no")} icon={Shield} delay={0.15} />
        </div>
        {ops?.emergency_active && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 p-4 rounded-lg bg-danger/10 border border-danger/30 text-danger font-semibold">
            {t("risk.emergencyActive")}
          </motion.div>
        )}
      </div>

      {/* Service Health */}
      <div>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Radio className="w-5 h-5 text-primary" /> {t("operations.serviceHealth")}
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {ops?.services && Object.entries(ops.services).map(([name, status]) => (
            <motion.div key={name} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-4 flex items-center justify-between">
              <span className="font-medium capitalize">{name.replace("_", " ")}</span>
              <Badge className={statusColor[status as string] || ""}>{status as string}</Badge>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Dead Letter Queue */}
      <div>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Inbox className="w-5 h-5 text-primary" /> {t("operations.deadLetterQueue")}
        </h2>
        {dlqLoading ? <Skeleton className="h-48" /> : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                    <th className="p-3 font-medium">{t("operations.orderId")}</th>
                    <th className="p-3 font-medium">{t("operations.symbol")}</th>
                    <th className="p-3 font-medium">{t("operations.action")}</th>
                    <th className="p-3 font-medium">{t("operations.error")}</th>
                    <th className="p-3 font-medium">{t("operations.attempts")}</th>
                    <th className="p-3 font-medium">{t("financial.status")}</th>
                    <th className="p-3 font-medium">{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {dlqTrades?.map((trade) => (
                    <tr key={trade.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                      <td className="p-3 font-mono text-xs">{trade.order_id.substring(0, 12)}...</td>
                      <td className="p-3 font-semibold">{trade.symbol}</td>
                      <td className="p-3"><Badge variant="outline">{trade.action} {trade.direction}</Badge></td>
                      <td className="p-3 text-danger text-xs max-w-[200px] truncate">{trade.error_message}</td>
                      <td className="p-3 font-mono">{trade.attempt_count}</td>
                      <td className="p-3"><Badge className={statusColor[trade.status] || ""}>{trade.status}</Badge></td>
                      <td className="p-3">
                        {trade.status === "pending" && (
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={() => retryTrade.mutate(trade.id)} disabled={retryTrade.isPending}>
                              <RefreshCw className="w-3 h-3" /> {t("operations.retry")}
                            </Button>
                            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => resolveTrade.mutate({ tradeId: trade.id, note: "" })} disabled={resolveTrade.isPending}>
                              {t("operations.resolve")}
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {(!dlqTrades || dlqTrades.length === 0) && (
                    <tr><td colSpan={7} className="p-6 text-center text-muted-foreground">{t("operations.noDLQ")}</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default OperationsDashboard;
