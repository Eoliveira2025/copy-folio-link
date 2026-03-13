import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { motion } from "framer-motion";

const SettingsPage = () => {
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground text-sm">Manage your account preferences</p>
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card-glass rounded-lg p-6 space-y-6">
        <h2 className="font-semibold">Profile</h2>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Email</Label>
            <Input defaultValue="trader@example.com" className="h-11 bg-secondary border-border" disabled />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>New Password</Label>
              <Input type="password" placeholder="••••••••" className="h-11 bg-secondary border-border" />
            </div>
            <div className="space-y-2">
              <Label>Confirm Password</Label>
              <Input type="password" placeholder="••••••••" className="h-11 bg-secondary border-border" />
            </div>
          </div>
          <Button>Update Password</Button>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card-glass rounded-lg p-6 space-y-6">
        <h2 className="font-semibold">Notifications</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div><Label>Trade Notifications</Label><p className="text-xs text-muted-foreground">Get notified when trades are copied</p></div>
            <Switch defaultChecked />
          </div>
          <div className="flex items-center justify-between">
            <div><Label>Billing Alerts</Label><p className="text-xs text-muted-foreground">Payment reminders and invoice alerts</p></div>
            <Switch defaultChecked />
          </div>
          <div className="flex items-center justify-between">
            <div><Label>Connection Alerts</Label><p className="text-xs text-muted-foreground">MT5 connection status changes</p></div>
            <Switch defaultChecked />
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default SettingsPage;
