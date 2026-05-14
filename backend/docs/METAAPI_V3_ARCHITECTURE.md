# MetaApi V3 Architecture

## Overview
This document describes the V3 architecture for CopyTrade Pro, integrating MetaApi and CopyFactory for cloud-based MT5 connectivity and copy trading.

## Components

### Backend Services (`backend/app/services/metaapi/`)

- `client.py`: MetaApi SDK integration, account management.
- `copyfactory.py`: CopyFactory integration, strategy and subscription management.
- `provisioning.py`: Orchestration for account onboarding and deployment.
- `risk_mapper.py`: Maps system strategy levels to CopyFactory risk settings.
- `fallback.py`: Logic for switching between V1 (Local) and V3 (Cloud).

### Data Model
- `metaapi_accounts`: Stores MetaApi-specific account metadata.
- `metaapi_masters`: Maps system strategies to MetaApi/CopyFactory master accounts.
- `copyfactory_subscriptions`: Tracks CopyFactory subscription status and settings.
- `metaapi_events`: Log for MetaApi webhooks and internal events.

## Features
- Modular design parallel to V1.
- Feature flags for gradual rollout.
- Cloud-based execution reducing Windows VPS dependency.
- Automated provisioning via Celery.

## Feature Flags
- `METAAPI_ENABLED`: Global toggle for V3 features.
- `COPYFACTORY_ENABLED`: Global toggle for CopyFactory integration.
