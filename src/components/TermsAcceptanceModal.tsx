import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api } from "@/lib/api";
import type { TermsCheckResult } from "@/lib/api";
import { toast } from "sonner";
import { Shield } from "lucide-react";

interface TermsAcceptanceModalProps {
  onAccepted: () => void;
}

export function TermsAcceptanceModal({ onAccepted }: TermsAcceptanceModalProps) {
  const [checkResult, setCheckResult] = useState<TermsCheckResult | null>(null);
  const [termsContent, setTermsContent] = useState<string>("");
  const [accepted, setAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.checkTermsAcceptance().then((result) => {
      if (result.needs_acceptance && result.terms_id) {
        setOpen(true);
        setCheckResult(result);
        // Fetch full terms content
        api.getActiveTerms().then((terms) => setTermsContent(terms.content)).catch(() => {});
      }
    }).catch(() => {});
  }, []);

  const handleAccept = async () => {
    if (!checkResult?.terms_id) return;
    setSubmitting(true);
    try {
      await api.acceptTerms(checkResult.terms_id);
      toast.success("Terms accepted");
      setOpen(false);
      onAccepted();
    } catch (err: any) {
      toast.error(err.message || "Failed to accept terms");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="max-w-2xl [&>button]:hidden" onPointerDownOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-9 h-9 rounded-lg bg-primary/15 flex items-center justify-center">
              <Shield className="w-5 h-5 text-primary" />
            </div>
            <DialogTitle className="text-xl">Terms and Conditions Updated</DialogTitle>
          </div>
          <DialogDescription>
            Please review and accept the updated Terms and Conditions (v{checkResult?.version}) to continue using the platform.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[400px] rounded-md border border-border bg-muted/30 p-4">
          <div
            className="text-sm [&_h1]:text-lg [&_h1]:font-bold [&_h1]:mt-6 [&_h1]:mb-3 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-4 [&_h2]:mb-2 [&_p]:text-muted-foreground [&_p]:mb-3 [&_p]:leading-relaxed [&_ul]:list-disc [&_ul]:ml-5 [&_ul]:mb-3 [&_ol]:list-decimal [&_ol]:ml-5 [&_ol]:mb-3 [&_li]:text-muted-foreground [&_li]:mb-1 [&_strong]:text-foreground"
            dangerouslySetInnerHTML={{ __html: termsContent }}
          />
        </ScrollArea>

        <div className="flex items-start gap-3 mt-2">
          <Checkbox
            id="modal-terms"
            checked={accepted}
            onCheckedChange={(c) => setAccepted(c === true)}
            className="mt-0.5"
          />
          <Label htmlFor="modal-terms" className="text-sm text-muted-foreground font-normal leading-relaxed cursor-pointer">
            I have read and agree to the updated Terms and Conditions
          </Label>
        </div>

        <Button
          onClick={handleAccept}
          disabled={!accepted || submitting}
          className="w-full mt-2"
        >
          {submitting ? "Accepting..." : "Accept and Continue"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
