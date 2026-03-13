import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Lock, Check, TrendingUp, BarChart3 } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";

interface Strategy {
  name: string;
  description: string;
  risk: string;
  expectedReturn: string;
  locked: boolean;
}

const strategies: Strategy[] = [
  { name: "Low", description: "Conservative approach with minimal risk", risk: "Low", expectedReturn: "5-10% / month", locked: false },
  { name: "Medium", description: "Balanced risk-reward ratio", risk: "Medium", expectedReturn: "10-20% / month", locked: false },
  { name: "High", description: "Aggressive trading with higher returns", risk: "High", expectedReturn: "20-35% / month", locked: false },
  { name: "Pro", description: "Professional strategy for experienced traders", risk: "Very High", expectedReturn: "30-50% / month", locked: true },
  { name: "Expert", description: "Expert-level with advanced algorithms", risk: "Very High", expectedReturn: "40-60% / month", locked: true },
  { name: "Expert Pro", description: "Maximum performance strategy", risk: "Extreme", expectedReturn: "50-80% / month", locked: true },
];

const riskColors: Record<string, string> = {
  Low: "text-success border-success/30",
  Medium: "text-warning border-warning/30",
  High: "text-danger border-danger/30",
  "Very High": "text-danger border-danger/30",
  Extreme: "text-danger border-danger/30",
};

const Strategies = () => {
  const [active, setActive] = useState("Medium");

  const handleSelect = (name: string, locked: boolean) => {
    if (locked) {
      toast.error("This strategy is locked. Contact admin to unlock.");
      return;
    }
    setActive(name);
    toast.success(`Strategy changed to ${name}`);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Strategies</h1>
        <p className="text-muted-foreground text-sm">Choose a copy trading strategy level</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies.map((s, i) => (
          <motion.div
            key={s.name}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`card-glass rounded-lg p-5 relative ${active === s.name ? "ring-2 ring-primary glow-green" : ""} ${s.locked ? "opacity-60" : ""}`}
          >
            {s.locked && (
              <div className="absolute top-3 right-3">
                <Lock className="w-4 h-4 text-muted-foreground" />
              </div>
            )}
            {active === s.name && (
              <div className="absolute top-3 right-3">
                <Check className="w-5 h-5 text-primary" />
              </div>
            )}

            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="w-5 h-5 text-primary" />
              <h3 className="font-bold text-lg">{s.name}</h3>
            </div>
            <p className="text-muted-foreground text-sm mb-4">{s.description}</p>

            <div className="space-y-2 text-sm mb-4">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Risk Level</span>
                <Badge variant="outline" className={riskColors[s.risk]}>{s.risk}</Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Expected Return</span>
                <span className="font-mono text-success">{s.expectedReturn}</span>
              </div>
            </div>

            <Button
              className="w-full"
              variant={active === s.name ? "default" : "outline"}
              disabled={s.locked}
              onClick={() => handleSelect(s.name, s.locked)}
            >
              {s.locked ? "Locked" : active === s.name ? "Active" : "Select"}
            </Button>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default Strategies;
