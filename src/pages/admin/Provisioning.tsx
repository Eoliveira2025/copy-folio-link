import { useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Copy, CheckCircle, RefreshCw, MonitorSmartphone, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { useAdminPendingAccounts, useAdminCompleteProvision } from "@/hooks/use-api";
import { api } from "@/lib/api";

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
  toast.success("Copied!");
}

const Provisioning = () => {
  const { t } = useTranslation();
  const { data: accounts, isLoading, refetch } = useAdminPendingAccounts();
  const completeProvision = useAdminCompleteProvision();
  const [visiblePasswords, setVisiblePasswords] = useState<Record<string, boolean>>({});
  const [revealedPasswords, setRevealedPasswords] = useState<Record<string, string>>({});

  const togglePassword = async (id: string) => {
    if (!visiblePasswords[id] && !revealedPasswords[id]) {
      try {
        const data = await api.adminRevealProvisionPassword(id);
        setRevealedPasswords((prev) => ({ ...prev, [id]: data.password }));
      } catch {
        toast.error("Failed to reveal password");
        return;
      }
    }
    setVisiblePasswords((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("provisioning.title")}</h1>
          <p className="text-muted-foreground text-sm">{t("provisioning.subtitle")}</p>
        </div>
        <Button variant="outline" onClick={() => refetch()} className="gap-2">
          <RefreshCw className="w-4 h-4" />
          {t("common.update", "Refresh")}
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : !accounts || accounts.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="card-glass rounded-lg p-12 text-center"
        >
          <CheckCircle className="w-12 h-12 text-success mx-auto mb-3" />
          <h3 className="text-lg font-semibold">{t("provisioning.allClear")}</h3>
          <p className="text-muted-foreground text-sm mt-1">
            {t("provisioning.allClearDesc")}
          </p>
        </motion.div>
      ) : (
        <div className="space-y-4">
          {accounts.map((account, idx) => (
            <motion.div
              key={account.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="card-glass rounded-lg p-5 space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <MonitorSmartphone className="w-5 h-5 text-warning" />
                  <span className="font-semibold">{account.user_email}</span>
                </div>
                <Badge className="bg-warning/15 text-warning border-warning/30">
                  {t("provisioning.pendingStatus")}
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">
                    {t("provisioning.mt5Login")}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-lg">{account.login}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => copyToClipboard(String(account.login))}
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">
                    {t("provisioning.password")}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-lg">
                      {visiblePasswords[account.id] ? account.password : "••••••••"}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => togglePassword(account.id)}
                    >
                      {visiblePasswords[account.id] ? (
                        <EyeOff className="w-3.5 h-3.5" />
                      ) : (
                        <Eye className="w-3.5 h-3.5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => copyToClipboard(account.password)}
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">
                    {t("provisioning.server")}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-lg">{account.server}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => copyToClipboard(account.server)}
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={() => completeProvision.mutate(account.id)}
                  disabled={completeProvision.isPending}
                  className="gap-2"
                >
                  <CheckCircle className="w-4 h-4" />
                  {completeProvision.isPending
                    ? t("common.loading")
                    : t("provisioning.confirmConnection")}
                </Button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Provisioning;
