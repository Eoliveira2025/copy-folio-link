import { useClientMyMetaApiStatus, useClientSwitchStatus } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, ArrowUpCircle, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";

export const MetaApiV3ClientInfo = () => {
  const { data: status, isLoading } = useClientMyMetaApiStatus();
  const { data: switches } = useClientSwitchStatus();

  const pendingSwitch = switches?.find(s => s.status === 'PENDING_WAIT_FLAT');

  if (isLoading || !status) return null;

  return (
    <div className="space-y-4">
      {pendingSwitch && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4 flex items-center gap-3"
        >
          <ArrowUpCircle className="w-5 h-5 text-yellow-500 shrink-0" />
          <div>
            <p className="text-sm font-medium text-yellow-600">Troca de estratégia programada</p>
            <p className="text-xs text-muted-foreground">Será aplicada automaticamente assim que suas operações abertas forem encerradas.</p>
          </div>
        </motion.div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="card-glass border-none">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cloud Account Status</CardTitle>
            <Activity className={`w-4 h-4 ${status.connection_status === 'CONNECTED' ? 'text-success animate-pulse' : 'text-muted-foreground'}`} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="text-2xl font-bold">{status.connection_status}</div>
              <Badge variant={status.connection_status === 'CONNECTED' ? 'default' : 'destructive'}>
                {status.deployment_status}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">Login: {status.login}</p>
          </CardContent>
        </Card>

        <Card className="card-glass border-none">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">MetaApi Real-time Stats</CardTitle>
            <Activity className="w-4 h-4 text-primary" />
          </CardHeader>
          <CardContent>
             <div className="grid grid-cols-2 gap-2">
               <div>
                 <span className="text-xs text-muted-foreground block">Balance</span>
                 <span className="font-bold">${status.last_balance.toFixed(2)}</span>
               </div>
               <div>
                 <span className="text-xs text-muted-foreground block">Equity</span>
                 <span className="font-bold">${status.last_equity.toFixed(2)}</span>
               </div>
               <div>
                 <span className="text-xs text-muted-foreground block">Profit/Loss</span>
                 <span className={`font-bold ${status.last_profit_loss >= 0 ? 'text-success' : 'text-destructive'}`}>
                   ${status.last_profit_loss.toFixed(2)}
                 </span>
               </div>
               <div>
                 <span className="text-xs text-muted-foreground block">Positions</span>
                 <span className="font-bold">{status.last_positions_count}</span>
               </div>
             </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
