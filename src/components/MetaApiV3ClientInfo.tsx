import { useQuery } from "@tanstack/react-query";
import { metaapiV3Api } from "@/integrations/metaapi_v3";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Activity, ShieldCheck, TrendingUp, AlertCircle } from "lucide-react";

export const MetaApiV3ClientInfo = () => {
  const { data: account, isLoading: loadingAccount } = useQuery({
    queryKey: ["metaapi-v3-account"],
    queryFn: metaapiV3Api.getMyAccount,
    retry: 1,
  });

  const { data: subscription, isLoading: loadingSub } = useQuery({
    queryKey: ["metaapi-v3-subscription"],
    queryFn: metaapiV3Api.getMySubscription,
    retry: 1,
  });

  if (loadingAccount || loadingSub) {
    return <Skeleton className="h-40 w-full mb-6" />;
  }

  // Se não tem conta V3, não mostra nada (mantém fallback V1)
  if (!account) return null;

  return (
    <div className="space-y-6 mb-6">
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-primary" />
              Conta MetaApi V3
            </CardTitle>
            <Badge 
              variant={account.connection_status === "CONNECTED" ? "default" : "destructive"}
              className={account.connection_status === "CONNECTED" ? "bg-success hover:bg-success" : ""}
            >
              {account.connection_status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Login / Servidor</p>
              <p className="font-mono font-medium">{account.login}</p>
              <p className="text-xs text-muted-foreground">{account.server}</p>
            </div>
            
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Saldo / Equity</p>
              <p className="font-mono font-medium text-lg">
                ${account.last_balance?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
              <p className="text-xs text-muted-foreground">
                Equity: ${account.last_equity?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Estratégia Atual</p>
              {subscription ? (
                <>
                  <p className="font-medium text-primary flex items-center gap-1">
                    <TrendingUp className="w-4 h-4" />
                    {subscription.display_name}
                  </p>
                  <Badge variant="outline" className="text-[10px] h-5">
                    {subscription.copyfactory_strategy_id}
                  </Badge>
                </>
              ) : (
                <div className="flex items-center gap-2 text-warning">
                  <AlertCircle className="w-4 h-4" />
                  <p className="text-sm font-medium">Aguardando Provisionamento</p>
                </div>
              )}
            </div>
          </div>

          {subscription?.status === "ACTIVE" && (
            <div className="mt-4 pt-4 border-t border-primary/10 flex items-center gap-2 text-xs text-success">
              <Activity className="w-3 h-3 animate-pulse" />
              Copiando operações em tempo real via CopyFactory
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
