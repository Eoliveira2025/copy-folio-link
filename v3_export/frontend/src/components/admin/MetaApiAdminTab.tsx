import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { 
  AlertCircle, CheckCircle2, Cloud, RefreshCcw, 
  Plus, Play, Trash2, Activity, Link as LinkIcon,
  ShieldCheck, UserCheck, AlertTriangle
} from "lucide-react";
import { 
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger 
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface MetaApiAccount {
  id: string;
  login: string;
  server: string;
  name: string;
  account_type: "MASTER" | "CLIENT";
  metaapi_account_id?: string;
  deployment_status: string;
  connection_status: string;
  created_at: string;
}

const MetaApiAdminTab = () => {
  const queryClient = useQueryClient();
  const [isAddAccountOpen, setIsAddAccountOpen] = useState(false);
  const [newAccount, setNewAccount] = useState({
    login: "",
    password: "",
    server: "",
    name: "",
    type: "CLIENT" as "MASTER" | "CLIENT"
  });

  const { data: status } = useQuery<{
    enabled: boolean;
    copyfactory_enabled: boolean;
    region: string;
  }>({
    queryKey: ["metaapi-status"],
    queryFn: () => api.get("/admin/metaapi/status"),
  });

  const { data: accounts, isLoading: accountsLoading } = useQuery<MetaApiAccount[]>({
    queryKey: ["metaapi-accounts"],
    queryFn: () => api.get("/admin/metaapi/accounts"),
  });

  const addAccountMutation = useMutation({
    mutationFn: (data: any) => api.post("/admin/metaapi/accounts", data),
    onSuccess: () => {
      toast.success("Account added and deployment started");
      setIsAddAccountOpen(false);
      queryClient.invalidateQueries({ queryKey: ["metaapi-accounts"] });
    },
    onError: (error: any) => {
      toast.error(error.message || "Failed to add account");
    }
  });

  const deployMutation = useMutation({
    mutationFn: (id: string) => api.post(`/admin/metaapi/accounts/${id}/deploy`, {}),
    onSuccess: () => {
      toast.success("Redeploy requested");
      queryClient.invalidateQueries({ queryKey: ["metaapi-accounts"] });
    }
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/admin/metaapi/accounts/${id}`),
    onSuccess: () => {
      toast.success("Account removed");
      queryClient.invalidateQueries({ queryKey: ["metaapi-accounts"] });
    }
  });

  const createProviderMutation = useMutation({
    mutationFn: (id: string) => api.post(`/admin/metaapi/masters/${id}/create-provider`, {}),
    onSuccess: () => {
      toast.success("CopyFactory Provider created");
      queryClient.invalidateQueries({ queryKey: ["metaapi-accounts"] });
    }
  });

  return (
    <div className="space-y-6 mt-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium">Cloud Environment (V3)</h3>
          <p className="text-sm text-muted-foreground">Manage MetaApi accounts and CopyFactory providers.</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={isAddAccountOpen} onOpenChange={setIsAddAccountOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2">
                <Plus className="h-4 w-4" /> Add MT5 Account
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add MetaApi Account</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Login MT5</Label>
                    <Input 
                      value={newAccount.login} 
                      onChange={e => setNewAccount({...newAccount, login: e.target.value})} 
                      placeholder="123456" 
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input 
                      type="password"
                      value={newAccount.password} 
                      onChange={e => setNewAccount({...newAccount, password: e.target.value})} 
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Server</Label>
                  <Input 
                    value={newAccount.server} 
                    onChange={e => setNewAccount({...newAccount, server: e.target.value})} 
                    placeholder="Exness-MT5Trial" 
                  />
                </div>
                <div className="space-y-2">
                  <Label>Internal Name</Label>
                  <Input 
                    value={newAccount.name} 
                    onChange={e => setNewAccount({...newAccount, name: e.target.value})} 
                    placeholder="master-demo-01" 
                  />
                </div>
                <div className="space-y-2">
                  <Label>Account Type</Label>
                  <Select 
                    value={newAccount.type} 
                    onValueChange={(val: any) => setNewAccount({...newAccount, type: val})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MASTER">MASTER (Signal Provider)</SelectItem>
                      <SelectItem value="CLIENT">CLIENT (Subscriber)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button 
                  className="w-full" 
                  onClick={() => addAccountMutation.mutate(newAccount)}
                  disabled={addAccountMutation.isPending}
                >
                  {addAccountMutation.isPending ? "Connecting..." : "Create Account"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="bg-secondary/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">MetaApi Core</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Badge variant={status?.enabled ? "default" : "destructive"}>
                {status?.enabled ? "ENABLED" : "DISABLED"}
              </Badge>
              <span className="text-xs text-muted-foreground">{status?.region}</span>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-secondary/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">CopyFactory V2</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={status?.copyfactory_enabled ? "default" : "destructive"}>
              {status?.copyfactory_enabled ? "ACTIVE" : "INACTIVE"}
            </Badge>
          </CardContent>
        </Card>
        <Card className="bg-secondary/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Environment</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline">HOMOLOGATION</Badge>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cloud Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr className="border-b">
                  <th className="p-3 text-left">Login / Name</th>
                  <th className="p-3 text-left">Type</th>
                  <th className="p-3 text-left">Cloud Status</th>
                  <th className="p-3 text-left">Connection</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {accountsLoading ? (
                  <tr><td colSpan={5} className="p-8 text-center">Loading accounts...</td></tr>
                ) : accounts?.length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">No accounts found.</td></tr>
                ) : accounts?.map(acc => (
                  <tr key={acc.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="p-3">
                      <div className="font-medium">{acc.login}</div>
                      <div className="text-xs text-muted-foreground">{acc.name}</div>
                    </td>
                    <td className="p-3">
                      <Badge variant="outline">{acc.account_type}</Badge>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-1.5">
                        <Activity className={`h-3 w-3 ${acc.deployment_status === 'DEPLOYED' ? 'text-green-500' : 'text-yellow-500'}`} />
                        {acc.deployment_status}
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-1.5">
                        {acc.connection_status === 'CONNECTED' ? (
                          <CheckCircle2 className="h-3 w-3 text-green-500" />
                        ) : (
                          <AlertTriangle className="h-3 w-3 text-yellow-500" />
                        )}
                        {acc.connection_status}
                      </div>
                    </td>
                    <td className="p-3 text-right">
                      <div className="flex justify-end gap-1">
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          title="Redeploy"
                          onClick={() => deployMutation.mutate(acc.id)}
                          disabled={deployMutation.isPending}
                        >
                          <RefreshCcw className="h-4 w-4" />
                        </Button>
                        {acc.account_type === 'MASTER' && (
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="text-primary"
                            title="Create CF Provider"
                            onClick={() => createProviderMutation.mutate(acc.id)}
                          >
                            <ShieldCheck className="h-4 w-4" />
                          </Button>
                        )}
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="text-destructive"
                          onClick={() => removeMutation.mutate(acc.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MetaApiAdminTab;
