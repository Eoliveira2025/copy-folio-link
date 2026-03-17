import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Plus, Pencil, Trash2, Server, Link2 } from "lucide-react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  useAdminStrategies, useAdminCreateStrategy, useAdminUpdateStrategy,
  useAdminDeleteStrategy, useAdminSetMasterAccount,
} from "@/hooks/use-api";
import type { AdminStrategy, CreateStrategyData, CreateMasterAccountData } from "@/lib/api";

const LEVEL_OPTIONS = ["low", "medium", "high", "pro", "expert", "expert_pro"];

const levelColors: Record<string, string> = {
  low: "bg-success/15 text-success border-success/30",
  medium: "bg-warning/15 text-warning border-warning/30",
  high: "bg-danger/15 text-danger border-danger/30",
  pro: "bg-primary/15 text-primary border-primary/30",
  expert: "bg-accent/15 text-accent-foreground border-accent/30",
  expert_pro: "bg-danger/15 text-danger border-danger/30",
};

function StrategyFormDialog({ strategy, onClose }: { strategy?: AdminStrategy; onClose: () => void }) {
  const { t } = useTranslation();
  const createStrategy = useAdminCreateStrategy();
  const updateStrategy = useAdminUpdateStrategy();

  const [level, setLevel] = useState(strategy?.level || "");
  const [name, setName] = useState(strategy?.name || "");
  const [description, setDescription] = useState(strategy?.description || "");
  const [riskMultiplier, setRiskMultiplier] = useState(String(strategy?.risk_multiplier ?? 1.0));
  const [requiresUnlock, setRequiresUnlock] = useState(strategy?.requires_unlock ?? false);
  const [minCapital, setMinCapital] = useState(String(strategy?.min_capital ?? 0));

  const handleSubmit = () => {
    const data: CreateStrategyData = {
      level,
      name,
      description: description || null,
      risk_multiplier: parseFloat(riskMultiplier),
      requires_unlock: requiresUnlock,
    };
    if (strategy) {
      const { level: _, ...updates } = data;
      updateStrategy.mutate({ strategyId: strategy.id, updates }, { onSuccess: onClose });
    } else {
      createStrategy.mutate(data, { onSuccess: onClose });
    }
  };

  return (
    <div className="space-y-4">
      {!strategy && (
        <div className="space-y-2">
          <Label>{t("adminStrategies.level")}</Label>
          <Select value={level} onValueChange={setLevel}>
            <SelectTrigger className="bg-secondary"><SelectValue placeholder={t("adminStrategies.selectLevel")} /></SelectTrigger>
            <SelectContent>
              {LEVEL_OPTIONS.map((l) => (
                <SelectItem key={l} value={l}>{l.toUpperCase()}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="space-y-2">
        <Label>{t("adminStrategies.strategyName")}</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Conservative Growth" className="bg-secondary" />
      </div>
      <div className="space-y-2">
        <Label>{t("adminStrategies.description")}</Label>
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t("adminStrategies.descriptionPlaceholder")} className="bg-secondary min-h-[80px]" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label>{t("adminStrategies.riskMultiplier")}</Label>
          <Input type="number" min="0.1" step="0.1" value={riskMultiplier} onChange={(e) => setRiskMultiplier(e.target.value)} className="bg-secondary" />
        </div>
        <div className="space-y-2 flex flex-col justify-end">
          <div className="flex items-center gap-2 pb-1">
            <Switch checked={requiresUnlock} onCheckedChange={setRequiresUnlock} />
            <Label className="text-sm">{t("adminStrategies.requiresUnlock")}</Label>
          </div>
        </div>
      </div>
      <Button
        onClick={handleSubmit}
        disabled={createStrategy.isPending || updateStrategy.isPending || !name || (!strategy && !level) || parseFloat(riskMultiplier) <= 0}
        className="w-full"
      >
        {strategy ? t("adminStrategies.updateStrategy") : t("adminStrategies.createStrategy")}
      </Button>
    </div>
  );
}

function MasterAccountDialog({ strategy, onClose }: { strategy: AdminStrategy; onClose: () => void }) {
  const { t } = useTranslation();
  const setMasterAccount = useAdminSetMasterAccount();

  const [accountName, setAccountName] = useState(strategy.master_account?.account_name || "");
  const [login, setLogin] = useState(String(strategy.master_account?.login || ""));
  const [server, setServer] = useState(strategy.master_account?.server || "");
  const [password, setPassword] = useState("");

  const handleSubmit = () => {
    const data: CreateMasterAccountData = {
      account_name: accountName,
      login: parseInt(login),
      server,
      password,
    };
    setMasterAccount.mutate({ strategyId: strategy.id, masterData: data }, { onSuccess: onClose });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {t("adminStrategies.masterAccountFor")} <span className="text-foreground font-medium">{strategy.name}</span> ({strategy.level.toUpperCase()})
      </p>
      <div className="space-y-2">
        <Label>{t("adminStrategies.accountName")}</Label>
        <Input value={accountName} onChange={(e) => setAccountName(e.target.value)} placeholder="e.g. Master Low Risk" className="bg-secondary" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label>{t("adminStrategies.masterLogin")}</Label>
          <Input type="number" value={login} onChange={(e) => setLogin(e.target.value)} placeholder="e.g. 12345678" className="bg-secondary font-mono" />
        </div>
        <div className="space-y-2">
          <Label>{t("adminStrategies.masterServer")}</Label>
          <Input value={server} onChange={(e) => setServer(e.target.value)} placeholder="Exness-MT5Real" className="bg-secondary" />
        </div>
      </div>
      <div className="space-y-2">
        <Label>{t("adminStrategies.masterPassword")}</Label>
        <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={strategy.master_account ? t("adminStrategies.leaveBlank") : t("adminStrategies.passwordPlaceholder")} className="bg-secondary" />
      </div>
      <Button
        onClick={handleSubmit}
        disabled={setMasterAccount.isPending || !accountName || !login || !server || (!strategy.master_account && !password)}
        className="w-full"
      >
        {setMasterAccount.isPending ? t("common.loading") : strategy.master_account ? t("adminStrategies.updateMasterAccount") : t("adminStrategies.setMasterAccount")}
      </Button>
    </div>
  );
}

export function StrategiesTab() {
  const { t } = useTranslation();
  const { data: strategies, isLoading } = useAdminStrategies();
  const deleteStrategy = useAdminDeleteStrategy();
  const [strategyDialogOpen, setStrategyDialogOpen] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<AdminStrategy | undefined>();
  const [masterDialogStrategy, setMasterDialogStrategy] = useState<AdminStrategy | null>(null);

  if (isLoading) return <Skeleton className="h-48" />;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">{t("adminStrategies.subtitle")}</p>
        <Dialog open={strategyDialogOpen} onOpenChange={(open) => { setStrategyDialogOpen(open); if (!open) setEditingStrategy(undefined); }}>
          <DialogTrigger asChild>
            <Button className="gap-2" onClick={() => { setEditingStrategy(undefined); setStrategyDialogOpen(true); }}>
              <Plus className="w-4 h-4" /> {t("adminStrategies.createStrategy")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingStrategy ? t("adminStrategies.editStrategy") : t("adminStrategies.createStrategy")}</DialogTitle></DialogHeader>
            <StrategyFormDialog strategy={editingStrategy} onClose={() => setStrategyDialogOpen(false)} />
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies?.map((s, i) => (
          <motion.div
            key={s.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="card-glass rounded-lg p-5 space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={levelColors[s.level] || ""}>{s.level.toUpperCase()}</Badge>
                <h3 className="font-semibold">{s.name}</h3>
              </div>
              <div className="flex gap-1">
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { setEditingStrategy(s); setStrategyDialogOpen(true); }}>
                  <Pencil className="w-3.5 h-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7 text-danger hover:text-danger" onClick={() => deleteStrategy.mutate(s.id)}>
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>

            {s.description && <p className="text-sm text-muted-foreground">{s.description}</p>}

            <div className="text-sm space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t("strategies.multiplier")}</span>
                <span className="font-mono">{s.risk_multiplier}x</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t("adminStrategies.requiresUnlock")}</span>
                <span>{s.requires_unlock ? "✓" : "—"}</span>
              </div>
            </div>

            {/* Master Account Section */}
            <div className="border-t border-border pt-3">
              {s.master_account ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-sm font-medium">
                    <Server className="w-3.5 h-3.5 text-primary" />
                    {t("adminStrategies.masterAccount")}
                  </div>
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    <div>{s.master_account.account_name}</div>
                    <div className="font-mono">{t("mt5.login")}: {s.master_account.login} · {s.master_account.server}</div>
                    <div>{t("dashboard.balance")}: <span className="text-success font-mono">${s.master_account.balance.toFixed(2)}</span></div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground italic">{t("adminStrategies.noMasterAccount")}</p>
              )}

              <Dialog open={masterDialogStrategy?.id === s.id} onOpenChange={(open) => !open && setMasterDialogStrategy(null)}>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm" className="w-full mt-2 gap-1.5 text-xs" onClick={() => setMasterDialogStrategy(s)}>
                    <Link2 className="w-3 h-3" />
                    {s.master_account ? t("adminStrategies.editMasterAccount") : t("adminStrategies.setMasterAccount")}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>{t("adminStrategies.masterAccountConfig")}</DialogTitle></DialogHeader>
                  <MasterAccountDialog strategy={s} onClose={() => setMasterDialogStrategy(null)} />
                </DialogContent>
              </Dialog>
            </div>
          </motion.div>
        ))}
        {(!strategies || strategies.length === 0) && (
          <div className="col-span-full p-6 text-center text-muted-foreground card-glass rounded-lg">
            {t("adminStrategies.noStrategies")}
          </div>
        )}
      </div>
    </div>
  );
}
