import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";

export function useAffiliates() {
  return useQuery({
    queryKey: ["admin", "affiliates"],
    queryFn: () => api.adminListAffiliates(),
  });
}

export function useCreateAffiliate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: any) => api.adminCreateAffiliate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliates"] });
      toast.success("Afiliado criado com sucesso");
    },
    onError: (error: any) => {
      toast.error(error.message || "Erro ao criar afiliado");
    },
  });
}

export function useResetAffiliatePassword() {
  return useMutation({
    mutationFn: (id: string) => api.adminResetAffiliatePassword(id),
    onSuccess: () => {
      toast.success("Senha resetada para copy123");
    },
  });
}

export function useAssignReferral() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { affiliate_id: string; user_id: string }) => api.adminAssignReferral(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliates"] });
      toast.success("Indicação vinculada com sucesso");
    },
  });
}

export function useAffiliateDashboard(affiliateId?: string) {
  return useQuery({
    queryKey: ["admin", "affiliate-dashboard", affiliateId],
    queryFn: () => api.adminGetAffiliateDashboard(affiliateId!),
    enabled: !!affiliateId,
  });
}

export function useMyAffiliateDashboard() {
  return useQuery({
    queryKey: ["affiliate", "dashboard"],
    queryFn: () => api.affiliateGetDashboard(),
  });
}
