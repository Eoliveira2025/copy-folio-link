import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { AlertTriangle, XCircle, Clock, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

interface BillingAccessBannerProps {
  accessStatus: string;
  blockedAt?: string | null;
}

export function BillingAccessBanner({ accessStatus, blockedAt }: BillingAccessBannerProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (accessStatus === "active") return null;

  const config = {
    warning: {
      icon: AlertTriangle,
      bg: "border-warning/40 bg-warning/10",
      iconColor: "text-warning",
      title: t("billing.warningTitle", "Fatura próxima do vencimento"),
      description: t("billing.warningDesc", "Sua fatura vence em breve. Efetue o pagamento para evitar interrupção do serviço."),
      btnLabel: t("billing.payNow", "Pagar agora"),
    },
    grace: {
      icon: Clock,
      bg: "border-orange-500/40 bg-orange-500/10",
      iconColor: "text-orange-500",
      title: t("billing.graceTitle", "Fatura vencida — período de carência"),
      description: t("billing.graceDesc", "Sua fatura está vencida. Você ainda pode operar, mas o acesso será bloqueado em breve se o pagamento não for realizado."),
      btnLabel: t("billing.payNow", "Pagar agora"),
    },
    blocked: {
      icon: XCircle,
      bg: "border-destructive/40 bg-destructive/10",
      iconColor: "text-destructive",
      title: t("billing.blockedTitle", "Acesso bloqueado"),
      description: t("billing.blockedDesc", "Seu acesso foi bloqueado por fatura vencida. Todas as contas MT5 foram desconectadas. Efetue o pagamento para restaurar o serviço."),
      btnLabel: t("billing.regularize", "Regularizar"),
    },
  }[accessStatus];

  if (!config) return null;

  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-lg border p-4 ${config.bg}`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-6 h-6 ${config.iconColor} shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          <h3 className={`font-semibold text-sm ${config.iconColor}`}>{config.title}</h3>
          <p className="text-sm text-muted-foreground mt-1">{config.description}</p>
          {blockedAt && accessStatus === "blocked" && (
            <p className="text-xs text-muted-foreground mt-1">
              {t("billing.blockedSince", "Bloqueado desde")}: {new Date(blockedAt).toLocaleDateString()}
            </p>
          )}
        </div>
        <Button
          size="sm"
          variant={accessStatus === "blocked" ? "destructive" : "default"}
          className="shrink-0 gap-1.5"
          onClick={() => navigate("/dashboard/financial")}
        >
          <CreditCard className="w-4 h-4" />
          {config.btnLabel}
        </Button>
      </div>
    </motion.div>
  );
}
