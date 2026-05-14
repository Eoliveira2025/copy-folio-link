# MetaApi V3 Architecture - CopyTrade Pro

This document describes the V3 architecture based on MetaApi and CopyFactory.

## Overview
V3 is designed to provide a cloud-native, high-frequency, and scalable copy trading solution that bypasses the need for local Windows/MT5 installations for every account.

## Key Components

### 1. MetaApi Cloud SDK
- Handles the connection to MetaTrader 4/5 terminals in the cloud.
- Provides a REST and WebSocket API for real-time trade monitoring and execution.
- Manages provisioning of "terminals" in different geographic regions (NY, London, etc.) to minimize latency.

### 2. CopyFactory Service
- MetaApi's specialized engine for multi-account trade copying.
- **Strategies**: Define the master source of signals.
- **Subscriptions**: Link client accounts to specific strategies with risk management.
- **Risk Management**: Handles lot sizing (fixed, proportional, risk-based) and symbol mapping at the API level.

### 3. Backend Integration (FastAPI)
- **MetaApiClient**: Wrapper around MetaApi SDK for account lifecycle management.
- **CopyFactoryService**: Manages the mapping between our internal `strategies` and MetaApi `copyfactory_strategies`.
- **Database**: 
  - `metaapi_accounts`: Stores MetaApi-specific account metadata and status.
  - `metaapi_masters`: Maps our internal master accounts to CopyFactory strategies.
  - `copyfactory_subscriptions`: Tracks client links and risk settings.

## Workflow

1. **Account Provisioning**:
   - User adds account credentials.
   - System registers account in MetaApi.
   - MetaApi spins up a cloud terminal.

2. **Master Setup**:
   - Admin designates an account as a "V3 Master".
   - System creates a `strategy` in CopyFactory.

3. **Client Subscription**:
   - User subscribes to a V3 strategy.
   - System creates a `subscription` in CopyFactory.
   - CopyFactory handles all logic for copying orders from Master to Subscriber.

4. **Event Monitoring**:
   - Webhooks from MetaApi update account status and trade history in our database.

## Coexistence with V1
- V1 continues to use the local Windows Bridge/Executor.
- V3 uses the Cloud SDK.
- Users can choose between V1 (Traditional) and V3 (Cloud) based on their subscription plan.
- **Feature Flag**: `V3_FEATURE_FLAG` controls UI visibility and backend activation.

## Performance & Scalability
- **Latency**: Sub-50ms copy time within the same cloud region.
- **Throughput**: Capable of handling thousands of accounts without vertical scaling bottlenecks.
- **Resilience**: MetaApi handles terminal crashes and automatic reconnection.
