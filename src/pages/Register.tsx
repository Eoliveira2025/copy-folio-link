import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Eye, EyeOff, TrendingUp, FileText } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

function formatCpfCnpj(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length <= 11) {
    // CPF: 000.000.000-00
    return digits
      .replace(/(\d{3})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
  }
  // CNPJ: 00.000.000/0000-00
  return digits
    .replace(/(\d{2})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1/$2")
    .replace(/(\d{4})(\d{1,2})$/, "$1-$2");
}

const Register = () => {
  const { t } = useTranslation();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [cpfCnpj, setCpfCnpj] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [termsModalOpen, setTermsModalOpen] = useState(false);
  const navigate = useNavigate();
  const { register } = useAuth();

  const { data: activeTerms } = useQuery({
    queryKey: ["active-terms"],
    queryFn: () => api.getActiveTerms(),
    retry: false,
  });

  const cpfCnpjDigits = cpfCnpj.replace(/\D/g, "");
  const isValidCpfCnpj = cpfCnpjDigits.length === 11 || cpfCnpjDigits.length === 14;

  const canSubmit =
    firstName.trim().length > 0 &&
    lastName.trim().length > 0 &&
    isValidCpfCnpj &&
    termsAccepted &&
    !isLoading;

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!termsAccepted) {
      toast.error(t("auth.termsRequired"));
      return;
    }
    if (!isValidCpfCnpj) {
      toast.error(t("auth.invalidCpfCnpj"));
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
      const fullName = `${firstName.trim()} ${lastName.trim()}`;
      await register(email, password, confirmPassword, fullName, cpfCnpjDigits);
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

        <form onSubmit={handleRegister} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="firstName">{t("auth.firstName")}</Label>
              <Input
                id="firstName"
                placeholder={t("auth.firstNamePlaceholder")}
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="h-11 bg-secondary border-border"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lastName">{t("auth.lastName")}</Label>
              <Input
                id="lastName"
                placeholder={t("auth.lastNamePlaceholder")}
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="h-11 bg-secondary border-border"
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="cpfCnpj">{t("auth.cpfCnpj")}</Label>
            <Input
              id="cpfCnpj"
              placeholder="000.000.000-00"
              value={cpfCnpj}
              onChange={(e) => {
                const digits = e.target.value.replace(/\D/g, "").slice(0, 14);
                setCpfCnpj(formatCpfCnpj(digits));
              }}
              className="h-11 bg-secondary border-border"
              required
            />
            <p className="text-xs text-muted-foreground">{t("auth.cpfCnpjHint")}</p>
          </div>

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
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  setTermsModalOpen(true);
                }}
                className="text-primary hover:underline font-medium"
              >
                {t("auth.termsAndConditions")}
              </button>
            </Label>
          </div>

          <Button type="submit" className="w-full h-11 font-semibold" disabled={!canSubmit}>
            {isLoading ? t("auth.creatingAccount") : t("auth.register")}
          </Button>
        </form>

        <p className="text-center text-muted-foreground mt-6 text-sm">
          {t("auth.hasAccount")}{" "}
          <Link to="/login" className="text-primary hover:underline font-medium">{t("auth.signIn")}</Link>
        </p>
      </motion.div>

      {/* Terms Modal */}
      <Dialog open={termsModalOpen} onOpenChange={setTermsModalOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              {t("auth.termsAndConditions")}
            </DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[55vh] rounded-md border border-border bg-muted/30 p-4">
            {activeTerms?.content ? (
              <div
                className="text-sm [&_h1]:text-lg [&_h1]:font-bold [&_h1]:mt-6 [&_h1]:mb-3 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-4 [&_h2]:mb-2 [&_p]:text-muted-foreground [&_p]:mb-3 [&_p]:leading-relaxed [&_ul]:list-disc [&_ul]:ml-5 [&_ul]:mb-3 [&_ol]:list-decimal [&_ol]:ml-5 [&_ol]:mb-3 [&_li]:text-muted-foreground [&_li]:mb-1 [&_strong]:text-foreground"
                dangerouslySetInnerHTML={{ __html: activeTerms.content }}
              />
            ) : (
              <p className="text-muted-foreground text-sm">{t("auth.termsLoading")}</p>
            )}
          </ScrollArea>
          <Button
            onClick={() => {
              setTermsAccepted(true);
              setTermsModalOpen(false);
            }}
            className="w-full"
          >
            {t("auth.acceptTermsButton")}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Register;
