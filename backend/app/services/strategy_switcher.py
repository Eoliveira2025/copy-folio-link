"""Strategy switching service for plan upgrades.

Handles automatic strategy re-mapping when a user's plan changes,
including unsubscribing from the old master and subscribing to the new one.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.strategy import Strategy, MasterAccount, UserStrategy, StrategyLevel
from app.models.mt5_account import MT5Account, MT5Status
from app.models.plan import Plan
from app.services import copy_engine

logger = logging.getLogger("app.services.strategy_switcher")

# Maps plan allowed_strategies to the highest strategy level the plan supports.
# The plan's first allowed strategy (by tier) determines the default master.
STRATEGY_TIER_ORDER = [
    StrategyLevel.LOW,
    StrategyLevel.MEDIUM,
    StrategyLevel.HIGH,
    StrategyLevel.PRO,
    StrategyLevel.EXPERT,
    StrategyLevel.EXPERT_PRO,
]


def get_highest_strategy_for_plan(plan: Plan) -> str | None:
    """Return the highest strategy level allowed by the plan."""
    allowed = set(plan.allowed_strategies or [])
    for level in reversed(STRATEGY_TIER_ORDER):
        if level.value in allowed:
            return level.value
    return None


async def switch_user_strategy_for_plan(
    user_id,
    new_plan: Plan,
    db: AsyncSession,
) -> dict:
    """
    Switch a user's active strategy to match their new plan.

    Steps:
    1. Determine the highest strategy the new plan allows
    2. Find the corresponding Strategy + MasterAccount
    3. Deactivate the user's current UserStrategy
    4. Activate the new one
    5. Dispatch Redis commands to unsubscribe/subscribe on connected MT5 accounts
    """
    target_level = get_highest_strategy_for_plan(new_plan)
    if not target_level:
        logger.warning(f"Plan '{new_plan.name}' has no allowed strategies")
        return {"switched": False, "reason": "Plan has no allowed strategies"}

    # Find the strategy record
    strat_result = await db.execute(
        select(Strategy).where(Strategy.level == StrategyLevel(target_level))
    )
    new_strategy = strat_result.scalar_one_or_none()
    if not new_strategy:
        logger.warning(f"Strategy level '{target_level}' not found in DB")
        return {"switched": False, "reason": f"Strategy '{target_level}' not found"}

    # Find the master account for the new strategy
    ma_result = await db.execute(
        select(MasterAccount).where(MasterAccount.strategy_id == new_strategy.id)
    )
    new_master = ma_result.scalar_one_or_none()
    if not new_master:
        logger.warning(f"No master account for strategy '{target_level}'")
        return {"switched": False, "reason": f"No master for '{target_level}'"}

    # Get current active strategy for unsubscription
    current_us_result = await db.execute(
        select(UserStrategy).where(
            UserStrategy.user_id == user_id,
            UserStrategy.is_active == True,
        )
    )
    current_user_strategies = current_us_result.scalars().all()

    # Deactivate all current strategies
    for us in current_user_strategies:
        us.is_active = False

    # Activate new strategy
    db.add(UserStrategy(
        user_id=user_id,
        strategy_id=new_strategy.id,
        is_active=True,
    ))

    # Get all connected MT5 accounts for this user
    mt5_result = await db.execute(
        select(MT5Account).where(
            MT5Account.user_id == user_id,
            MT5Account.status == MT5Status.CONNECTED,
        )
    )
    mt5_accounts = mt5_result.scalars().all()

    # Dispatch Redis commands for each connected account
    for account in mt5_accounts:
        try:
            # Unsubscribe from old strategy
            copy_engine.dispatch_unsubscribe_strategy(
                account_id=str(account.id),
                client_login=account.login,
            )
            # Subscribe to new strategy
            copy_engine.dispatch_subscribe_strategy(
                account_id=str(account.id),
                client_login=account.login,
                strategy_level=new_strategy.level.value,
                master_login=new_master.login,
                risk_multiplier=new_strategy.risk_multiplier,
            )
        except Exception as e:
            logger.error(f"Failed to switch strategy for MT5 account {account.login}: {e}")

    # Also publish on the strategy_change channel for any listeners
    try:
        import json
        r = copy_engine._get_redis()
        r.publish("copytrade:strategy_change", json.dumps({
            "action": "switch",
            "user_id": str(user_id),
            "new_strategy": new_strategy.level.value,
            "new_master_login": new_master.login,
            "affected_accounts": [a.login for a in mt5_accounts],
        }))
    except Exception as e:
        logger.error(f"Failed to publish strategy_change event: {e}")

    logger.info(
        f"User {user_id} strategy switched to {new_strategy.level.value} "
        f"(master {new_master.login}), {len(mt5_accounts)} accounts updated"
    )

    return {
        "switched": True,
        "new_strategy": new_strategy.level.value,
        "new_master_login": new_master.login,
        "accounts_updated": len(mt5_accounts),
    }
