import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { RefreshCw, ShieldCheck, AlertTriangle } from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_URL || "/api/v1") as string;
async function fetchJson<T>(path: string): Promise<T> {
  const token = localStorage.getItem("access_token");
  const r = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!r.ok) throw new Error(String(r.status));
  return r.json() as Promise<T>;
}

interface AuditorStats {
  enabled: boolean;
  auto_fix_enabled: boolean;
  close_orphans: boolean;
  pending: number;
  matched: number;
  not_executed: number;
  still_open: number;
  auto_fixed: number;
  auto_fix_failed: number;
  failed_to_check: number;
  sl_tp_mismatch: number;
  last_24h: number;
}

interface AuditRow {
  id: string;
  client_login: string;
  user_email: string | null;
  expected_action: string;
  expected_symbol: string;
  expected_order_type: string | null;
  expected_lot: number | null;
  master_ticket: string | null;
  audit_status: string;
  detected_status: string | null;
  failure_reason: string | null;
  auto_fix_attempted: boolean;
  created_at: string | null;
  checked_at: string | null;
}

const STATUS_TONE: Record<string, string> = {
  matched: "bg-success/15 text-success border-success/30",
  auto_fixed: "bg-success/15 text-success border-success/30",
  pending: "bg-info/15 text-info border-info/30",
  not_executed: "bg-danger/15 text-danger border-danger/30",
  still_open: "bg-danger/15 text-danger border-danger/30",
  auto_fix_failed: "bg-danger/15 text-danger border-danger/30",
  failed_to_check: "bg-warning/15 text-warning border-warning/30",
  sl_tp_mismatch: "bg-warning/15 text-warning border-warning/30",
  wrong_lot: "bg-warning/15 text-warning border-warning/30",
  wrong_direction: "bg-warning/15 text-warning border-warning/30",
  already_closed: "bg-muted text-muted-foreground border-border",
};

export function BridgeAuditorPanel() {
  const [stats, setStats] = useState<AuditorStats | null>(null);
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [s, r] = await Promise.all([
        fetchJson<AuditorStats>("/admin/bridge/auditor/stats").catch(() => null),
        fetchJson<AuditRow[]>(
          `/admin/bridge/auditor/audits?limit=200${filter ? `&status=${filter}` : ""}`
        ).catch(() => []),
      ]);
      setStats(s);
      setRows(r || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const alerts: { label: string; tone: "danger" | "warning"; n: number }[] = stats ? [
    { label: "Executadas e não encontradas", tone: "danger", n: stats.not_executed },
    { label: "Master fechou, cliente aberto", tone: "danger", n: stats.still_open },
    { label: "Correções com falha", tone: "danger", n: stats.auto_fix_failed },
    { label: "SL/TP divergente", tone: "warning", n: stats.sl_tp_mismatch },
    { label: "Falhou ao verificar", tone: "warning", n: stats.failed_to_check },
  ].filter(a => a.n > 0) : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-primary" />
          <h3 className="font-semibold">Fiscal de Execução</h3>
          {stats && (
            <>
              <Badge variant="outline" className={stats.enabled
                ? "bg-success/15 text-success border-success/30"
                : "bg-muted text-muted-foreground border-border"}>
                {stats.enabled ? "Ativo" : "Inativo"}
              </Badge>
              <Badge variant="outline" className={stats.auto_fix_enabled
                ? "bg-warning/15 text-warning border-warning/30"
                : "bg-muted text-muted-foreground border-border"}>
                Auto-fix {stats.auto_fix_enabled ? "ON" : "OFF"}
              </Badge>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Select value={filter || "all"} onValueChange={(v) => setFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="w-56 h-9 bg-secondary"><SelectValue placeholder="Filtrar" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="not_executed">not_executed</SelectItem>
              <SelectItem value="still_open">still_open</SelectItem>
              <SelectItem value="auto_fix_failed">auto_fix_failed</SelectItem>
              <SelectItem value="failed_to_check">failed_to_check</SelectItem>
              <SelectItem value="sl_tp_mismatch">sl_tp_mismatch</SelectItem>
              <SelectItem value="matched">matched</SelectItem>
              <SelectItem value="auto_fixed">auto_fixed</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={load} className="gap-2">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Atualizar
          </Button>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="card-glass rounded-lg p-3 flex flex-wrap gap-2 items-center">
          <AlertTriangle className="w-4 h-4 text-warning" />
          {alerts.map(a => (
            <Badge key={a.label} variant="outline"
                   className={a.tone === "danger"
                     ? "bg-danger/15 text-danger border-danger/30"
                     : "bg-warning/15 text-warning border-warning/30"}>
              {a.label}: {a.n}
            </Badge>
          ))}
        </div>
      )}

      {loading && !stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KPI label="Pending" value={stats.pending} />
          <KPI label="Matched" value={stats.matched} tone="success" />
          <KPI label="Not executed" value={stats.not_executed} tone="danger" />
          <KPI label="Still open" value={stats.still_open} tone="danger" />
          <KPI label="Auto-fixed" value={stats.auto_fixed} tone="success" />
          <KPI label="Auto-fix failed" value={stats.auto_fix_failed} tone="danger" />
          <KPI label="SL/TP mismatch" value={stats.sl_tp_mismatch} tone="warning" />
          <KPI label="Failed to check" value={stats.failed_to_check} tone="warning" />
        </div>
      ) : null}

      <div className="card-glass rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr className="text-left">
                <th className="p-3 font-medium">Quando</th>
                <th className="p-3 font-medium">Cliente</th>
                <th className="p-3 font-medium">Símbolo</th>
                <th className="p-3 font-medium">Esperado</th>
                <th className="p-3 font-medium">Lot</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">Auto-fix</th>
                <th className="p-3 font-medium">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                  <td className="p-3 font-mono text-xs">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                  <td className="p-3">
                    <div className="font-mono">{r.client_login}</div>
                    {r.user_email && <div className="text-xs text-muted-foreground">{r.user_email}</div>}
                  </td>
                  <td className="p-3 font-mono">{r.expected_symbol}</td>
                  <td className="p-3"><Badge variant="outline">{r.expected_action} {r.expected_order_type || ""}</Badge></td>
                  <td className="p-3 font-mono">{r.expected_lot ?? "—"}</td>
                  <td className="p-3">
                    <Badge variant="outline" className={STATUS_TONE[r.audit_status] || ""}>
                      {r.audit_status}
                    </Badge>
                  </td>
                  <td className="p-3">{r.auto_fix_attempted ? <Badge variant="outline">tentado</Badge> : "—"}</td>
                  <td className="p-3 text-xs text-muted-foreground max-w-xs truncate" title={r.failure_reason || ""}>
                    {r.failure_reason || "—"}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={8} className="p-6 text-center text-muted-foreground">Nenhuma auditoria</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KPI({ label, value, tone }: { label: string; value: number; tone?: "danger" | "success" | "warning" }) {
  const cls = tone === "danger" ? "text-danger"
    : tone === "success" ? "text-success"
    : tone === "warning" ? "text-warning" : "";
  return (
    <div className="card-glass rounded-lg p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-2xl font-semibold ${cls}`}>{value}</div>
    </div>
  );
}
