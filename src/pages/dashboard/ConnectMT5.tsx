import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Link2, Shield, CheckCircle2, AlertCircle, Clock, Search, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { useMT5Accounts, useConnectMT5, useDisconnectMT5 } from "@/hooks/use-api";
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { metaapiV3Api } from "@/integrations/metaapi_v3";
import { toast } from "sonner";
import { MetaApiV3ClientInfo } from "@/components/MetaApiV3ClientInfo";


const servers = [
  ...Array.from({ length: 41 }, (_, i) => `Exness-MT5Real${i + 1}`),
  "Exness-MT5Trial11",
  "Exness-MT5Trial12",
];

const ConnectMT5 = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");
  const [importLogin, setImportLogin] = useState("");

  const { data: accounts, isLoading } = useMT5Accounts();
  const connectMutation = useConnectMT5();
  const disconnectMutation = useDisconnectMT5();

  const { data: v3Account, isLoading: loadingV3 } = useQuery({
    queryKey: ["metaapi-v3-account"],
    queryFn: metaapiV3Api.getMyAccount,
    retry: 1,
  });

  const importMutation = useMutation({
    mutationFn: metaapiV3Api.importAccount,
    onSuccess: (data) => {
      toast.success("Conta sincronizada com sucesso!");
      queryClient.invalidateQueries({ queryKey: ["metaapi-v3-account"] });
      queryClient.invalidateQueries({ queryKey: ["metaapi-v3-subscription"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao sincronizar conta");
    },
  });


  const connectedAccount = accounts?.[0];

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    connectMutation.mutate({ login: parseInt(login), password, server });
  };

  const handleDisconnect = () => {
    if (connectedAccount) disconnectMutation.mutate(connectedAccount.id);
  };

  if (isLoading || loadingV3) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }


  const isPending = connectedAccount?.status === "pending_provision";

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">{t("mt5.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("mt5.subtitle")}</p>
      </div>

      <MetaApiV3ClientInfo />

      {v3Account ? (
        <div className="card-glass rounded-lg p-6 border-primary/20 bg-primary/5">
          <div className="flex items-center gap-3 mb-4">
            <Shield className="w-5 h-5 text-primary" />
            <h2 className="font-semibold text-lg">Conta Cloud V3 Detectada</h2>
          </div>
          <p className="text-sm text-muted-foreground mb-6">
            Sua conta {v3Account.login} já está sendo gerenciada pelo sistema Cloud.
            O provisionamento e sincronização são feitos automaticamente.
          </p>
          <div className="flex items-center gap-4 text-xs">
             <Badge variant="outline">Login: {v3Account.login}</Badge>
             <Badge variant="outline">Server: {v3Account.server}</Badge>
             <Badge className="bg-success">Ativa</Badge>
          </div>
        </div>
      ) : (
        <div className="card-glass rounded-lg p-6 border-primary/10 mb-8">
           <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
             <Search className="w-5 h-5 text-primary" />
             Já possui conta no MetaApi?
           </h2>
           <p className="text-sm text-muted-foreground mb-4">
             Se sua conta já foi adicionada manualmente pelo administrador ou via sistema antigo, você pode sincronizá-la aqui.
           </p>
           <div className="flex gap-2">
              <Input 
                placeholder="Login MT5" 
                value={importLogin} 
                onChange={(e) => setImportLogin(e.target.value)}
                className="font-mono"
              />
              <Button 
                variant="secondary" 
                onClick={() => importMutation.mutate(importLogin)}
                disabled={importMutation.isPending || !importLogin}
                className="shrink-0"
              >
                {importMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Sincronizar"}
              </Button>
           </div>
        </div>
      )}

      <div className="pt-4 border-t border-border/50">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 text-muted-foreground">
          <Link2 className="w-5 h-5" />
          Conexão Direta V1/V2 (Antigo)
        </h2>


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
    </div>
  );
};


export default ConnectMT5;
