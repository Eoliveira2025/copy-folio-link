import { useAdminMetaApiStrategies, useClientRequestSwitch, useClientMyMetaApiStatus } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BarChart3, CheckCircle2, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";

export const MetaApiV3Strategies = () => {
  const { data: strategies, isLoading } = useAdminMetaApiStrategies();
  const { data: myStatus } = useClientMyMetaApiStatus();
  const requestSwitch = useClientRequestSwitch();

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (!strategies || strategies.length === 0) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Estratégias MetaApi V3</h2>
        <p className="text-muted-foreground text-sm">Cópia institucional via CopyFactory</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies.filter(s => s.is_active).map((s, i) => (
          <motion.div
            key={s.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`card-glass rounded-lg p-5 flex flex-col justify-between ${myStatus?.strategy_id === s.id ? "ring-1 ring-primary/40" : ""}`}
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-primary" />
                  <h3 className="font-bold">{s.display_name}</h3>
                </div>
                <Badge variant="outline">{s.strategy_code}</Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-4">
                Min Balance: ${s.min_balance}
              </p>
            </div>

            <Button
              className="w-full mt-2"
              variant={myStatus?.strategy_id === s.id ? "outline" : "default"}
              disabled={myStatus?.strategy_id === s.id || requestSwitch.isPending}
              onClick={() => requestSwitch.mutate(s.id)}
            >
              {myStatus?.strategy_id === s.id ? (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Ativo
                </>
              ) : (
                <>
                  Selecionar Estratégia
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </motion.div>
        ))}
      </div>
    </div>
  );
};
