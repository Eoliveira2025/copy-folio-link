import { useState } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Crown, Zap, Shield, Star, Rocket, Gem, Copy, QrCode, X, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { usePlans, useSubscription, useCheckout } from "@/hooks/use-api";
import { toast } from "sonner";
import type { PlanPublic } from "@/lib/api";

const planIcons: Record<string, typeof Zap> = {
  LOW: Shield,
  MEDIUM: Star,
  HIGH: Zap,
  PRO: Rocket,
  EXPERT: Crown,
  EXPERT_PRO: Gem,
};

const planColors: Record<string, string> = {
  LOW: "from-[hsl(var(--muted))] to-[hsl(var(--secondary))]",
  MEDIUM: "from-[hsl(210,90%,55%/0.15)] to-[hsl(210,90%,55%/0.05)]",
  HIGH: "from-[hsl(var(--primary)/0.15)] to-[hsl(var(--primary)/0.05)]",
  PRO: "from-[hsl(38,92%,55%/0.15)] to-[hsl(38,92%,55%/0.05)]",
  EXPERT: "from-[hsl(280,70%,55%/0.15)] to-[hsl(280,70%,55%/0.05)]",
  EXPERT_PRO: "from-[hsl(0,72%,55%/0.15)] to-[hsl(0,72%,55%/0.05)]",
};

type BillingType = "PIX" | "BOLETO" | "CREDIT_CARD";

const Plans = () => {
  const { t } = useTranslation();
  const { data: plans, isLoading } = usePlans();
  const { data: subscription } = useSubscription();
  const checkout = useCheckout();

  const [checkoutDialog, setCheckoutDialog] = useState<PlanPublic | null>(null);
  const [paymentResult, setPaymentResult] = useState<{
    pix_qr_code?: string | null;
    pix_copy_paste?: string | null;
    boleto_url?: string | null;
    checkout_url?: string | null;
    status?: string;
  } | null>(null);

  const currentPlanName = subscription?.plan_name?.toUpperCase();

  const handleCheckout = async (plan: PlanPublic, billingType: BillingType) => {
    try {
      const result = await checkout.mutateAsync({
        plan_id: plan.id,
        billing_type: billingType,
        gateway: "asaas",
      });
      setPaymentResult(result);

      if (billingType === "CREDIT_CARD" && result.checkout_url) {
        window.open(result.checkout_url, "_blank");
      }
    } catch {
      // error handled by mutation
    }
  };

  const copyPixCode = (code: string) => {
    navigator.clipboard.writeText(code);
    toast.success(t("plans.pixCopied"));
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-6xl">
        <div>
          <Skeleton className="h-8 w-48 mb-2" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-72" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold">{t("plans.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("plans.subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {plans?.map((plan, i) => {
          const Icon = planIcons[plan.name?.toUpperCase()] || Star;
          const isCurrent = currentPlanName === plan.name?.toUpperCase();
          const gradient = planColors[plan.name?.toUpperCase()] || planColors.LOW;

          return (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Card className={`relative overflow-hidden transition-all hover:border-primary/40 ${isCurrent ? "border-primary glow-green" : ""}`}>
                <div className={`absolute inset-0 bg-gradient-to-br ${gradient} pointer-events-none`} />
                <CardHeader className="relative pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className="w-5 h-5 text-primary" />
                      <CardTitle className="text-lg">{plan.name}</CardTitle>
                    </div>
                    {isCurrent && (
                      <Badge className="bg-primary/15 text-primary border-primary/30 hover:bg-primary/15">
                        {t("plans.current")}
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="relative space-y-4">
                  <div>
                    <span className="text-3xl font-bold font-mono">
                      R$ {plan.price.toFixed(0)}
                    </span>
                    <span className="text-muted-foreground text-sm">/{t("plans.month")}</span>
                  </div>

                  <ul className="space-y-2 text-sm">
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-primary shrink-0" />
                      <span>{t("plans.maxAccounts", { count: plan.max_accounts })}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-primary shrink-0" />
                      <span>{t("plans.trialDays", { count: plan.trial_days })}</span>
                    </li>
                    {plan.allowed_strategies?.map((s) => (
                      <li key={s} className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-primary shrink-0" />
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    className="w-full"
                    variant={isCurrent ? "outline" : "default"}
                    disabled={isCurrent}
                    onClick={() => setCheckoutDialog(plan)}
                  >
                    {isCurrent ? t("plans.currentPlan") : t("plans.subscribe")}
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Checkout Dialog */}
      <Dialog open={!!checkoutDialog} onOpenChange={(open) => { if (!open) { setCheckoutDialog(null); setPaymentResult(null); } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {paymentResult ? t("plans.paymentDetails") : t("plans.choosePayment")}
            </DialogTitle>
          </DialogHeader>

          {!paymentResult ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {t("plans.subscribingTo")} <strong>{checkoutDialog?.name}</strong> — R$ {checkoutDialog?.price.toFixed(2)}/{t("plans.month")}
              </p>
              <div className="grid gap-2">
                <Button
                  variant="outline"
                  className="justify-start gap-3 h-14"
                  onClick={() => checkoutDialog && handleCheckout(checkoutDialog, "PIX")}
                  disabled={checkout.isPending}
                >
                  <QrCode className="w-5 h-5 text-primary" />
                  <div className="text-left">
                    <div className="font-medium">PIX</div>
                    <div className="text-xs text-muted-foreground">{t("plans.pixDesc")}</div>
                  </div>
                  {checkout.isPending && <Loader2 className="w-4 h-4 animate-spin ml-auto" />}
                </Button>
                <Button
                  variant="outline"
                  className="justify-start gap-3 h-14"
                  onClick={() => checkoutDialog && handleCheckout(checkoutDialog, "BOLETO")}
                  disabled={checkout.isPending}
                >
                  <svg className="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="7" y1="8" x2="7" y2="16"/><line x1="11" y1="8" x2="11" y2="16"/><line x1="15" y1="8" x2="15" y2="16"/></svg>
                  <div className="text-left">
                    <div className="font-medium">Boleto</div>
                    <div className="text-xs text-muted-foreground">{t("plans.boletoDesc")}</div>
                  </div>
                </Button>
                <Button
                  variant="outline"
                  className="justify-start gap-3 h-14"
                  onClick={() => checkoutDialog && handleCheckout(checkoutDialog, "CREDIT_CARD")}
                  disabled={checkout.isPending}
                >
                  <svg className="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
                  <div className="text-left">
                    <div className="font-medium">{t("plans.creditCard")}</div>
                    <div className="text-xs text-muted-foreground">{t("plans.creditCardDesc")}</div>
                  </div>
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {paymentResult.pix_qr_code && (
                <div className="flex flex-col items-center gap-3">
                  <div className="bg-background p-4 rounded-lg border border-border">
                    <img
                      src={`data:image/png;base64,${paymentResult.pix_qr_code}`}
                      alt="PIX QR Code"
                      className="w-48 h-48"
                    />
                  </div>
                  {paymentResult.pix_copy_paste && (
                    <Button
                      variant="outline"
                      className="w-full gap-2"
                      onClick={() => copyPixCode(paymentResult.pix_copy_paste!)}
                    >
                      <Copy className="w-4 h-4" />
                      {t("plans.copyPixCode")}
                    </Button>
                  )}
                  <p className="text-xs text-muted-foreground text-center">
                    {t("plans.pixInstructions")}
                  </p>
                </div>
              )}
              {paymentResult.boleto_url && (
                <div className="flex flex-col items-center gap-3">
                  <Button asChild className="w-full">
                    <a href={paymentResult.boleto_url} target="_blank" rel="noopener noreferrer">
                      {t("plans.openBoleto")}
                    </a>
                  </Button>
                  <p className="text-xs text-muted-foreground text-center">
                    {t("plans.boletoInstructions")}
                  </p>
                </div>
              )}
              {!paymentResult.pix_qr_code && !paymentResult.boleto_url && paymentResult.checkout_url && (
                <div className="text-center">
                  <p className="text-sm text-muted-foreground mb-3">{t("plans.redirected")}</p>
                  <Button asChild>
                    <a href={paymentResult.checkout_url} target="_blank" rel="noopener noreferrer">
                      {t("plans.goToPayment")}
                    </a>
                  </Button>
                </div>
              )}
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => { setPaymentResult(null); setCheckoutDialog(null); }}
              >
                {t("common.close")}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Plans;
