import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Link2, Shield, CheckCircle2, AlertCircle, Clock } from "lucide-react";
import { motion } from "framer-motion";
import { useMT5Accounts, useConnectMT5, useDisconnectMT5 } from "@/hooks/use-api";
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslation } from "react-i18next";

const servers = [
  ...Array.from({ length: 41 }, (_, i) => `Exness-MT5Real${i + 1}`),
  "Exness-MT5Trial11",
  "Exness-MT5Trial12",
];

const ConnectMT5 = () => {
  const { t } = useTranslation();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");

  const { data: accounts, isLoading } = useMT5Accounts();
  const connectMutation = useConnectMT5();
  const disconnectMutation = useDisconnectMT5();

  const connectedAccount = accounts?.[0];

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    connectMutation.mutate({ login: parseInt(login), password, server });
  };

  const handleDisconnect = () => {
    if (connectedAccount) disconnectMutation.mutate(connectedAccount.id);
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const isPending = connectedAccount?.status === "pending_provision";

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">{t("mt5.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("mt5.subtitle")}</p>
      </div>

      {connectedAccount ? (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card-glass rounded-lg p-8 text-center">
          {isPending ? (
            <>
              <Clock className="w-16 h-16 text-warning mx-auto mb-4" />
              <h2 className="text-xl font-bold mb-2">{t("mt5.pendingTitle", "Aguardando Conexão")}</h2>
              <p className="text-muted-foreground mb-4">{t("mt5.pendingMessage", "Seus dados foram enviados. O administrador fará a primeira conexão manualmente. Após a confirmação, o sistema assume automaticamente.")}</p>
            </>
          ) : (
            <>
              <CheckCircle2 className="w-16 h-16 text-success mx-auto mb-4" />
              <h2 className="text-xl font-bold mb-2">{t("mt5.accountConnected")}</h2>
              <p className="text-muted-foreground mb-4">{t("mt5.accountLinked")}</p>
            </>
          )}
          <div className="flex items-center justify-center gap-4 text-sm">
            <div><span className="text-muted-foreground">{t("mt5.login")}:</span> <span className="font-mono">{connectedAccount.login}</span></div>
            <div><span className="text-muted-foreground">{t("mt5.serverLabel")}:</span> <span className="font-mono">{connectedAccount.server}</span></div>
            <Badge className={
              connectedAccount.status === "connected"
                ? "bg-success/15 text-success border-success/30 hover:bg-success/15"
                : connectedAccount.status === "pending_provision"
                ? "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15"
                : connectedAccount.status === "blocked"
                ? "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15"
                : "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15"
            }>
              {connectedAccount.status === "pending_provision" 
                ? t("mt5.pendingStatus", "Aguardando") 
                : connectedAccount.status}
            </Badge>
          </div>
          {connectedAccount.balance !== null && connectedAccount.status !== "pending_provision" && (
            <div className="flex items-center justify-center gap-4 text-sm mt-3">
              <div><span className="text-muted-foreground">{t("dashboard.balance")}:</span> <span className="font-mono text-success">${connectedAccount.balance?.toFixed(2)}</span></div>
              <div><span className="text-muted-foreground">{t("dashboard.equity")}:</span> <span className="font-mono">${connectedAccount.equity?.toFixed(2)}</span></div>
            </div>
          )}
          {connectedAccount.status === "blocked" && (
            <div className="flex items-center justify-center gap-2 mt-4 text-sm text-danger">
              <AlertCircle className="w-4 h-4" />
              <span>{t("mt5.blockedMessage")}</span>
            </div>
          )}
          <Button variant="outline" className="mt-6" onClick={handleDisconnect} disabled={disconnectMutation.isPending}>
            {disconnectMutation.isPending ? t("mt5.disconnecting") : t("mt5.disconnect")}
          </Button>
        </motion.div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-6">
          <div className="flex items-center gap-2 mb-6 text-sm text-muted-foreground">
            <Shield className="w-4 h-4" />
            <span>{t("mt5.credentialsSecure")}</span>
          </div>

          <form onSubmit={handleConnect} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="login">{t("mt5.accountLogin")}</Label>
              <Input id="login" placeholder={t("mt5.loginPlaceholder")} value={login} onChange={(e) => setLogin(e.target.value)} className="h-11 bg-secondary border-border font-mono" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mt5pass">{t("mt5.mt5Password")}</Label>
              <Input id="mt5pass" type="password" placeholder={t("mt5.passwordPlaceholder")} value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 bg-secondary border-border" required />
            </div>
            <div className="space-y-2">
              <Label>{t("mt5.serverLabel")}</Label>
              <Select value={server} onValueChange={setServer} required>
                <SelectTrigger className="h-11 bg-secondary border-border">
                  <SelectValue placeholder={t("mt5.selectServer")} />
                </SelectTrigger>
                <SelectContent>
                  {servers.map((s) => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" className="w-full h-11 font-semibold" disabled={connectMutation.isPending}>
              <Link2 className="w-4 h-4 mr-2" />
              {connectMutation.isPending ? t("mt5.connecting") : t("mt5.connectAccount")}
            </Button>
          </form>
        </motion.div>
      )}
    </div>
  );
};

export default ConnectMT5;
