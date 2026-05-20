import { useState } from "react";
import { 
  Users, 
  UserPlus, 
  Key, 
  ExternalLink, 
  DollarSign, 
  Search,
  MoreHorizontal,
  LayoutDashboard,
  ShieldCheck,
  UserCheck,
  Clock,
  CheckCircle,
  XCircle,
  CreditCard
} from "lucide-react";

import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger,
  DialogFooter,
  DialogDescription
} from "@/components/ui/dialog";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { 
  useAffiliates, 
  useCreateAffiliate, 
  useResetAffiliatePassword,
  useAssignReferral,
  useAdminCommissions,
  useApproveCommission,
  useMarkCommissionPaid,
  useCancelCommission 
} from "@/hooks/use-affiliate";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { format } from "date-fns";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const AffiliateAdmin = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [selectedAffiliate, setSelectedAffiliate] = useState<string | null>(null);

  // Form states
  const [newAff, setNewAff] = useState({
    name: "",
    email: "",
    commission_percentage: 20,
    commission_base: "COMPANY_COMMISSION"
  });
  const [assignData, setAssignData] = useState({ user_id: "" });

  const { data: affiliates, isLoading } = useAffiliates();
  const createAff = useCreateAffiliate();
  const resetPass = useResetAffiliatePassword();
  const assignRef = useAssignReferral();
  const { data: commissions, isLoading: loadingCommissions } = useAdminCommissions();
  const approveComm = useApproveCommission();
  const paidComm = useMarkCommissionPaid();
  const cancelComm = useCancelCommission();

  // Search users for assignment
  const { data: users } = useQuery({
    queryKey: ["admin", "users", searchTerm],
    queryFn: () => api.adminSearchUsers(searchTerm),
    enabled: searchTerm.length > 2
  });

  const handleCreate = async () => {
    await createAff.mutateAsync(newAff);
    setIsAddOpen(false);
    setNewAff({ name: "", email: "", commission_percentage: 20, commission_base: "COMPANY_COMMISSION" });
  };

  const handleAssign = async () => {
    if (selectedAffiliate && assignData.user_id) {
      await assignRef.mutateAsync({ affiliate_id: selectedAffiliate, user_id: assignData.user_id });
      setIsAssignOpen(false);
      setAssignData({ user_id: "" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Afiliados</h1>
          <p className="text-muted-foreground">Gerencie parceiros, comissões e indicações.</p>
        </div>
        <Button onClick={() => setIsAddOpen(true)}>
          <UserPlus className="mr-2 h-4 w-4" />
          Novo Afiliado
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Afiliados</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{affiliates?.length || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Comissão Pendente</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-500">
              ${affiliates?.reduce((acc, curr) => acc + (curr.pending_commission || 0), 0).toFixed(2)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Pago</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">
              ${affiliates?.reduce((acc, curr) => acc + (curr.paid_commission || 0), 0).toFixed(2)}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="partners">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="partners">Parceiros</TabsTrigger>
          <TabsTrigger value="commissions">Comissões Semanais</TabsTrigger>
        </TabsList>
        <TabsContent value="partners" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Lista de Parceiros</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nome / Email</TableHead>
                    <TableHead>Comissão</TableHead>
                    <TableHead>Base</TableHead>
                    <TableHead>Indicados</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <TableRow><TableCell colSpan={6} className="text-center">Carregando...</TableCell></TableRow>
                  ) : affiliates?.length === 0 ? (
                    <TableRow><TableCell colSpan={6} className="text-center">Nenhum afiliado encontrado</TableCell></TableRow>
                  ) : (
                    affiliates?.map((aff) => (
                      <TableRow key={aff.id}>
                        <TableCell>
                          <div className="font-medium">{aff.name}</div>
                          <div className="text-sm text-muted-foreground">{aff.email}</div>
                        </TableCell>
                        <TableCell>{aff.commission_percentage}%</TableCell>
                        <TableCell>
                          <Badge variant="outline">{aff.commission_base}</Badge>
                        </TableCell>
                        <TableCell>{aff.total_referrals}</TableCell>
                        <TableCell>
                          {aff.active ? (
                            <Badge className="bg-green-500">Ativo</Badge>
                          ) : (
                            <Badge variant="destructive">Inativo</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => {
                                setSelectedAffiliate(aff.id);
                                setIsAssignOpen(true);
                              }}>
                                <UserPlus className="mr-2 h-4 w-4" /> Vincular Cliente
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => resetPass.mutate(aff.id)}>
                                <Key className="mr-2 h-4 w-4" /> Resetar Senha
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem className="text-destructive">
                                Desativar
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="commissions" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Comissões Geradas por Ciclo</CardTitle>
              <CardDescription>Aprove e gerencie os pagamentos aos afiliados.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data</TableHead>
                    <TableHead>Afiliado</TableHead>
                    <TableHead>Cliente</TableHead>
                    <TableHead>Lucro Bruto</TableHead>
                    <TableHead>Comissão</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingCommissions ? (
                    <TableRow><TableCell colSpan={7} className="text-center">Carregando...</TableCell></TableRow>
                  ) : commissions?.length === 0 ? (
                    <TableRow><TableCell colSpan={7} className="text-center">Nenhuma comissão encontrada</TableCell></TableRow>
                  ) : (
                    commissions?.map((comm: any) => (
                      <TableRow key={comm.id}>
                        <TableCell className="text-xs">
                          {format(new Date(comm.created_at), "dd/MM/yyyy HH:mm")}
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{comm.affiliate_name}</div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm text-muted-foreground">{comm.referred_user_email}</div>
                        </TableCell>
                        <TableCell>${comm.gross_profit}</TableCell>
                        <TableCell className="font-bold text-green-600">${comm.affiliate_commission_amount}</TableCell>
                        <TableCell>
                          <Badge className={
                            comm.status === 'PAID' ? 'bg-green-500' : 
                            comm.status === 'APPROVED' ? 'bg-blue-500' :
                            comm.status === 'PENDING' ? 'bg-orange-500' : 'bg-destructive'
                          }>
                            {comm.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            {comm.status === 'PENDING' && (
                              <Button variant="outline" size="sm" onClick={() => approveComm.mutate(comm.id)}>
                                <CheckCircle className="h-4 w-4 mr-1" /> Aprovar
                              </Button>
                            )}
                            {comm.status === 'APPROVED' && (
                              <Button variant="outline" size="sm" className="bg-green-50 text-green-700" onClick={() => paidComm.mutate(comm.id)}>
                                <CreditCard className="h-4 w-4 mr-1" /> Pagar
                              </Button>
                            )}
                            {(comm.status === 'PENDING' || comm.status === 'APPROVED') && (
                              <Button variant="ghost" size="sm" className="text-destructive" onClick={() => cancelComm.mutate(comm.id)}>
                                <XCircle className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
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

      {/* Add Dialog */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Novo Parceiro Afiliado</DialogTitle>
            <DialogDescription>
              Crie um acesso para um novo afiliado. A senha inicial será 'copy123'.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Nome Completo</Label>
              <Input 
                id="name" 
                value={newAff.name} 
                onChange={(e) => setNewAff({...newAff, name: e.target.value})} 
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="email">E-mail</Label>
              <Input 
                id="email" 
                type="email" 
                value={newAff.email} 
                onChange={(e) => setNewAff({...newAff, email: e.target.value})} 
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>% Comissão</Label>
                <Input 
                  type="number" 
                  value={newAff.commission_percentage} 
                  onChange={(e) => setNewAff({...newAff, commission_percentage: Number(e.target.value)})} 
                />
              </div>
              <div className="grid gap-2">
                <Label>Base de Cálculo</Label>
                <Select 
                  value={newAff.commission_base} 
                  onValueChange={(v) => setNewAff({...newAff, commission_base: v})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="COMPANY_COMMISSION">Comissão Empresa</SelectItem>
                    <SelectItem value="GROSS_PROFIT">Lucro Bruto</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddOpen(false)}>Cancelar</Button>
            <Button onClick={handleCreate} disabled={createAff.isPending}>Criar Afiliado</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign Referral Dialog */}
      <Dialog open={isAssignOpen} onOpenChange={setIsAssignOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Vincular Novo Cliente</DialogTitle>
            <DialogDescription>
              Busque um cliente existente para vincular a este afiliado.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid gap-2">
              <Label>Buscar Cliente (Email ou Login)</Label>
              <Input 
                placeholder="mínimo 3 caracteres..." 
                onChange={(e) => setSearchTerm(e.target.value)} 
              />
            </div>
            {users && users.length > 0 && (
              <div className="border rounded-md max-h-[200px] overflow-y-auto">
                {users.map(u => (
                  <div 
                    key={u.id} 
                    className={`p-2 flex justify-between items-center cursor-pointer hover:bg-accent ${assignData.user_id === u.id ? 'bg-accent' : ''}`}
                    onClick={() => setAssignData({ user_id: u.id })}
                  >
                    <div>
                      <div className="text-sm font-medium">{u.email}</div>
                      <div className="text-xs text-muted-foreground">MT5: {u.mt5_accounts?.[0]?.login || 'N/A'}</div>
                    </div>
                    {assignData.user_id === u.id && <UserCheck className="h-4 w-4 text-primary" />}
                  </div>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAssignOpen(false)}>Cancelar</Button>
            <Button onClick={handleAssign} disabled={!assignData.user_id || assignRef.isPending}>Vincular</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AffiliateAdmin;
