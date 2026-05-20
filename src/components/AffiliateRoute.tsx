import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export function AffiliateRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Allow both admins and affiliates to see this route for testing/management
  if (!user || (user.role !== "affiliate" && user.role !== "admin")) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
