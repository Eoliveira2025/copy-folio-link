import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search, RefreshCw, Users, BarChart3, Server, Shield } from "lucide-react";
import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAdminUsers,
  useAdminCheckPayments,
  useAdminUnblockUser,
  useAdminDashboard,
} from "@/hooks/use-api";
import { StatCard } from "@/components/StatCard";

const statusStyle: Record<string, string> = {
  active: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  trial: "bg-info/15 text-info border-info/30 hover:bg-info/15",
  blocked: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
  expired: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  connected: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  disconnected: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
};

const AdminPanel = () => {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const { data: users, isLoading: usersLoading } = useAdminUsers(debouncedSearch);
  const { data: dashboard, isLoading: dashLoading } = useAdminDashboard();
  const checkPayments = useAdminCheckPayments();
  const unblockUser = useAdminUnblockUser();

  const handleSearch = (val: string) => {
    setSearch(val);
    // Simple debounce
    setTimeout(() => setDebouncedSearch(val), 300);
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin Panel</h1>
          <p className="text-muted-foreground text-sm">Manage users, strategies, and billing</p>
        </div>
        <Button
          variant="outline"
          onClick={() => checkPayments.mutate()}
          disabled={checkPayments.isPending}
          className="gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${checkPayments.isPending ? "animate-spin" : ""}`} />
          {checkPayments.isPending ? "Checking..." : "Check Payments Now"}
        </Button>
      </div>

      {/* Dashboard Stats */}
      {dashLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : dashboard ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Total Users" value={String(dashboard.total_users)} icon={Users} delay={0} />
          <StatCard title="Active" value={String(dashboard.active_accounts)} icon={Shield} trend="up" delay={0.05} />
          <StatCard title="Trial" value={String(dashboard.trial_accounts)} icon={BarChart3} trend="neutral" subtitle="Free trial" delay={0.1} />
          <StatCard title="Blocked" value={String(dashboard.blocked_accounts)} icon={Server} trend="down" subtitle={`${dashboard.pending_invoices} pending invoices`} delay={0.15} />
        </div>
      ) : null}

      <Tabs defaultValue="users">
        <TabsList className="bg-secondary">
          <TabsTrigger value="users" className="gap-2"><Users className="w-4 h-4" /> Users</TabsTrigger>
          <TabsTrigger value="servers" className="gap-2"><Server className="w-4 h-4" /> Servers</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-4 space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search by email or MT5 login..."
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-9 h-10 bg-secondary border-border"
            />
          </div>

          {usersLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted-foreground text-left border-b border-border bg-muted/30">
                      <th className="p-3 font-medium">Email</th>
                      <th className="p-3 font-medium">MT5 Login</th>
                      <th className="p-3 font-medium">MT5 Status</th>
                      <th className="p-3 font-medium">Subscription</th>
                      <th className="p-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users?.map((user) => (
                      <tr key={user.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                        <td className="p-3">{user.email}</td>
                        <td className="p-3 font-mono">
                          {user.mt5_accounts.length > 0
                            ? user.mt5_accounts.map((a) => a.login).join(", ")
                            : "—"}
                        </td>
                        <td className="p-3">
                          {user.mt5_accounts.length > 0 ? (
                            user.mt5_accounts.map((a) => (
                              <Badge key={a.login} className={statusStyle[a.status] || ""}>
                                {a.status}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-muted-foreground">No account</span>
                          )}
                        </td>
                        <td className="p-3">
                          {user.subscription_status ? (
                            <Badge className={statusStyle[user.subscription_status] || ""}>
                              {user.subscription_status}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="p-3">
                          <div className="flex gap-1">
                            {user.subscription_status === "blocked" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => unblockUser.mutate(user.id)}
                                disabled={unblockUser.isPending}
                              >
                                Unblock
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {(!users || users.length === 0) && (
                      <tr>
                        <td colSpan={5} className="p-6 text-center text-muted-foreground">
                          No users found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </TabsContent>

        <TabsContent value="servers" className="mt-4">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card-glass rounded-lg p-6 space-y-4">
            <h3 className="font-semibold">MT5 Servers</h3>
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
