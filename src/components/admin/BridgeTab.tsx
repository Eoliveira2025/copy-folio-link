import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RefreshCw, Radio, ShieldCheck } from "lucide-react";
import { BridgeAuditorPanel } from "./BridgeAuditorPanel";

const API_BASE = (import.meta.env.VITE_API_URL || "/api/v1") as string;
async function fetchJson<T>(path: string): Promise<T> {
  const token = localStorage.getItem("access_token");
  const r = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!r.ok) throw new Error(String(r.status));
  return r.json() as Promise<T>;
}

interface BridgeSignal {
  id: string;
  master_id: string;
  strategy_id: string | null;
  action: string;
  symbol: string;
  volume: number;
  status: string;
  created_at: string;
  processed_at: string | null;
}

interface BridgeStats {
  enabled: boolean;
  signals_24h: number;
  orders_queued: number;
  orders_executed: number;
  orders_failed: number;
}

export function BridgeTab() {
  const [stats, setStats] = useState<BridgeStats | null>(null);
  const [signals, setSignals] = useState<BridgeSignal[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [s, sig] = await Promise.all([
        fetchJson<BridgeStats>("/admin/bridge/stats").catch(() => null),
        fetchJson<BridgeSignal[]>("/admin/bridge/signals?limit=50").catch(() => []),
      ]);
      setStats(s);
      setSignals(sig || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <Tabs defaultValue="overview">
        <TabsList className="bg-secondary">
          <TabsTrigger value="overview" className="gap-2"><Radio className="w-4 h-4" /> Visão geral</TabsTrigger>
          <TabsTrigger value="auditor" className="gap-2"><ShieldCheck className="w-4 h-4" /> Fiscal de Execução</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="w-5 h-5 text-primary" />
              <h2 className="text-lg font-semibold">Bridge</h2>
              {stats && (
                <Badge variant="outline" className={stats.enabled
                  ? "bg-success/15 text-success border-success/30"
                  : "bg-muted text-muted-foreground border-border"}>
                  {stats.enabled ? "Ativo" : "Inativo"}
                </Badge>
              )}
              <Badge variant="outline" className="bg-info/15 text-info border-info/30">
                modo paralelo
              </Badge>
            </div>
            <Button variant="outline" size="sm" onClick={load} className="gap-2">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Atualizar
            </Button>
          </div>

          {loading && !stats ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20" />)}
            </div>
          ) : stats ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KPI label="Sinais 24h" value={stats.signals_24h} />
              <KPI label="Em fila" value={stats.orders_queued} />
              <KPI label="Executadas" value={stats.orders_executed} />
              <KPI label="Falhas" value={stats.orders_failed} tone="danger" />
            </div>
          ) : (
            <div className="card-glass p-6 text-sm text-muted-foreground">
              Endpoint Bridge ainda não disponível no backend.
            </div>
          )}

          <div className="card-glass rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-border text-sm font-medium">
              Últimos sinais recebidos
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 text-muted-foreground">
                  <tr className="text-left">
                    <th className="p-3 font-medium">Quando</th>
                    <th className="p-3 font-medium">Master</th>
                    <th className="p-3 font-medium">Ação</th>
                    <th className="p-3 font-medium">Símbolo</th>
                    <th className="p-3 font-medium">Volume</th>
                    <th className="p-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map((s) => (
                    <tr key={s.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                      <td className="p-3 font-mono text-xs">{new Date(s.created_at).toLocaleString()}</td>
                      <td className="p-3">{s.master_id}</td>
                      <td className="p-3"><Badge variant="outline">{s.action}</Badge></td>
                      <td className="p-3 font-mono">{s.symbol}</td>
                      <td className="p-3 font-mono">{Number(s.volume).toFixed(2)}</td>
                      <td className="p-3"><Badge variant="outline">{s.status}</Badge></td>
                    </tr>
                  ))}
                  {signals.length === 0 && (
                    <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">Nenhum sinal recebido ainda</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="auditor" className="mt-4">
          <BridgeAuditorPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function KPI({ label, value, tone }: { label: string; value: number; tone?: "danger" }) {
  return (
    <div className="card-glass rounded-lg p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-2xl font-semibold ${tone === "danger" ? "text-danger" : ""}`}>{value}</div>
    </div>
  );
}
