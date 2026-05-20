import { 
  Users, 
  DollarSign, 
  Clock, 
  TrendingUp,
  Activity,
  History,
  Layout,
  FileText
} from "lucide-react";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useMyAffiliateDashboard, useMyCommissions } from "@/hooks/use-affiliate";
import { format } from "date-fns";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const AffiliateDashboard = () => {
  const { data, isLoading } = useMyAffiliateDashboard();
  const { data: myCommissions, isLoading: loadingCommissions } = useMyCommissions();

  const fmtMoney = (val?: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(val || 0);
  };

  if (isLoading) {
    return <div className="p-8 text-center">Carregando Dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Painel do Afiliado</h1>
          <p className="text-muted-foreground">Acompanhe seus indicados e comissões em tempo real.</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Comissão Pendente</CardTitle>
            <Clock className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{fmtMoney(data?.total_pending)}</div>
            <p className="text-xs text-muted-foreground">Aguardando aprovação</p>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Recebido</CardTitle>
            <DollarSign className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{fmtMoney(data?.total_paid)}</div>
            <p className="text-xs text-muted-foreground">Pago via carteira interna</p>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Indicados Ativos</CardTitle>
            <Users className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data?.active_referrals_count}</div>
            <p className="text-xs text-muted-foreground">Clientes operando</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="overview">Visão Geral</TabsTrigger>
          <TabsTrigger value="history">Histórico Semanal</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6 space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="col-span-1">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Activity className="mr-2 h-4 w-4" />
                  Desempenho dos Clientes
                </CardTitle>
                <CardDescription>Status atual das contas vinculadas.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Estratégia</TableHead>
                      <TableHead className="text-right">Lucro (S)</TableHead>
                      <TableHead className="text-right">Sua Comissão</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data?.referrals.length === 0 ? (
                      <TableRow><TableCell colSpan={4} className="text-center py-4">Nenhum cliente ativo</TableCell></TableRow>
                    ) : (
                      data?.referrals.map((ref) => (
                        <TableRow key={ref.user_id}>
                          <TableCell className="max-w-[150px] truncate font-medium">{ref.email}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{ref.strategy_name}</Badge>
                          </TableCell>
                          <TableCell className="text-right text-green-500">
                            {fmtMoney(ref.weekly_profit)}
                          </TableCell>
                          <TableCell className="text-right font-bold">
                            {fmtMoney(ref.affiliate_commission)}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <Card className="col-span-1">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <History className="mr-2 h-4 w-4" />
                  Últimos Lançamentos
                </CardTitle>
                <CardDescription>Comissões geradas recentemente.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Data</TableHead>
                      <TableHead>Valor</TableHead>
                      <TableHead className="text-right">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data?.recent_commissions.length === 0 ? (
                      <TableRow><TableCell colSpan={3} className="text-center py-4">Sem histórico recente</TableCell></TableRow>
                    ) : (
                      data?.recent_commissions.map((comm) => (
                        <TableRow key={comm.id}>
                          <TableCell className="text-xs">
                            {format(new Date(comm.created_at), "dd/MM/yyyy HH:mm")}
                          </TableCell>
                          <TableCell className="font-medium">{fmtMoney(comm.amount)}</TableCell>
                          <TableCell className="text-right">
                            <Badge className={
                              comm.status === 'PAID' ? 'bg-green-500' : 
                              comm.status === 'PENDING' ? 'bg-blue-500' : 'bg-gray-500'
                            }>
                              {comm.status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="history" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <FileText className="mr-2 h-4 w-4" />
                Histórico Completo de Comissões
              </CardTitle>
              <CardDescription>Lista detalhada de todas as suas comissões por ciclo.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data</TableHead>
                    <TableHead>Cliente</TableHead>
                    <TableHead>Lucro Bruto</TableHead>
                    <TableHead>Minha Comissão</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingCommissions ? (
                    <TableRow><TableCell colSpan={5} className="text-center py-4">Carregando...</TableCell></TableRow>
                  ) : myCommissions?.length === 0 ? (
                    <TableRow><TableCell colSpan={5} className="text-center py-4">Nenhuma comissão encontrada</TableCell></TableRow>
                  ) : (
                    myCommissions?.map((comm) => (
                      <TableRow key={comm.id}>
                        <TableCell className="text-xs">
                          {format(new Date(comm.created_at), "dd/MM/yyyy HH:mm")}
                        </TableCell>
                        <TableCell className="font-medium">{comm.referred_user_email}</TableCell>
                        <TableCell>{fmtMoney(comm.gross_profit)}</TableCell>
                        <TableCell className="font-bold text-green-600">
                          {fmtMoney(comm.affiliate_commission_amount)}
                        </TableCell>
                        <TableCell>
                          <Badge className={
                            comm.status === 'PAID' ? 'bg-green-500' : 
                            comm.status === 'APPROVED' ? 'bg-blue-500' :
                            comm.status === 'PENDING' ? 'bg-orange-500' : 'bg-gray-500'
                          }>
                            {comm.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
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

export default AffiliateDashboard;
