import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { TrendingUp } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import type { TermsPublic } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

const TermsOfService = () => {
  const [terms, setTerms] = useState<TermsPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getActiveTerms()
      .then(setTerms)
      .catch((err) => setError(err.message || "Failed to load terms"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link to="/" className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-primary-foreground" />
          </div>
          <span className="text-2xl font-bold">CopyTrade Pro</span>
        </Link>

        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-[400px]" />
          </div>
        ) : error ? (
          <div className="card-glass rounded-lg p-8 text-center">
            <p className="text-muted-foreground">{error}</p>
          </div>
        ) : terms ? (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="text-3xl font-bold mb-2">{terms.title}</h1>
            <p className="text-sm text-muted-foreground mb-8">
              Version {terms.version} · {terms.company_name} · Last updated{" "}
              {new Date(terms.updated_at).toLocaleDateString("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
            </p>
            <div
              className="prose prose-invert max-w-none [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mt-8 [&_h1]:mb-4 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mt-6 [&_h2]:mb-3 [&_h3]:text-lg [&_h3]:font-medium [&_h3]:mt-4 [&_h3]:mb-2 [&_p]:text-muted-foreground [&_p]:mb-4 [&_p]:leading-relaxed [&_ul]:list-disc [&_ul]:ml-6 [&_ul]:mb-4 [&_ol]:list-decimal [&_ol]:ml-6 [&_ol]:mb-4 [&_li]:text-muted-foreground [&_li]:mb-1 [&_strong]:text-foreground [&_a]:text-primary [&_a]:underline"
              dangerouslySetInnerHTML={{ __html: terms.content }}
            />
          </motion.div>
        ) : null}
      </div>
    </div>
  );
};

export default TermsOfService;
