import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TrendingUp, ArrowLeft } from "lucide-react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { toast } from "sonner";

const ResetPassword = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error(t("auth.passwordMinLength"));
      return;
    }
    if (password !== confirmPassword) {
      toast.error(t("auth.passwordsNoMatch"));
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(token, password);
      setSuccess(true);
      toast.success(t("auth.passwordResetSuccess"));
    } catch (err: any) {
      toast.error(err.message || t("auth.resetFailed"));
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md text-center">
          <h2 className="text-2xl font-bold mb-4">{t("auth.invalidResetLink")}</h2>
          <p className="text-muted-foreground mb-6">{t("auth.invalidResetLinkDesc")}</p>
          <Link to="/forgot-password">
            <Button>{t("auth.requestNewLink")}</Button>
          </Link>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
        <Link to="/login" className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-8 text-sm">
          <ArrowLeft className="w-4 h-4" /> {t("auth.backToLogin")}
        </Link>

        <div className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-primary-foreground" />
          </div>
          <span className="text-2xl font-bold">{t("common.appName")}</span>
        </div>

        {success ? (
          <div>
            <h2 className="text-2xl font-bold mb-2">{t("auth.passwordResetDone")}</h2>
            <p className="text-muted-foreground mb-6">{t("auth.passwordResetDoneDesc")}</p>
            <Link to="/login">
              <Button className="w-full h-11 font-semibold">{t("auth.login")}</Button>
            </Link>
          </div>
        ) : (
          <>
            <h2 className="text-2xl font-bold mb-2">{t("auth.setNewPassword")}</h2>
            <p className="text-muted-foreground mb-8">{t("auth.setNewPasswordDesc")}</p>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="password">{t("auth.newPassword")}</Label>
                <Input id="password" type="password" placeholder={t("auth.passwordMinPlaceholder")} value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 bg-secondary border-border" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">{t("auth.confirmPassword")}</Label>
                <Input id="confirmPassword" type="password" placeholder={t("auth.repeatPassword")} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="h-11 bg-secondary border-border" />
              </div>
              <Button type="submit" className="w-full h-11 font-semibold" disabled={loading}>
                {loading ? t("common.loading") : t("auth.resetPassword")}
              </Button>
            </form>
          </>
        )}
      </motion.div>
    </div>
  );
};

export default ResetPassword;
