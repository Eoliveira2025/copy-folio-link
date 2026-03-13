import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search, RefreshCw, Users, BarChart3, CreditCard, Server } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";

const mockUsers = [
  { id: 1, email: "trader1@example.com", mt5: "12345678", strategy: "Medium", status: "Active", billing: "Paid", mt5Status: "Connected" },
  { id: 2, email: "trader2@example.com", mt5: "87654321", strategy: "Low", status: "Active", billing: "Pending", mt5Status: "Connected" },
  { id: 3, email: "trader3@example.com", mt5: "11223344", strategy: "High", status: "Blocked", billing: "Overdue", mt5Status: "Disconnected" },
  { id: 4, email: "pro@example.com", mt5: "99887766", strategy: "Pro", status: "Active", billing: "Paid", mt5Status: "Connected" },
];

const masterMappings = [
  { strategy: "Low", master: "Master Account 01", account: "10001" },
  { strategy: "Medium", master: "Master Account 02", account: "10002" },
  { strategy: "High", master: "Master Account 03", account: "10003" },
  { strategy: "Pro", master: "Master Account 04", account: "10004" },
  { strategy: "Expert", master: "Master Account 05", account: "10005" },
  { strategy: "Expert Pro", master: "Master Account 06", account: "10006" },
];

const statusStyle: Record<string, string> = {
  Active: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  Blocked: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  Paid: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  Pending: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  Overdue: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  Connected: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  Disconnected: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
};

const AdminPanel = () => {
  const [search, setSearch] = useState("");
  const filtered = mockUsers.filter(u => u.email.includes(search) || u.mt5.includes(search));

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin Panel</h1>
          <p className="text-muted-foreground text-sm">Manage users, strategies, and billing</p>
        </div>
        <Button variant="outline" onClick={() => toast.success("Payment check triggered")} className="gap-2">
          <RefreshCw className="w-4 h-4" /> Check Payments Now
        </Button>
      </div>

      <Tabs defaultValue="users">
        <TabsList className="bg-secondary">
          <TabsTrigger value="users" className="gap-2"><Users className="w-4 h-4" /> Users</TabsTrigger>
          <TabsTrigger value="strategies" className="gap-2"><BarChart3 className="w-4 h-4" /> Strategy Mapping</TabsTrigger>
          <TabsTrigger value="servers" className="gap-2"><Server className="w-4 h-4" /> Servers</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-4 space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input placeholder="Search by email or MT5 login..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-10 bg-secondary border-border" />
          </div>

          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                    <th className="p-3 font-medium">Email</th>
                    <th className="p-3 font-medium">MT5 Login</th>
                    <th className="p-3 font-medium">Strategy</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Billing</th>
                    <th className="p-3 font-medium">MT5</th>
                    <th className="p-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((user) => (
                    <tr key={user.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                      <td className="p-3">{user.email}</td>
                      <td className="p-3 font-mono">{user.mt5}</td>
                      <td className="p-3">{user.strategy}</td>
                      <td className="p-3"><Badge className={statusStyle[user.status]}>{user.status}</Badge></td>
                      <td className="p-3"><Badge className={statusStyle[user.billing]}>{user.billing}</Badge></td>
                      <td className="p-3"><Badge className={statusStyle[user.mt5Status]}>{user.mt5Status}</Badge></td>
                      <td className="p-3">
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => toast.success("Strategy unlocked")}>Unlock</Button>
                          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => toast.success("Account unblocked")}>Unblock</Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        </TabsContent>

        <TabsContent value="strategies" className="mt-4">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                    <th className="p-3 font-medium">Strategy</th>
                    <th className="p-3 font-medium">Master Account</th>
                    <th className="p-3 font-medium">Account ID</th>
                    <th className="p-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {masterMappings.map((m) => (
                    <tr key={m.strategy} className="border-b border-border/50 last:border-0">
                      <td className="p-3 font-medium">{m.strategy}</td>
                      <td className="p-3">{m.master}</td>
                      <td className="p-3 font-mono">{m.account}</td>
                      <td className="p-3"><Button variant="ghost" size="sm" className="h-7 text-xs">Edit</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        </TabsContent>

        <TabsContent value="servers" className="mt-4">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">MT5 Servers</h3>
              <Button size="sm">Add Server</Button>
            </div>
            <div className="space-y-2">
              {["Exness-MT5Real", "Exness-MT5Real2", "Exness-MT5Real3", "Exness-MT5Trial"].map((s) => (
                <div key={s} className="flex items-center justify-between p-3 rounded-md bg-muted/30">
                  <span className="font-mono text-sm">{s}</span>
                  <Badge className="bg-success/15 text-success border-success/30 hover:bg-success/15">Active</Badge>
                </div>
              ))}
            </div>
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminPanel;
