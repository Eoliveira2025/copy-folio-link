import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Lock, BarChart3, CheckCircle2, AlertTriangle, Send, Clock } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { useStrategies, useSelectStrategy, useRequestStrategy } from "@/hooks/use-api";
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslation } from "react-i18next";

const riskInfo: Record<string, { risk: string; expectedReturn: string }> = {
  low: { risk: "Low", expectedReturn: "5-10% / month" },
  medium: { risk: "Medium", expectedReturn: "10-20% / month" },
  high: { risk: "High", expectedReturn: "20-35% / month" },
  pro: { risk: "Very High", expectedReturn: "30-50% / month" },
  expert: { risk: "Very High", expectedReturn: "40-60% / month" },
  expert_pro: { risk: "Extreme", expectedReturn: "50-80% / month" },
};

const riskColors: Record<string, string> = {
  Low: "text-success border-success/30",
  Medium: "text-warning border-warning/30",
  High: "text-danger border-danger/30",
  "Very High": "text-danger border-danger/30",
  Extreme: "text-danger border-danger/30",
};

const riskTranslationKeys: Record<string, string> = {
  Low: "strategies.low",
  Medium: "strategies.medium",
  High: "strategies.high",
  "Very High": "strategies.veryHigh",
  Extreme: "strategies.extreme",
};

const statusConfig: Record<string, { color: string; borderColor: string }> = {
  active: { color: "bg-success/15 text-success border-success/30", borderColor: "border-success/40" },
  available: { color: "bg-primary/15 text-primary border-primary/30", borderColor: "" },
  request: { color: "bg-warning/15 text-warning border-warning/30", borderColor: "" },
  pending: { color: "bg-info/15 text-info border-info/30", borderColor: "" },
  insufficient: { color: "bg-muted text-muted-foreground border-border", borderColor: "" },
  locked: { color: "bg-muted text-muted-foreground border-border", borderColor: "" },
};

const Strategies = () => {
  const { t } = useTranslation();
  const { data: strategies, isLoading } = useStrategies();
  const selectMutation = useSelectStrategy();
  const requestMutation = useRequestStrategy();

  const handleSelect = (id: string, status: string) => {
    if (status === "active") return;
    if (status === "insufficient" || status === "locked") {
      toast.error(t("strategies.lockedMessage"));
      return;
    }
    selectMutation.mutate(id);
  };

  const handleRequest = (id: string) => {
    requestMutation.mutate(id);
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-4xl">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-56" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">{t("strategies.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("strategies.subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies?.map((s, i) => {
          const info = riskInfo[s.level] || { risk: "Medium", expectedReturn: "10-20%" };
          const sc = statusConfig[s.user_status] || statusConfig.available;

          return (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`card-glass rounded-lg p-5 relative ${s.user_status === "active" ? "ring-1 ring-success/40" : ""} ${s.user_status === "insufficient" || s.user_status === "locked" ? "opacity-60" : ""}`}
            >
              {/* Status badge */}
              <div className="absolute top-3 right-3">
                {s.user_status === "active" && <CheckCircle2 className="w-5 h-5 text-success" />}
                {s.user_status === "pending" && <Clock className="w-4 h-4 text-info" />}
                {s.user_status === "locked" && <Lock className="w-4 h-4 text-muted-foreground" />}
                {s.user_status === "insufficient" && <AlertTriangle className="w-4 h-4 text-warning" />}
              </div>

              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-5 h-5 text-primary" />
                <h3 className="font-bold text-lg">{s.name}</h3>
              </div>
              <p className="text-muted-foreground text-sm mb-4">{s.description}</p>

              <div className="space-y-2 text-sm mb-4">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("strategies.riskLevel")}</span>
                  <Badge variant="outline" className={riskColors[info.risk]}>{t(riskTranslationKeys[info.risk] || "strategies.medium")}</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("strategies.expectedReturn")}</span>
                  <span className="font-mono text-success">{info.expectedReturn}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("strategies.multiplier")}</span>
                  <span className="font-mono">{s.risk_multiplier}x</span>
                </div>
                {s.min_capital > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t("strategies.minCapital")}</span>
                    <span className="font-mono text-warning">R$ {s.min_capital.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
              </div>

              {/* Status indicator */}
              <div className="mb-3">
                <Badge variant="outline" className={sc.color}>
                  {t(`strategies.status_${s.user_status}`)}
                </Badge>
              </div>

              {/* Action button */}
              {s.user_status === "active" ? (
                <Button className="w-full" variant="outline" disabled>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  {t("strategies.active")}
                </Button>
              ) : s.user_status === "available" ? (
                <Button
                  className="w-full"
                  disabled={selectMutation.isPending}
                  onClick={() => handleSelect(s.id, s.user_status)}
                >
                  {t("strategies.select")}
                </Button>
              ) : s.user_status === "request" ? (
                <Button
                  className="w-full"
                  variant="secondary"
                  disabled={requestMutation.isPending}
                  onClick={() => handleRequest(s.id)}
                >
                  <Send className="w-4 h-4 mr-2" />
                  {t("strategies.requestAccess")}
                </Button>
              ) : s.user_status === "pending" ? (
                <Button className="w-full" variant="outline" disabled>
                  <Clock className="w-4 h-4 mr-2" />
                  {t("strategyRequests.pendingMessage")}
                </Button>
              ) : (
                <Button className="w-full" variant="outline" disabled>
                  {s.user_status === "insufficient" ? t("strategies.insufficientCapital") : t("strategies.locked")}
                </Button>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

export default Strategies;
