import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AdminRoute } from "@/components/AdminRoute";
import Index from "./pages/Index";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import TermsOfService from "./pages/TermsOfService";
import { DashboardLayout } from "./components/DashboardLayout";
import DashboardHome from "./pages/dashboard/DashboardHome";
import ConnectMT5 from "./pages/dashboard/ConnectMT5";
import Strategies from "./pages/dashboard/Strategies";
import Financial from "./pages/dashboard/Financial";
import SettingsPage from "./pages/dashboard/SettingsPage";
import Plans from "./pages/dashboard/Plans";
import AdminPanel from "./pages/admin/AdminPanel";
import OperationsDashboard from "./pages/admin/OperationsDashboard";
import AdminBilling from "./pages/admin/AdminBilling";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/terms-of-service" element={<TermsOfService />} />
            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardHome />} />
              <Route path="/dashboard/connect" element={<ConnectMT5 />} />
              <Route path="/dashboard/strategies" element={<Strategies />} />
              <Route path="/dashboard/plans" element={<Plans />} />
              <Route path="/dashboard/financial" element={<Financial />} />
              <Route path="/dashboard/settings" element={<SettingsPage />} />
              <Route
                path="/admin"
                element={
                  <AdminRoute>
                    <AdminPanel />
                  </AdminRoute>
                }
              />
              <Route
                path="/admin/operations"
                element={
                  <AdminRoute>
                    <OperationsDashboard />
                  </AdminRoute>
                }
              />
              <Route
                path="/admin/billing"
                element={
                  <AdminRoute>
                    <AdminBilling />
                  </AdminRoute>
                }
              />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
