import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Eye, EyeOff, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const Register = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const navigate = useNavigate();
  const { register } = useAuth();

  const { data: activeTerms } = useQuery({
    queryKey: ["active-terms"],
    queryFn: () => api.getActiveTerms(),
    retry: false,
  });

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!termsAccepted) {
      toast.error(t("auth.termsRequired"));
      return;
    }
    if (password !== confirmPassword) {
      toast.error(t("auth.passwordsNoMatch"));
      return;
    }
    if (password.length < 8) {
      toast.error(t("auth.passwordMinLength"));
      return;
    }
    setIsLoading(true);
    try {
      await register(email, password, confirmPassword);
      if (activeTerms?.id) {
        try {
          await api.acceptTerms(activeTerms.id);
        } catch {}
      }
      toast.success(t("auth.accountCreated"));
      navigate("/dashboard");
    } catch (err: any) {
      toast.error(err.message || t("auth.registerFailed"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 relative">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-primary-foreground" />
          </div>
          <span className="text-2xl font-bold">{t("common.appName")}</span>
        </div>

        <h2 className="text-2xl font-bold mb-2">{t("auth.createYourAccount")}</h2>
        <p className="text-muted-foreground mb-8">{t("auth.startTrial")}</p>

        <form onSubmit={handleRegister} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="email">{t("auth.email")}</Label>
            <Input id="email" type="email" placeholder={t("auth.emailPlaceholder")} value={email} onChange={(e) => setEmail(e.target.value)} className="h-11 bg-secondary border-border" required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">{t("auth.password")}</Label>
            <div className="relative">
              <Input id="password" type={showPassword ? "text" : "password"} placeholder={t("auth.passwordMinPlaceholder")} value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 bg-secondary border-border pr-10" required />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm">{t("auth.confirmPassword")}</Label>
            <Input id="confirm" type="password" placeholder={t("auth.repeatPassword")} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="h-11 bg-secondary border-border" required />
          </div>

          <div className="flex items-start gap-3">
            <Checkbox
              id="terms"
              checked={termsAccepted}
              onCheckedChange={(checked) => setTermsAccepted(checked === true)}
              className="mt-0.5"
            />
            <Label htmlFor="terms" className="text-sm text-muted-foreground font-normal leading-relaxed cursor-pointer">
              {t("auth.termsAgree")}{" "}
              <Link to="/terms-of-service" target="_blank" className="text-primary hover:underline font-medium">
                {t("auth.termsAndConditions")}
              </Link>
            </Label>
          </div>

          <Button type="submit" className="w-full h-11 font-semibold" disabled={isLoading || !termsAccepted}>
            {isLoading ? t("auth.creatingAccount") : t("auth.register")}
          </Button>
        </form>

        <p className="text-center text-muted-foreground mt-6 text-sm">
          {t("auth.hasAccount")}{" "}
          <Link to="/login" className="text-primary hover:underline font-medium">{t("auth.signIn")}</Link>
        </p>
      </motion.div>
    </div>
  );
};

export default Register;
