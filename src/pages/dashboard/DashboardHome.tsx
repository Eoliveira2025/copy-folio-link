import { StatCard } from "@/components/StatCard";
import { Link2, BarChart3, CreditCard, Activity, Copy, ArrowUpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { useMT5Accounts, useSubscription, useStrategies, useUpgradeEligibility, useRequestUpgrade } from "@/hooks/use-api";
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslation } from "react-i18next";

const DashboardHome = () => {
  const { t } = useTranslation();
  const { data: accounts, isLoading: mt5Loading } = useMT5Accounts();
  const { data: subscription, isLoading: subLoading } = useSubscription();
  const { data: strategies } = useStrategies();
  const { data: upgradeCheck } = useUpgradeEligibility();
  const requestUpgrade = useRequestUpgrade();

  const account = accounts?.[0];
  const isLoading = mt5Loading || subLoading;

  const getDaysRemaining = () => {
    if (!subscription) return "—";
    const endDate = subscription.trial_end || subscription.current_period_end;
    if (!endDate) return "—";
    const days = Math.ceil((new Date(endDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    return days > 0 ? t("dashboard.daysRemaining", { count: days }) : t("dashboard.expired");
  };

  const getSubStatus = () => {
    if (!subscription) return t("dashboard.noSubscription");
    return subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1);
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-6xl">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-40" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold">{t("dashboard.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("dashboard.subtitle")}</p>
      </div>

      {upgradeCheck?.eligible && !upgradeCheck.has_pending_request && upgradeCheck.next_plan && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-lg border border-primary/30 bg-primary/5 p-4 flex items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3">
            <ArrowUpCircle className="w-6 h-6 text-primary shrink-0" />
            <div>
              <p className="font-medium text-sm">
                {t("dashboard.upgradeAvailable", { balance: upgradeCheck.mt5_balance?.toFixed(2) })}{" "}
                <span className="text-primary font-semibold">{upgradeCheck.next_plan.name}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                ${upgradeCheck.next_plan.price}/mo · Min balance: ${upgradeCheck.min_balance_required?.toFixed(2)}
              </p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => requestUpgrade.mutate(upgradeCheck.next_plan!.id)}
            disabled={requestUpgrade.isPending}
            className="shrink-0 gap-1.5"
          >
            <ArrowUpCircle className="w-4 h-4" />
            {requestUpgrade.isPending ? t("dashboard.requesting") : t("dashboard.requestUpgrade")}
          </Button>
        </motion.div>
      )}

      {upgradeCheck?.has_pending_request && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-lg border border-warning/30 bg-warning/5 p-4 flex items-center gap-3"
        >
          <ArrowUpCircle className="w-5 h-5 text-warning shrink-0" />
          <p className="text-sm text-warning">{t("dashboard.upgradePending")}</p>
        </motion.div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("dashboard.mt5Status")}
          value={account ? (account.status === "connected" ? t("dashboard.connected") : account.status === "blocked" ? t("dashboard.blocked") : t("dashboard.disconnected")) : t("dashboard.notConnected")}
          icon={Link2}
          trend={account?.status === "connected" ? "up" : "down"}
          subtitle={account?.server || t("dashboard.connectYourAccount")}
          delay={0}
        />
        <StatCard
          title={t("dashboard.strategy")}
          value={strategies?.find(s => s.is_available)?.name || t("dashboard.notSelected")}
          icon={BarChart3}
          trend="neutral"
          subtitle={t("dashboard.activeStrategy")}
          delay={0.05}
        />
        <StatCard
          title={t("dashboard.subscription")}
          value={getSubStatus()}
          icon={CreditCard}
          trend={subscription?.status === "blocked" ? "down" : "up"}
          subtitle={getDaysRemaining()}
          delay={0.1}
        />
        <StatCard
          title={t("dashboard.balance")}
          value={account?.balance !== null && account?.balance !== undefined ? `$${account.balance.toFixed(2)}` : "—"}
          icon={Copy}
          trend="up"
          subtitle={account?.equity !== null && account?.equity !== undefined ? `${t("dashboard.equity")}: $${account.equity.toFixed(2)}` : t("dashboard.connectToSeeBalance")}
          delay={0.15}
        />
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="card-glass rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Activity className={`w-5 h-5 ${account?.status === "connected" ? "text-success animate-pulse" : "text-muted-foreground"}`} />
            <h2 className="font-semibold">{t("dashboard.copyEngineStatus")}</h2>
          </div>
          <Badge className={
            account?.status === "connected"
              ? "bg-success/15 text-success border-success/30 hover:bg-success/15"
              : "bg-muted text-muted-foreground border-border hover:bg-muted"
          }>
            {account?.status === "connected" ? t("dashboard.running") : t("dashboard.inactive")}
          </Badge>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground block">{t("dashboard.status")}</span>
            <span className="font-mono font-medium">
              {account?.status === "connected" ? t("dashboard.copyingTrades") : t("dashboard.waitingConnection")}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block">{t("dashboard.account")}</span>
            <span className="font-mono font-medium">{account?.login || "—"}</span>
          </div>
          <div>
            <span className="text-muted-foreground block">{t("dashboard.server")}</span>
            <span className="font-mono font-medium">{account?.server || "—"}</span>
          </div>
          <div>
            <span className="text-muted-foreground block">{t("dashboard.subscription")}</span>
            <span className="font-mono font-medium">{getSubStatus()}</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default DashboardHome;
