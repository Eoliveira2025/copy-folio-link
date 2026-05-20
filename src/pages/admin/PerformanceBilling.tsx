import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { format } from "date-fns";
import {
  DollarSign,
  Users,
  TrendingUp,
  Clock,
  Search,
  MoreHorizontal,
  CheckCircle2,
  PlayCircle,
  StopCircle,
  Receipt,
  Settings,
  History,
  Activity,
  User as UserIcon
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  usePerformanceUsers,
  usePerformanceCycles,
  usePerformanceSummary,
  useSetPerformanceMethod,
  useStartPerformanceCycle,
  useClosePerformanceCycle,
  useGeneratePerformanceInvoice
} from "@/hooks/use-performance-billing";
import { Skeleton } from "@/components/ui/skeleton";
import type { PerformanceUserSummary, PerformanceCycle } from "@/lib/api";

const statusStyle: Record<string, string> = {
  OPEN: "bg-info/15 text-info border-info/30",
  CLOSED: "bg-muted text-muted-foreground border-border",
  INVOICED: "bg-success/15 text-success border-success/30",
  NO_PROFIT: "bg-warning/15 text-warning border-warning/30",
  ERROR: "bg-danger/15 text-danger border-danger/30",
};

const fmtMoney = (val?: number | null, currency = "USD") => {
  if (val === null || val === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(val);
};

const safeFormat = (d?: string | null, fmt = "dd/MM/yyyy HH:mm") => {
  if (!d) return "—";
  try {
    return format(new Date(d), fmt);
  } catch {
    return "—";
  }
};

const PerformanceBilling = () => {
  const { t } = useTranslation();
  const [userSearch, setUserSearch] = useState("");
  const [cycleUserFilter, setCycleUserFilter] = useState("");
  const [cycleStatusFilter, setCycleStatusFilter] = useState("all");

  // Data
  const { data: users, isLoading: usersLoading } = usePerformanceUsers();
  const { data: cycles, isLoading: cyclesLoading } = usePerformanceCycles(
    cycleUserFilter || undefined,
    cycleStatusFilter === "all" ? undefined : cycleStatusFilter
  );
  const { data: summary, isLoading: summaryLoading } = usePerformanceSummary();

  // Mutations
  const setMethod = useSetPerformanceMethod();
  const startCycle = useStartPerformanceCycle();
  const closeCycle = useClosePerformanceCycle();
  const generateInvoice = useGeneratePerformanceInvoice();

  // Local State
  const [configUser, setConfigUser] = useState<PerformanceUserSummary | null>(null);
  const [configMethod, setConfigMethod] = useState("MONTHLY");
  const [configPercentage, setConfigPercentage] = useState("30");

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    return users.filter(u => 
      u.email.toLowerCase().includes(userSearch.toLowerCase()) || 
      (u.full_name || "").toLowerCase().includes(userSearch.toLowerCase())
    );
  }, [users, userSearch]);

  const handleSaveMethod = () => {
    if (!configUser) return;
    setMethod.mutate({
      user_id: configUser.user_id,
      method: configMethod,
      performance_percentage: parseFloat(configPercentage)
    }, {
      onSuccess: () => setConfigUser(null)
    });
  };

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Performance Billing</h1>
          <p className="text-muted-foreground text-sm">Gerenciamento de cobrança por resultado semanal.</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="card-glass">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-primary" />
              <span className="text-xs text-muted-foreground uppercase font-semibold">Comissões em Aberto</span>
            </div>
            {summaryLoading ? <Skeleton className="h-8 w-24" /> : (
              <div className="text-2xl font-bold font-mono text-primary">{fmtMoney(summary?.open_commissions)}</div>
            )}
          </CardContent>
        </Card>
        <Card className="card-glass">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-success" />
              <span className="text-xs text-muted-foreground uppercase font-semibold">Total Faturado</span>
            </div>
            {summaryLoading ? <Skeleton className="h-8 w-24" /> : (
              <div className="text-2xl font-bold font-mono text-success">{fmtMoney(summary?.total_invoiced)}</div>
            )}
          </CardContent>
        </Card>
        <Card className="card-glass">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-4 h-4 text-info" />
              <span className="text-xs text-muted-foreground uppercase font-semibold">Ciclos Lucrativos</span>
            </div>
            {summaryLoading ? <Skeleton className="h-8 w-24" /> : (
              <div className="text-2xl font-bold font-mono">{summary?.profitable_cycles}</div>
            )}
          </CardContent>
        </Card>
        <Card className="card-glass">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-warning" />
              <span className="text-xs text-muted-foreground uppercase font-semibold">Ciclos Negativos</span>
            </div>
            {summaryLoading ? <Skeleton className="h-8 w-24" /> : (
              <div className="text-2xl font-bold font-mono">{summary?.negative_cycles}</div>
            )}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="config">
        <TabsList className="mb-4">
          <TabsTrigger value="config" className="gap-2"><Settings className="w-4 h-4" /> Configuração</TabsTrigger>
          <TabsTrigger value="cycles" className="gap-2"><History className="w-4 h-4" /> Ciclos</TabsTrigger>
        </TabsList>

        <TabsContent value="config" className="space-y-4">
          <Card className="card-glass">
            <CardHeader>
              <CardTitle className="text-lg">Configurar Usuários</CardTitle>
              <CardDescription>Defina o método de cobrança e percentual para cada usuário.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4 mb-6">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input 
                    placeholder="Buscar por e-mail ou nome..." 
                    className="pl-10"
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                  />
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Usuário</TableHead>
                    <TableHead>Login / Estratégia</TableHead>
                    <TableHead>Saldo Atual</TableHead>
                    <TableHead>Método Atual</TableHead>
                    <TableHead>Percentual</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usersLoading ? (
                    <TableRow><TableCell colSpan={6}><Skeleton className="h-20 w-full" /></TableCell></TableRow>
                  ) : filteredUsers.map((u) => (
                    <TableRow key={u.user_id}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{u.full_name || "—"}</span>
                          <span className="text-xs text-muted-foreground">{u.email}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-mono text-xs">{u.account_login || "—"}</span>
                          <Badge variant="outline" className="w-fit text-[10px] mt-1">{u.strategy_code || "N/A"}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono">{fmtMoney(u.current_balance)}</TableCell>
                      <TableCell>
                        <Badge variant={u.method === 'PERFORMANCE_WEEKLY' ? 'default' : 'secondary'}>
                          {u.method || 'MONTHLY'}
                        </Badge>
                      </TableCell>
                      <TableCell>{u.performance_percentage ? `${u.performance_percentage}%` : "—"}</TableCell>
                      <TableCell className="text-right">
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={() => {
                            setConfigUser(u);
                            setConfigMethod(u.method || "MONTHLY");
                            setConfigPercentage(String(u.performance_percentage || "30"));
                          }}
                        >
                          Configurar
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cycles" className="space-y-4">
          <Card className="card-glass">
            <CardContent className="p-4 flex flex-wrap gap-4 items-center">
               <Select value={cycleStatusFilter} onValueChange={setCycleStatusFilter}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos Status</SelectItem>
                  <SelectItem value="OPEN">Aberto</SelectItem>
                  <SelectItem value="CLOSED">Fechado</SelectItem>
                  <SelectItem value="INVOICED">Faturado</SelectItem>
                  <SelectItem value="NO_PROFIT">Sem Lucro</SelectItem>
                  <SelectItem value="ERROR">Erro</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <Card className="card-glass">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Login</TableHead>
                    <TableHead>Período</TableHead>
                    <TableHead>Saldo Inicial</TableHead>
                    <TableHead>Saldo Final</TableHead>
                    <TableHead>Lucro</TableHead>
                    <TableHead>Comissão</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cyclesLoading ? (
                    <TableRow><TableCell colSpan={8}><Skeleton className="h-24 w-full" /></TableCell></TableRow>
                  ) : cycles?.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-mono text-sm">{c.account_login}</span>
                          <span className="text-[10px] text-muted-foreground uppercase">{c.account_source}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col text-xs gap-1">
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {safeFormat(c.cycle_start)}</span>
                          {c.cycle_end && <span className="flex items-center gap-1 font-semibold"><CheckCircle2 className="w-3 h-3 text-success" /> {safeFormat(c.cycle_end)}</span>}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{fmtMoney(c.start_balance)}</TableCell>
                      <TableCell className="font-mono text-xs">{fmtMoney(c.end_balance)}</TableCell>
                      <TableCell className={`font-mono text-xs ${(c.gross_profit || 0) > 0 ? "text-success font-bold" : ""}`}>
                        {fmtMoney(c.gross_profit)}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        <div className="flex flex-col">
                          <span className="font-bold">{fmtMoney(c.commission_amount)}</span>
                          <span className="text-[10px] text-muted-foreground">{c.commission_percentage}%</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusStyle[c.status] || ""}>{c.status}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon"><MoreHorizontal className="w-4 h-4" /></Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            {c.status === "OPEN" && (
                              <DropdownMenuItem onClick={() => closeCycle.mutate(c.id)}>
                                <StopCircle className="w-4 h-4 mr-2" /> Fechar Ciclo
                              </DropdownMenuItem>
                            )}
                            {c.status === "CLOSED" && (c.gross_profit || 0) > 0 && (
                              <DropdownMenuItem onClick={() => generateInvoice.mutate(c.id)}>
                                <Receipt className="w-4 h-4 mr-2" /> Gerar Fatura
                              </DropdownMenuItem>
                            )}
                            {c.invoice_id && (
                              <DropdownMenuItem onClick={() => window.open(`/admin/billing?invoice=${c.invoice_id}`, '_blank')}>
                                <Receipt className="w-4 h-4 mr-2" /> Ver Fatura
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setCycleUserFilter(c.user_id)}>
                                <UserIcon className="w-4 h-4 mr-2" /> Ver Usuário
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={!!configUser} onOpenChange={(open) => !open && setConfigUser(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configurar Cobrança</DialogTitle>
            <DialogDescription>
              {configUser?.full_name || configUser?.email}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="method">Método de Cobrança</Label>
              <Select value={configMethod} onValueChange={setConfigMethod}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="MONTHLY">MENSAL (Padrão)</SelectItem>
                  <SelectItem value="PERFORMANCE_WEEKLY">PERFORMANCE SEMANAL</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {configMethod === 'PERFORMANCE_WEEKLY' && (
              <div className="grid gap-2">
                <Label htmlFor="percentage">Percentual de Performance (%)</Label>
                <Input 
                  id="percentage" 
                  type="number" 
                  value={configPercentage} 
                  onChange={(e) => setConfigPercentage(e.target.value)} 
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfigUser(null)}>Cancelar</Button>
            <Button onClick={handleSaveMethod} disabled={setMethod.isPending}>Salvar Alterações</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PerformanceBilling;
