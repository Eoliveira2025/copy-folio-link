import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertTriangle, Shield, DollarSign, TrendingDown, Activity, RotateCcw } from "lucide-react";
import { motion } from "framer-motion";
import { StatCard } from "@/components/StatCard";
import { useTranslation } from "react-i18next";
import {
  useAdminRiskSettings,
  useAdminRiskStatus,
  useAdminRiskIncidents,
  useAdminUpdateRiskSettings,
  useAdminResetEmergency,
} from "@/hooks/use-api";

export function RiskProtectionTab() {
  const { t } = useTranslation();
  const { data: riskSettings, isLoading: settingsLoading } = useAdminRiskSettings();
  const { data: riskStatus, isLoading: statusLoading } = useAdminRiskStatus();
  const { data: incidents, isLoading: incidentsLoading } = useAdminRiskIncidents();
  const updateSettings = useAdminUpdateRiskSettings();
  const resetEmergency = useAdminResetEmergency();

  const [maxDrawdown, setMaxDrawdown] = useState<string>("");
  const [protectionEnabled, setProtectionEnabled] = useState<boolean | null>(null);

  const currentMaxDD = maxDrawdown || String(riskSettings?.global_max_drawdown_percent ?? 50);
  const currentEnabled = protectionEnabled ?? riskSettings?.protection_enabled ?? true;

  const handleSave = () => {
    updateSettings.mutate({
      global_max_drawdown_percent: parseFloat(currentMaxDD),
      protection_enabled: currentEnabled,
    });
  };

  const drawdownColor = (dd: number) => {
    if (dd >= 40) return "text-danger";
    if (dd >= 20) return "text-warning";
    return "text-success";
  };

  const formatCurrency = (v: number) =>
    `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary" /> {t("risk.liveStatus")}
        </h3>
        {statusLoading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : riskStatus ? (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard title={t("risk.totalBalance")} value={formatCurrency(riskStatus.total_balance)} icon={DollarSign} delay={0} />
              <StatCard title={t("risk.totalEquity")} value={formatCurrency(riskStatus.total_equity)} icon={TrendingDown} delay={0.05} />
              <StatCard title={t("risk.drawdown")} value={`${riskStatus.current_drawdown_percent}%`} icon={AlertTriangle} trend={riskStatus.current_drawdown_percent >= 20 ? "down" : "neutral"} delay={0.1} />
              <StatCard title={t("risk.accounts")} value={String(riskStatus.account_count)} icon={Shield} delay={0.15} />
            </div>

            {riskStatus.emergency_active && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-lg border-2 border-danger bg-danger/10 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-6 h-6 text-danger animate-pulse" />
                  <div>
                    <p className="font-bold text-danger">{t("risk.emergencyActive")}</p>
                    <p className="text-sm text-muted-foreground">{t("risk.emergencyDescription")}</p>
                  </div>
                </div>
                <Button
                  variant="destructive"
                  onClick={() => resetEmergency.mutate()}
                  disabled={resetEmergency.isPending}
                  className="gap-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  {resetEmergency.isPending ? t("risk.resetting") : t("risk.resetEmergency")}
                </Button>
              </motion.div>
            )}

            <div className="mt-4 card-glass rounded-lg p-4">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">{t("risk.currentDrawdown")}</span>
                <span className={drawdownColor(riskStatus.current_drawdown_percent)}>
                  {riskStatus.current_drawdown_percent}% / {riskStatus.max_drawdown_percent}%
                </span>
              </div>
              <div className="w-full h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    riskStatus.current_drawdown_percent >= riskStatus.max_drawdown_percent * 0.8
                      ? "bg-danger"
                      : riskStatus.current_drawdown_percent >= riskStatus.max_drawdown_percent * 0.5
                        ? "bg-warning"
                        : "bg-success"
                  }`}
                  style={{
                    width: `${Math.min(
                      (riskStatus.current_drawdown_percent / riskStatus.max_drawdown_percent) * 100,
                      100
                    )}%`,
                  }}
                />
              </div>
            </div>
          </>
        ) : null}
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-6 space-y-5">
        <h3 className="font-semibold text-lg flex items-center gap-2">
          <Shield className="w-5 h-5 text-primary" /> {t("risk.globalProtection")}
        </h3>

        {settingsLoading ? (
          <Skeleton className="h-32" />
        ) : (
          <>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-base">{t("risk.enableProtection")}</Label>
                <p className="text-sm text-muted-foreground">{t("risk.enableProtectionDesc")}</p>
              </div>
              <Switch checked={currentEnabled} onCheckedChange={(v) => setProtectionEnabled(v)} />
            </div>

            <div className="space-y-2 max-w-xs">
              <Label>{t("risk.globalMaxLoss")}</Label>
              <Input type="number" min={1} max={100} value={currentMaxDD} onChange={(e) => setMaxDrawdown(e.target.value)} className="bg-secondary" placeholder="50" />
              <p className="text-xs text-muted-foreground">{t("risk.maxLossDescription")}</p>
            </div>

            <Button onClick={handleSave} disabled={updateSettings.isPending} className="w-full sm:w-auto">
              {updateSettings.isPending ? t("risk.saving") : t("risk.saveSettings")}
            </Button>
          </>
        )}
      </motion.div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-6 space-y-4">
        <h3 className="font-semibold text-lg flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-warning" /> {t("risk.incidentHistory")}
        </h3>

        {incidentsLoading ? (
          <Skeleton className="h-32" />
        ) : incidents && incidents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                  <th className="p-3 font-medium">{t("risk.dateCol")}</th>
                  <th className="p-3 font-medium">{t("risk.type")}</th>
                  <th className="p-3 font-medium">{t("risk.drawdownCol")}</th>
                  <th className="p-3 font-medium">{t("risk.balanceCol")}</th>
                  <th className="p-3 font-medium">{t("risk.equityCol")}</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr key={inc.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                    <td className="p-3">
                      {new Date(inc.created_at).toLocaleString("en-US", {
                        month: "short", day: "numeric", year: "numeric",
                        hour: "2-digit", minute: "2-digit",
                      })}
                    </td>
                    <td className="p-3">
                      <Badge className="bg-danger/15 text-danger border-danger/30 hover:bg-danger/15">
                        {inc.incident_type.replace(/_/g, " ")}
                      </Badge>
                    </td>
                    <td className="p-3 font-mono text-danger">{inc.drawdown_percent.toFixed(2)}%</td>
                    <td className="p-3 font-mono">{formatCurrency(inc.total_balance)}</td>
                    <td className="p-3 font-mono">{formatCurrency(inc.total_equity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 text-center text-muted-foreground">{t("risk.noIncidents")}</div>
        )}
      </motion.div>
    </div>
  );
}
