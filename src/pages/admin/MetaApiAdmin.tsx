import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  AlertCircle, CheckCircle2, Cloud, RefreshCcw, 
  Settings, Users, Layers, ArrowLeftRight, Activity,
  ShieldCheck, AlertTriangle, Scale, Zap
} from "lucide-react";
import { 
  useAdminMetaApiAccounts, 
  useAdminMetaApiStrategies, 
  useAdminMetaApiSubscriptions, 
  useAdminMetaApiSwitchRequests,
  useAdminSyncMetaApiAccount,
  useAdminCreateMetaApiProvider,
  useAdminForceMetaApiSwitch,
  useAdminReconciliationEvents,
  useAdminApproveCloseOrphan,
  useAdminIgnoreOrphan,
  useAdminRunReconciliation,
  useAdminReconciliationSettings,
  useAdminUpdateReconciliationSettings,
  useAdminMetaApiHealth,
  useAdminMetaApiMonitorEvents,
  useAdminTriggerMonitorScan
} from "@/hooks/use-api";
import { format } from "date-fns";
import { toast } from "sonner";
import { api } from "@/lib/api";

const MetaApiAdmin = () => {
  const { data: accounts, isLoading: loadingAccounts } = useAdminMetaApiAccounts();
  const { data: strategies, isLoading: loadingStrategies } = useAdminMetaApiStrategies();
  const { data: subscriptions, isLoading: loadingSubs } = useAdminMetaApiSubscriptions();
  const { data: switchRequests, isLoading: loadingSwitches } = useAdminMetaApiSwitchRequests();
  
  const syncAccount = useAdminSyncMetaApiAccount();
  const createProvider = useAdminCreateMetaApiProvider();
  const forceSwitch = useAdminForceMetaApiSwitch();
  
  const { data: reconEvents } = useAdminReconciliationEvents();
  const { data: reconSettings } = useAdminReconciliationSettings();
  const approveClose = useAdminApproveCloseOrphan();
  const ignoreOrphan = useAdminIgnoreOrphan();
  const runRecon = useAdminRunReconciliation();
  const updateReconSettings = useAdminUpdateReconciliationSettings();
  
  const { data: health, isLoading: loadingHealth } = useAdminMetaApiHealth();
  const { data: monitorEvents, isLoading: loadingEvents } = useAdminMetaApiMonitorEvents();
  const triggerScan = useAdminTriggerMonitorScan();

  const handleSyncAll = async () => {
    try {
      await api.adminSyncAllMetaApi();
      toast.success("Sync triggered for all accounts");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">MetaApi V3 Management</h2>
          <p className="text-muted-foreground">Institutional copy-trade administration</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => triggerScan.mutate()} disabled={triggerScan.isPending} className="flex items-center gap-2">
            <ShieldCheck className={`h-4 w-4 ${triggerScan.isPending ? 'animate-pulse' : ''}`} />
            Scan Health
          </Button>
          <Button onClick={handleSyncAll} className="flex items-center gap-2">
            <RefreshCcw className="h-4 w-4" />
            Sync All
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview" className="gap-2"><Activity className="h-4 w-4" /> Visão Geral</TabsTrigger>
          <TabsTrigger value="strategies" className="gap-2"><Layers className="h-4 w-4" /> Estratégias</TabsTrigger>
          <TabsTrigger value="accounts" className="gap-2"><Users className="h-4 w-4" /> Contas</TabsTrigger>
          <TabsTrigger value="subscriptions" className="gap-2"><CheckCircle2 className="h-4 w-4" /> Assinaturas</TabsTrigger>
          <TabsTrigger value="switches" className="gap-2"><ArrowLeftRight className="h-4 w-4" /> Switch Requests</TabsTrigger>
          <TabsTrigger value="reconciliation" className="gap-2"><Scale className="h-4 w-4" /> Reconciliação</TabsTrigger>
          <TabsTrigger value="monitoring" className="gap-2"><Activity className="h-4 w-4" /> Monitoramento</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Contas Conectadas</CardTitle>
                <Cloud className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{accounts?.filter(a => a.connection_status === 'CONNECTED').length || 0} / {accounts?.length || 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Estratégias Ativas</CardTitle>
                <Layers className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{strategies?.filter(s => s.is_active).length || 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Assinantes Ativos</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{subscriptions?.filter(s => s.status === 'ACTIVE').length || 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Trocas Pendentes</CardTitle>
                <ArrowLeftRight className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{switchRequests?.filter(r => r.status === 'PENDING_WAIT_FLAT').length || 0}</div>
              </CardContent>
            </Card>
          </div>
          
          <Card>
            <CardHeader>
              <CardTitle>Health Monitor</CardTitle>
              <CardDescription>Live status of V3 infrastructure</CardDescription>
            </CardHeader>
            <CardContent>
               <div className="space-y-4">
                 <div className={`flex items-center gap-4 p-4 border rounded-lg ${health?.status === 'OK' ? 'bg-success/5 border-success/20' : 'bg-warning/5 border-warning/20'}`}>
                   {health?.status === 'OK' ? (
                     <CheckCircle2 className="h-5 w-5 text-success" />
                   ) : (
                     <AlertTriangle className="h-5 w-5 text-warning" />
                   )}
                   <div>
                     <p className={`font-medium ${health?.status === 'OK' ? 'text-success' : 'text-warning'}`}>
                       V3 System Status: {health?.status || 'Unknown'}
                     </p>
                     <p className="text-xs text-muted-foreground">
                       {health?.timestamp ? `Last updated: ${format(new Date(health.timestamp), 'HH:mm:ss')}` : 'Checking...'}
                     </p>
                   </div>
                 </div>
                 {health?.stats && (
                   <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                     <div className="p-3 border rounded-md text-center">
                       <p className="text-xs text-muted-foreground mb-1">Total</p>
                       <p className="text-lg font-bold">{health.stats.total_accounts}</p>
                     </div>
                     <div className="p-3 border rounded-md text-center">
                       <p className="text-xs text-muted-foreground mb-1">Online</p>
                       <p className="text-lg font-bold text-success">{health.stats.connected}</p>
                     </div>
                     <div className="p-3 border rounded-md text-center">
                       <p className="text-xs text-muted-foreground mb-1">Deployed</p>
                       <p className="text-lg font-bold text-primary">{health.stats.deployed}</p>
                     </div>
                     <div className="p-3 border rounded-md text-center">
                       <p className="text-xs text-muted-foreground mb-1">Equity Zero</p>
                       <p className="text-lg font-bold text-destructive">{health.stats.equity_zero}</p>
                     </div>
                   </div>
                 )}
               </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="strategies">
          <Card>
            <CardHeader>
              <CardTitle>Trading Strategies</CardTitle>
              <CardDescription>Mapping strategies to CopyFactory providers</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Display Name</TableHead>
                    <TableHead>Master ID</TableHead>
                    <TableHead>CF Strategy ID</TableHead>
                    <TableHead>Min Balance</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {strategies?.map((strategy) => (
                    <TableRow key={strategy.id}>
                      <TableCell className="font-medium">{strategy.strategy_code}</TableCell>
                      <TableCell>{strategy.display_name}</TableCell>
                      <TableCell className="text-xs font-mono">{strategy.master_account_id?.substring(0, 8)}...</TableCell>
                      <TableCell className="text-xs font-mono">{strategy.copyfactory_strategy_id || '—'}</TableCell>
                      <TableCell>${strategy.min_balance}</TableCell>
                      <TableCell>
                        <Badge variant={strategy.is_active ? "default" : "secondary"}>
                          {strategy.is_active ? "ACTIVE" : "INACTIVE"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          disabled={createProvider.isPending}
                          onClick={() => createProvider.mutate(strategy.id)}
                        >
                          Sync CF
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="accounts">
          <Card>
            <CardHeader>
              <CardTitle>Cloud Accounts</CardTitle>
              <CardDescription>Master and client accounts on MetaApi</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Login</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Connection</TableHead>
                    <TableHead>Balance</TableHead>
                    <TableHead>Equity</TableHead>
                    <TableHead>Positions</TableHead>
                    <TableHead>Last Sync</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {accounts?.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell className="font-mono">{account.login}</TableCell>
                      <TableCell>{account.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{account.account_type}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <div className={`h-2 w-2 rounded-full ${account.connection_status === 'CONNECTED' ? 'bg-success' : 'bg-destructive'}`} />
                          <span className="text-xs">{account.connection_status}</span>
                        </div>
                      </TableCell>
                      <TableCell>${account.last_balance.toFixed(2)}</TableCell>
                      <TableCell>${account.last_equity.toFixed(2)}</TableCell>
                      <TableCell>{account.last_positions_count}</TableCell>
                      <TableCell className="text-xs">{account.last_sync_at ? format(new Date(account.last_sync_at), 'HH:mm:ss') : '—'}</TableCell>
                      <TableCell>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          disabled={syncAccount.isPending}
                          onClick={() => syncAccount.mutate(account.id)}
                        >
                          <RefreshCcw className={`h-4 w-4 ${syncAccount.isPending ? 'animate-spin' : ''}`} />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="subscriptions">
          <Card>
            <CardHeader>
              <CardTitle>Active Subscriptions</CardTitle>
              <CardDescription>Clients currently copying master strategies</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Client ID</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Risk Ratio</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created At</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {subscriptions?.map((sub) => (
                    <TableRow key={sub.id}>
                      <TableCell className="text-xs font-mono">{sub.client_account_id.substring(0, 8)}...</TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {strategies?.find(s => s.id === sub.strategy_id)?.strategy_code || 'Unknown'}
                        </Badge>
                      </TableCell>
                      <TableCell>{sub.risk_ratio}x</TableCell>
                      <TableCell>
                        <Badge variant={sub.status === 'ACTIVE' ? "default" : "destructive"}>
                          {sub.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">{format(new Date(sub.created_at), 'dd/MM HH:mm')}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm">Pause</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="switches">
          <Card>
            <CardHeader>
              <CardTitle>Strategy Switch Requests</CardTitle>
              <CardDescription>Upgrade and downgrade requests from users</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User ID</TableHead>
                    <TableHead>Target Strategy</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Open Positions?</TableHead>
                    <TableHead>Requested At</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {switchRequests?.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell className="text-xs font-mono">{req.user_id.substring(0, 8)}...</TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {strategies?.find(s => s.id === req.target_strategy_id)?.strategy_code || 'Unknown'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={
                          req.status === 'SWITCHED' ? 'default' : 
                          req.status === 'PENDING_WAIT_FLAT' ? 'outline' : 'secondary'
                        }>
                          {req.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{req.has_open_positions_at_request ? 'YES' : 'NO'}</TableCell>
                      <TableCell className="text-xs">{format(new Date(req.created_at), 'dd/MM HH:mm')}</TableCell>
                      <TableCell>
                        {req.status === 'PENDING_WAIT_FLAT' && (
                          <Button 
                            variant="destructive" 
                            size="sm"
                            disabled={forceSwitch.isPending}
                            onClick={() => forceSwitch.mutate(req.id)}
                          >
                            Force Switch
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reconciliation">
          <div className="grid gap-4 md:grid-cols-3 mb-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Settings className="h-4 w-4" /> Configurações do Engine
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span>Fechar Auto:</span>
                  <Badge variant={reconSettings?.auto_close_orphan_positions ? "default" : "secondary"} className="h-5 px-1.5 py-0">
                    {reconSettings?.auto_close_orphan_positions ? "ON" : "OFF"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span>Limite Perda:</span>
                  <span className="font-mono">${reconSettings?.orphan_auto_close_loss_limit?.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span>Fechar Lucro:</span>
                  <Badge variant={reconSettings?.orphan_auto_close_profit_enabled ? "default" : "secondary"} className="h-5 px-1.5 py-0">
                    {reconSettings?.orphan_auto_close_profit_enabled ? "ON" : "OFF"}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-xs font-medium">Orfãs</CardTitle>
                  <AlertTriangle className="h-3 w-3 text-warning" />
                </CardHeader>
                <CardContent>
                  <div className="text-xl font-bold">{reconEvents?.filter(e => e.status === 'ORPHAN_POSITION_DETECTED').length || 0}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-xs font-medium">Wait Admin</CardTitle>
                  <AlertCircle className="h-3 w-3 text-destructive" />
                </CardHeader>
                <CardContent>
                  <div className="text-xl font-bold">{reconEvents?.filter(e => e.status === 'WAITING_ADMIN_APPROVAL').length || 0}</div>
                </CardContent>
              </Card>
            </div>

            <div className="flex flex-col gap-2 justify-center">
              <Button onClick={() => runRecon.mutate()} disabled={runRecon.isPending} className="w-full h-full">
                <RefreshCcw className={`mr-2 h-4 w-4 ${runRecon.isPending ? 'animate-spin' : ''}`} />
                Rodar Reconciliação
              </Button>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Eventos de Reconciliação</CardTitle>
              <CardDescription>Detecção e ação sobre posições divergentes na V3</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data</TableHead>
                    <TableHead>Conta Cliente</TableHead>
                    <TableHead>Símbolo</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Volume</TableHead>
                    <TableHead>P/L</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Ação</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reconEvents?.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="text-xs">{format(new Date(event.created_at), 'dd/MM HH:mm')}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{accounts?.find(a => a.id === event.subscriber_account_id)?.login || 'Unknown'}</span>
                          <span className="text-[10px] text-muted-foreground font-mono">{event.subscriber_account_id.substring(0, 8)}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-bold">{event.symbol}</TableCell>
                      <TableCell>
                        <Badge variant={event.side === 'BUY' ? 'default' : 'destructive'}>{event.side}</Badge>
                      </TableCell>
                      <TableCell>{event.volume}</TableCell>
                      <TableCell className={event.profit >= 0 ? 'text-success' : 'text-destructive'}>
                        ${event.profit.toFixed(2)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={
                          event.status === 'AUTO_CLOSED' ? 'outline' : 
                          event.status === 'WAITING_ADMIN_APPROVAL' ? 'destructive' : 
                          event.status === 'ADMIN_CLOSED' ? 'default' : 'secondary'
                        }>
                          {event.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {(event.status === 'ORPHAN_POSITION_DETECTED' || event.status === 'WAITING_ADMIN_APPROVAL') && (
                          <div className="flex gap-2">
                            <Button 
                              variant="destructive" 
                              size="sm" 
                              onClick={() => approveClose.mutate(event.id)}
                              disabled={approveClose.isPending}
                            >
                              Fechar
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => ignoreOrphan.mutate(event.id)}
                              disabled={ignoreOrphan.isPending}
                            >
                              Ignorar
                            </Button>
                          </div>
                        )}
                        {event.action_taken && <span className="text-xs text-muted-foreground">{event.action_taken}</span>}
                      </TableCell>
                    </TableRow>
                  ))}
                  {reconEvents?.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                        Nenhum evento de divergência detectado.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="monitoring">
          <Card>
            <CardHeader>
              <CardTitle>Eventos de Monitoramento</CardTitle>
              <CardDescription>Alertas e eventos operacionais da V3</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data</TableHead>
                    <TableHead>Severidade</TableHead>
                    <TableHead>Evento</TableHead>
                    <TableHead>Mensagem</TableHead>
                    <TableHead>Conta</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {monitorEvents?.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="text-xs">{format(new Date(event.created_at), 'dd/MM HH:mm:ss')}</TableCell>
                      <TableCell>
                        <Badge variant={
                          event.severity === 'CRITICAL' ? 'destructive' : 
                          event.severity === 'WARNING' ? 'outline' : 'secondary'
                        }>
                          {event.severity}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium text-xs font-mono">{event.event_type}</TableCell>
                      <TableCell className="text-sm">{event.message}</TableCell>
                      <TableCell className="text-xs font-mono">
                        {accounts?.find(a => a.id === event.metaapi_account_id)?.login || 'Global'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {monitorEvents?.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        Nenhum evento de monitoramento registrado.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MetaApiAdmin;
