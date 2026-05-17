import { useQuery } from "@tanstack/react-query";
import { metaapiV3Api } from "@/integrations/metaapi_v3";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, AlertCircle, Info, CheckCircle2 } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export const MetaApiV3Strategies = () => {
  const { data: account, isLoading: loadingAccount } = useQuery({
    queryKey: ["metaapi-v3-account"],
    queryFn: metaapiV3Api.getMyAccount,
    retry: 1,
  });

  const { data: allowedStrategies, isLoading: loadingAllowed } = useQuery({
    queryKey: ["metaapi-v3-allowed-strategies"],
    queryFn: metaapiV3Api.getAllowedStrategies,
    retry: 1,
    enabled: !!account,
  });

  const { data: subscription } = useQuery({
    queryKey: ["metaapi-v3-subscription"],
    queryFn: metaapiV3Api.getMySubscription,
    retry: 1,
    enabled: !!account,
  });

  if (loadingAccount || loadingAllowed) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-48 w-full" />)}
      </div>
    );
  }

  // Se não tem conta V3, não mostra nada
  if (!account) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-primary" />
          Estratégias Cloud (CopyFactory V3)
        </h2>
        <p className="text-muted-foreground text-sm">
          Disponíveis para sua conta cloud com base no seu saldo atual (${account.last_equity?.toFixed(2)}).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {allowedStrategies?.map((s: any, i: number) => {
          const isActive = subscription?.strategy_code === s.strategy_code;
          
          return (
            <motion.div
              key={s.strategy_code}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Card className={`h-full relative overflow-hidden ${isActive ? 'ring-2 ring-primary border-primary/50' : s.allowed ? '' : 'opacity-70'}`}>
                {isActive && (
                  <div className="absolute top-0 right-0 p-2">
                    <CheckCircle2 className="w-5 h-5 text-primary fill-primary/10" />
                  </div>
                )}
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-primary" />
                    <CardTitle className="text-base">{s.display_name}</CardTitle>
                  </div>
                  <CardDescription className="text-xs">Code: {s.strategy_code}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Saldo Mínimo:</span>
                    <span className={`font-mono font-medium ${s.allowed ? 'text-success' : 'text-warning'}`}>
                      ${s.min_balance.toLocaleString()}
                    </span>
                  </div>

                  {!s.allowed && (
                    <div className="flex items-start gap-2 p-2 rounded bg-warning/10 text-warning text-[11px] leading-tight">
                      <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{s.reason}</span>
                    </div>
                  )}

                  {isActive ? (
                    <Badge className="w-full justify-center bg-primary/10 text-primary border-primary/20 hover:bg-primary/10">
                      ASSINATURA ATIVA
                    </Badge>
                  ) : s.allowed ? (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Badge variant="outline" className="w-full justify-center cursor-help">
                            DISPONÍVEL
                          </Badge>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">Para trocar para esta estratégia, entre em contato com o suporte ou aguarde a aprovação automática.</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ) : (
                    <Badge variant="secondary" className="w-full justify-center opacity-50">
                      BLOQUEADO
                    </Badge>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>
      
      <div className="flex items-center gap-2 p-4 rounded-lg bg-primary/5 border border-primary/10 text-xs text-muted-foreground">
        <Info className="w-4 h-4 text-primary shrink-0" />
        <p>As estratégias V3 operam com CopyFactory Institutional. O lote é copiado 1:1 e as configurações de SL/TP da master são seguidas rigorosamente.</p>
      </div>
    </div>
  );
};
