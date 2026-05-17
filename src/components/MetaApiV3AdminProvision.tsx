import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { metaapiV3Api } from "@/integrations/metaapi_v3";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ShieldCheck, UserPlus, Search, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export const MetaApiV3AdminProvision = () => {
  const queryClient = useQueryClient();
  const [userId, setUserId] = useState("");
  const [login, setLogin] = useState("");
  const [strategyCode, setStrategyCode] = useState("");
  const [cfSubId, setCfSubId] = useState("");
  const [searchEmail, setSearchEmail] = useState("");

  const { data: users, isLoading: searchingUsers } = useQuery({
    queryKey: ["admin-users-search", searchEmail],
    queryFn: () => api.adminSearchUsers(searchEmail),
    enabled: searchEmail.length > 3,
  });

  const provisionMutation = useMutation({
    mutationFn: metaapiV3Api.markProvisioned,
    onSuccess: (data) => {
      toast.success(data.message || "Provisionamento concluído com sucesso!");
      setUserId("");
      setLogin("");
      setStrategyCode("");
      setCfSubId("");
      queryClient.invalidateQueries({ queryKey: ["metaapi-v3-account"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Erro ao provisionar conta");
    },
  });

  const handleProvision = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId || !login || !strategyCode) {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }

    provisionMutation.mutate({
      user_id: userId,
      login,
      strategy_code: strategyCode,
      copyfactory_subscription_id: cfSubId,
    });
  };

  return (
    <Card className="mt-8 border-primary/20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-primary" />
          Provisionamento Manual V3
        </CardTitle>
        <CardDescription>
          Vincule manualmente uma conta MetaApi/CopyFactory a um usuário do sistema.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleProvision} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label>Buscar Usuário (Email)</Label>
              <div className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input 
                  placeholder="email@exemplo.com" 
                  className="pl-9"
                  value={searchEmail}
                  onChange={(e) => setSearchEmail(e.target.value)}
                />
              </div>
              {searchingUsers && <p className="text-xs text-muted-foreground">Buscando...</p>}
              {users && users.length > 0 && (
                <Select onValueChange={setUserId} value={userId}>
                  <SelectTrigger className="mt-2">
                    <SelectValue placeholder="Selecione o usuário" />
                  </SelectTrigger>
                  <SelectContent>
                    {users.map((u: any) => (
                      <SelectItem key={u.id} value={u.id}>
                        {u.email} ({u.id.substring(0, 8)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="login">Login MT5 (MetaApi)</Label>
              <Input 
                id="login"
                placeholder="Ex: 75080966"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Estratégia</Label>
              <Select onValueChange={setStrategyCode} value={strategyCode} required>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione a estratégia" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="LOW">LOW ($100)</SelectItem>
                  <SelectItem value="MEDIUM">MEDIUM ($500)</SelectItem>
                  <SelectItem value="HIGH">HIGH ($1000)</SelectItem>
                  <SelectItem value="PRO">PRO ($2000)</SelectItem>
                  <SelectItem value="EXPERT">EXPERT ($5000)</SelectItem>
                  <SelectItem value="EXPERT_PRO">EXPERT_PRO ($10000)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cf_sub_id">Subscription ID (Opcional)</Label>
              <Input 
                id="cf_sub_id"
                placeholder="Ex: manual-pro-75080966"
                value={cfSubId}
                onChange={(e) => setCfSubId(e.target.value)}
              />
            </div>
          </div>

          <Button 
            type="submit" 
            className="w-full md:w-auto gap-2"
            disabled={provisionMutation.isPending}
          >
            {provisionMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <UserPlus className="w-4 h-4" />
            )}
            Confirmar Provisionamento V3
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};
