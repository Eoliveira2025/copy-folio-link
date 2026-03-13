import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Link2, Shield, CheckCircle2, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { useMT5Accounts, useConnectMT5, useDisconnectMT5 } from "@/hooks/use-api";
import { Skeleton } from "@/components/ui/skeleton";

const servers = [
  "Exness-MT5Real",
  "Exness-MT5Real2",
  "Exness-MT5Real3",
  "Exness-MT5Trial",
];

const ConnectMT5 = () => {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");

  const { data: accounts, isLoading } = useMT5Accounts();
  const connectMutation = useConnectMT5();
  const disconnectMutation = useDisconnectMT5();

  const connectedAccount = accounts?.[0];

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    connectMutation.mutate({
      login: parseInt(login),
      password,
      server,
    });
  };

  const handleDisconnect = () => {
    if (connectedAccount) {
      disconnectMutation.mutate(connectedAccount.id);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Connect MT5 Account</h1>
        <p className="text-muted-foreground text-sm">Link your MetaTrader 5 account to start copy trading</p>
      </div>

      {connectedAccount ? (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card-glass rounded-lg p-8 text-center">
          <CheckCircle2 className="w-16 h-16 text-success mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Account Connected</h2>
          <p className="text-muted-foreground mb-4">Your MT5 account is linked and ready for copy trading</p>
          <div className="flex items-center justify-center gap-4 text-sm">
            <div><span className="text-muted-foreground">Login:</span> <span className="font-mono">{connectedAccount.login}</span></div>
            <div><span className="text-muted-foreground">Server:</span> <span className="font-mono">{connectedAccount.server}</span></div>
            <Badge className={
              connectedAccount.status === "connected"
                ? "bg-success/15 text-success border-success/30 hover:bg-success/15"
                : connectedAccount.status === "blocked"
                ? "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15"
                : "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15"
            }>
              {connectedAccount.status}
            </Badge>
          </div>
          {connectedAccount.balance !== null && (
            <div className="flex items-center justify-center gap-4 text-sm mt-3">
              <div><span className="text-muted-foreground">Balance:</span> <span className="font-mono text-success">${connectedAccount.balance?.toFixed(2)}</span></div>
              <div><span className="text-muted-foreground">Equity:</span> <span className="font-mono">${connectedAccount.equity?.toFixed(2)}</span></div>
            </div>
          )}
          {connectedAccount.status === "blocked" && (
            <div className="flex items-center justify-center gap-2 mt-4 text-sm text-danger">
              <AlertCircle className="w-4 h-4" />
              <span>Account blocked due to unpaid invoice. Please pay to reconnect.</span>
            </div>
          )}
          <Button variant="outline" className="mt-6" onClick={handleDisconnect} disabled={disconnectMutation.isPending}>
            {disconnectMutation.isPending ? "Disconnecting..." : "Disconnect"}
          </Button>
        </motion.div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-6">
          <div className="flex items-center gap-2 mb-6 text-sm text-muted-foreground">
            <Shield className="w-4 h-4" />
            <span>Your credentials are encrypted and stored securely</span>
          </div>

          <form onSubmit={handleConnect} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="login">MT5 Account Login</Label>
              <Input id="login" placeholder="e.g. 12345678" value={login} onChange={(e) => setLogin(e.target.value)} className="h-11 bg-secondary border-border font-mono" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mt5pass">MT5 Password</Label>
              <Input id="mt5pass" type="password" placeholder="Your MT5 password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 bg-secondary border-border" required />
            </div>
            <div className="space-y-2">
              <Label>Server</Label>
              <Select value={server} onValueChange={setServer} required>
                <SelectTrigger className="h-11 bg-secondary border-border">
                  <SelectValue placeholder="Select MT5 server" />
                </SelectTrigger>
                <SelectContent>
                  {servers.map((s) => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" className="w-full h-11 font-semibold" disabled={connectMutation.isPending}>
              <Link2 className="w-4 h-4 mr-2" />
              {connectMutation.isPending ? "Connecting..." : "Connect Account"}
            </Button>
          </form>
        </motion.div>
      )}
    </div>
  );
};

export default ConnectMT5;
