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
import {
  useAdminRiskSettings,
  useAdminRiskStatus,
  useAdminRiskIncidents,
  useAdminUpdateRiskSettings,
  useAdminResetEmergency,
} from "@/hooks/use-api";

export function RiskProtectionTab() {
  const { data: riskSettings, isLoading: settingsLoading } = useAdminRiskSettings();
  const { data: riskStatus, isLoading: statusLoading } = useAdminRiskStatus();
  const { data: incidents, isLoading: incidentsLoading } = useAdminRiskIncidents();
  const updateSettings = useAdminUpdateRiskSettings();
  const resetEmergency = useAdminResetEmergency();

  const [maxDrawdown, setMaxDrawdown] = useState<string>("");
  const [protectionEnabled, setProtectionEnabled] = useState<boolean | null>(null);

  // Sync local state from fetched settings
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
      {/* ── Live Status ── */}
      <div>
        <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary" /> Live Risk Status
        </h3>
        {statusLoading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : riskStatus ? (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Total Balance"
                value={formatCurrency(riskStatus.total_balance)}
                icon={DollarSign}
                delay={0}
              />
              <StatCard
                title="Total Equity"
                value={formatCurrency(riskStatus.total_equity)}
                icon={TrendingDown}
                delay={0.05}
              />
              <StatCard
                title="Drawdown"
                value={`${riskStatus.current_drawdown_percent}%`}
                icon={AlertTriangle}
                trend={riskStatus.current_drawdown_percent >= 20 ? "down" : "neutral"}
                delay={0.1}
              />
              <StatCard
                title="Accounts"
                value={String(riskStatus.account_count)}
                icon={Shield}
                delay={0.15}
              />
            </div>

            {/* Emergency Banner */}
            {riskStatus.emergency_active && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-lg border-2 border-danger bg-danger/10 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-6 h-6 text-danger animate-pulse" />
                  <div>
                    <p className="font-bold text-danger">⚠ EMERGENCY STOP ACTIVE</p>
                    <p className="text-sm text-muted-foreground">All trading has been halted. Review and reset when safe.</p>
                  </div>
                </div>
                <Button
                  variant="destructive"
                  onClick={() => resetEmergency.mutate()}
                  disabled={resetEmergency.isPending}
                  className="gap-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  {resetEmergency.isPending ? "Resetting..." : "Reset Emergency"}
                </Button>
              </motion.div>
            )}

            {/* Drawdown Progress Bar */}
            <div className="mt-4 card-glass rounded-lg p-4">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Current Drawdown</span>
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

      {/* ── Configuration ── */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-6 space-y-5">
        <h3 className="font-semibold text-lg flex items-center gap-2">
          <Shield className="w-5 h-5 text-primary" /> Global Risk Protection
        </h3>

        {settingsLoading ? (
          <Skeleton className="h-32" />
        ) : (
          <>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-base">Enable Protection</Label>
                <p className="text-sm text-muted-foreground">
                  Automatically close all trades when drawdown threshold is breached
                </p>
              </div>
              <Switch
                checked={currentEnabled}
                onCheckedChange={(v) => setProtectionEnabled(v)}
              />
            </div>

            <div className="space-y-2 max-w-xs">
              <Label>Global Max Loss (%)</Label>
              <Input
                type="number"
                min={1}
                max={100}
                value={currentMaxDD}
                onChange={(e) => setMaxDrawdown(e.target.value)}
                className="bg-secondary"
                placeholder="50"
              />
              <p className="text-xs text-muted-foreground">
                Emergency will trigger when total equity loss reaches this percentage
              </p>
            </div>

            <Button
              onClick={handleSave}
              disabled={updateSettings.isPending}
              className="w-full sm:w-auto"
            >
              {updateSettings.isPending ? "Saving..." : "Save Protection Settings"}
            </Button>
          </>
        )}
      </motion.div>

      {/* ── Incident Log ── */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-6 space-y-4">
        <h3 className="font-semibold text-lg flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-warning" /> Incident History
        </h3>

        {incidentsLoading ? (
          <Skeleton className="h-32" />
        ) : incidents && incidents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                  <th className="p-3 font-medium">Date</th>
                  <th className="p-3 font-medium">Type</th>
                  <th className="p-3 font-medium">Drawdown</th>
                  <th className="p-3 font-medium">Balance</th>
                  <th className="p-3 font-medium">Equity</th>
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
          <div className="p-6 text-center text-muted-foreground">
            No risk incidents recorded. System operating normally.
          </div>
        )}
      </motion.div>
    </div>
  );
}
