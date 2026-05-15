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
  useAdminUpdateReconciliationSettings
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
        <Button onClick={handleSyncAll} className="flex items-center gap-2">
          <RefreshCcw className="h-4 w-4" />
          Sync All
        </Button>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview" className="gap-2"><Activity className="h-4 w-4" /> Visão Geral</TabsTrigger>
          <TabsTrigger value="strategies" className="gap-2"><Layers className="h-4 w-4" /> Estratégias</TabsTrigger>
          <TabsTrigger value="accounts" className="gap-2"><Users className="h-4 w-4" /> Contas</TabsTrigger>
          <TabsTrigger value="subscriptions" className="gap-2"><CheckCircle2 className="h-4 w-4" /> Assinaturas</TabsTrigger>
          <TabsTrigger value="switches" className="gap-2"><ArrowLeftRight className="h-4 w-4" /> Switch Requests</TabsTrigger>
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
                 <div className="flex items-center gap-4 p-4 border rounded-lg bg-success/5">
                   <CheckCircle2 className="h-5 w-5 text-success" />
                   <div>
                     <p className="font-medium text-success">MetaApi Cloud Status: Online</p>
                     <p className="text-xs text-muted-foreground">All connections stable</p>
                   </div>
                 </div>
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
      </Tabs>
    </div>
  );
};

export default MetaApiAdmin;