import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { useChangePassword } from "@/hooks/use-api";
import { useTranslation } from "react-i18next";

const SettingsPage = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const changePassword = useChangePassword();

  const handleUpdatePassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) return;
    changePassword.mutate(
      { currentPassword, newPassword },
      {
        onSuccess: () => {
          setCurrentPassword("");
          setNewPassword("");
          setConfirmPassword("");
        },
      }
    );
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">{t("settings.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("settings.subtitle")}</p>
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-6 space-y-6">
        <h2 className="font-semibold">{t("settings.profile")}</h2>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("auth.email")}</Label>
            <Input defaultValue={user?.email || ""} className="h-11 bg-secondary border-border" disabled />
          </div>
          <form onSubmit={handleUpdatePassword} className="space-y-4">
            <div className="space-y-2">
              <Label>{t("auth.currentPassword")}</Label>
              <Input type="password" placeholder={t("auth.passwordPlaceholder")} value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="h-11 bg-secondary border-border" required />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t("auth.newPassword")}</Label>
                <Input type="password" placeholder={t("auth.passwordPlaceholder")} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="h-11 bg-secondary border-border" required />
              </div>
              <div className="space-y-2">
                <Label>{t("auth.confirmPassword")}</Label>
                <Input type="password" placeholder={t("auth.passwordPlaceholder")} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="h-11 bg-secondary border-border" required />
              </div>
            </div>
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? t("settings.updating") : t("settings.updatePassword")}
            </Button>
          </form>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card-glass rounded-lg p-6 space-y-6">
        <h2 className="font-semibold">{t("settings.notifications")}</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div><Label>{t("settings.tradeNotifications")}</Label><p className="text-xs text-muted-foreground">{t("settings.tradeNotificationsDesc")}</p></div>
            <Switch defaultChecked />
          </div>
          <div className="flex items-center justify-between">
            <div><Label>{t("settings.billingAlerts")}</Label><p className="text-xs text-muted-foreground">{t("settings.billingAlertsDesc")}</p></div>
            <Switch defaultChecked />
          </div>
          <div className="flex items-center justify-between">
            <div><Label>{t("settings.connectionAlerts")}</Label><p className="text-xs text-muted-foreground">{t("settings.connectionAlertsDesc")}</p></div>
            <Switch defaultChecked />
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default SettingsPage;
