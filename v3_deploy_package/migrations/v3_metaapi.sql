-- Migration V3: MetaApi and CopyFactory integration
-- Tables for cloud-based copy trading

-- MetaApi Accounts (Cloud terminals)
CREATE TABLE IF NOT EXISTS public.metaapi_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    account_id TEXT NOT NULL UNIQUE, -- MetaApi internal account id
    account_name TEXT,
    platform TEXT DEFAULT 'mt5',
    region TEXT DEFAULT 'new-york',
    status TEXT DEFAULT 'DEPLOYING',
    connection_status TEXT DEFAULT 'DISCONNECTED',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- MetaApi Masters (Strategies in CopyFactory)
CREATE TABLE IF NOT EXISTS public.metaapi_masters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES public.metaapi_accounts(id),
    strategy_id TEXT NOT NULL UNIQUE, -- CopyFactory strategy id
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- CopyFactory Subscriptions (Client connections)
CREATE TABLE IF NOT EXISTS public.copyfactory_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    subscriber_account_id UUID NOT NULL REFERENCES public.metaapi_accounts(id),
    master_strategy_id TEXT NOT NULL REFERENCES public.metaapi_masters(strategy_id),
    subscription_id TEXT NOT NULL UNIQUE, -- CopyFactory subscription id
    risk_config JSONB DEFAULT '{"type": "fixed_lot", "value": 0.01}'::jsonb,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Basic indexes
CREATE INDEX IF NOT EXISTS idx_metaapi_accounts_user ON public.metaapi_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_copyfactory_subs_user ON public.copyfactory_subscriptions(user_id);
