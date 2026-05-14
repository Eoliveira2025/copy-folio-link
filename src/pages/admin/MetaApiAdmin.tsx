import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CheckCircle2, Cloud, RefreshCcw } from "lucide-react";

const MetaApiAdmin = () => {
  const { data: status, isLoading } = useQuery({
    queryKey: ["metaapi-status"],
    queryFn: async () => {
      // Placeholder for API call
      return {
        enabled: true,
        copyfactory_enabled: true,
        region: "new-york",
        accounts_count: 0,
        masters_count: 0
      };
    },
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold tracking-tight">MetaApi V3 Management</h2>
        <Button className="flex items-center gap-2">
          <RefreshCcw className="h-4 w-4" />
          Sync All
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cloud Status</CardTitle>
            <Cloud className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="text-2xl font-bold">{status?.enabled ? "Active" : "Disabled"}</div>
              {status?.enabled ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <AlertCircle className="h-5 w-5 text-red-500" />
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Region: {status?.region}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">CopyFactory</CardTitle>
            <RefreshCcw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status?.copyfactory_enabled ? "Running" : "Stopped"}</div>
            <Badge variant={status?.copyfactory_enabled ? "default" : "destructive"} className="mt-1">
              {status?.copyfactory_enabled ? "OK" : "Error"}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Managed Accounts</CardTitle>
            <Cloud className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status?.accounts_count}</div>
            <p className="text-xs text-muted-foreground mt-1">Across all strategies</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Connected Cloud Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-10 text-muted-foreground">
            No cloud accounts connected yet. Use the feature flags to enable V3 for specific users.
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MetaApiAdmin;
