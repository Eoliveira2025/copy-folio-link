import { StatCard } from "@/components/StatCard";
import { Link2, BarChart3, CreditCard, Activity, TrendingUp, Copy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";

const recentTrades = [
  { pair: "EURUSD", type: "BUY", lots: "0.15", profit: "+$12.40", time: "2 min ago" },
  { pair: "GBPJPY", type: "SELL", lots: "0.08", profit: "+$8.70", time: "15 min ago" },
  { pair: "XAUUSD", type: "BUY", lots: "0.03", profit: "-$3.20", time: "1h ago" },
  { pair: "USDJPY", type: "SELL", lots: "0.10", profit: "+$22.10", time: "2h ago" },
];

const DashboardHome = () => {
  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground text-sm">Overview of your copy trading account</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="MT5 Status" value="Connected" icon={Link2} trend="up" subtitle="Exness-MT5Real" delay={0} />
        <StatCard title="Strategy" value="Medium" icon={BarChart3} trend="neutral" subtitle="Master Account 02" delay={0.05} />
        <StatCard title="Subscription" value="Active" icon={CreditCard} trend="up" subtitle="23 days remaining" delay={0.1} />
        <StatCard title="Copied Trades" value="147" icon={Copy} trend="up" subtitle="+12 today" delay={0.15} />
      </div>

      {/* Copy Engine Status */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="card-glass rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-success animate-pulse-glow" />
            <h2 className="font-semibold">Copy Engine Status</h2>
          </div>
          <Badge className="bg-success/15 text-success border-success/30 hover:bg-success/15">Running</Badge>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div><span className="text-muted-foreground block">Latency</span><span className="font-mono font-medium">23ms</span></div>
          <div><span className="text-muted-foreground block">Open Positions</span><span className="font-mono font-medium">5</span></div>
          <div><span className="text-muted-foreground block">Today P/L</span><span className="font-mono font-medium text-success">+$39.90</span></div>
          <div><span className="text-muted-foreground block">Win Rate</span><span className="font-mono font-medium">72%</span></div>
        </div>
      </motion.div>

      {/* Recent Trades */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="card-glass rounded-lg p-5">
        <h2 className="font-semibold mb-4">Recent Copied Trades</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-left border-b border-border">
                <th className="pb-3 font-medium">Pair</th>
                <th className="pb-3 font-medium">Type</th>
                <th className="pb-3 font-medium">Lots</th>
                <th className="pb-3 font-medium">Profit</th>
                <th className="pb-3 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.map((trade, i) => (
                <tr key={i} className="border-b border-border/50 last:border-0">
                  <td className="py-3 font-mono font-medium">{trade.pair}</td>
                  <td className="py-3">
                    <Badge variant="outline" className={trade.type === "BUY" ? "text-success border-success/30" : "text-danger border-danger/30"}>
                      {trade.type}
                    </Badge>
                  </td>
                  <td className="py-3 font-mono">{trade.lots}</td>
                  <td className={`py-3 font-mono ${trade.profit.startsWith("+") ? "text-success" : "text-danger"}`}>{trade.profit}</td>
                  <td className="py-3 text-muted-foreground">{trade.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
};

export default DashboardHome;
