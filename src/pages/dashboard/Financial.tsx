import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CreditCard, Download } from "lucide-react";
import { motion } from "framer-motion";

const invoices = [
  { id: "INV-001", date: "2026-03-01", due: "2026-04-02", amount: "$49.90", status: "Paid" },
  { id: "INV-002", date: "2026-04-01", due: "2026-05-02", amount: "$49.90", status: "Pending" },
  { id: "INV-003", date: "2026-02-01", due: "2026-03-02", amount: "$49.90", status: "Paid" },
];

const statusStyle: Record<string, string> = {
  Paid: "bg-success/15 text-success border-success/30 hover:bg-success/15",
  Pending: "bg-warning/15 text-warning border-warning/30 hover:bg-warning/15",
  Overdue: "bg-danger/15 text-danger border-danger/30 hover:bg-danger/15",
};

const Financial = () => {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Financial</h1>
        <p className="text-muted-foreground text-sm">Manage your subscription and invoices</p>
      </div>

      {/* Subscription Card */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <CreditCard className="w-5 h-5 text-primary" />
            <h2 className="font-semibold">Current Subscription</h2>
          </div>
          <Badge className="bg-success/15 text-success border-success/30 hover:bg-success/15">Active</Badge>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div><span className="text-muted-foreground block">Plan</span><span className="font-medium">Professional</span></div>
          <div><span className="text-muted-foreground block">Price</span><span className="font-mono font-medium">$49.90/mo</span></div>
          <div><span className="text-muted-foreground block">Next Billing</span><span className="font-mono">Apr 12, 2026</span></div>
          <div><span className="text-muted-foreground block">Trial</span><span className="text-muted-foreground">Completed</span></div>
        </div>
      </motion.div>

      {/* Invoices */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card-glass rounded-lg p-6">
        <h2 className="font-semibold mb-4">Invoices</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-left border-b border-border">
                <th className="pb-3 font-medium">Invoice</th>
                <th className="pb-3 font-medium">Issue Date</th>
                <th className="pb-3 font-medium">Due Date</th>
                <th className="pb-3 font-medium">Amount</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-border/50 last:border-0">
                  <td className="py-3 font-mono font-medium">{inv.id}</td>
                  <td className="py-3 text-muted-foreground">{inv.date}</td>
                  <td className="py-3 text-muted-foreground">{inv.due}</td>
                  <td className="py-3 font-mono">{inv.amount}</td>
                  <td className="py-3"><Badge className={statusStyle[inv.status]}>{inv.status}</Badge></td>
                  <td className="py-3"><Button variant="ghost" size="icon" className="h-8 w-8"><Download className="w-4 h-4" /></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
};

export default Financial;
