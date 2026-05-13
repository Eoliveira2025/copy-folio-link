"""Test for Institutional Safe Mode."""

import pytest
from uuid import uuid4
from backend.agent_v2.pool.failover_safe_mode import FailoverSafeMode
from backend.agent_v2.config import AgentV2Settings

def test_safe_mode_logic():
    safe_mode = FailoverSafeMode()
    # Mock settings to enable safe mode
    safe_mode.settings.V2_INSTITUTIONAL_SAFE_MODE_ENABLED = True
    
    assert not safe_mode.is_active()
    assert safe_mode.can_open()
    
    safe_mode.activate("Test crash")
    
    assert safe_mode.is_active()
    assert not safe_mode.can_open()
    assert safe_mode.get_reason() == "Test crash"
    
    safe_mode.deactivate()
    assert not safe_mode.is_active()
    assert safe_mode.can_open()

def test_safe_mode_disabled_flag():
    safe_mode = FailoverSafeMode()
    safe_mode.settings.V2_INSTITUTIONAL_SAFE_MODE_ENABLED = False
    
    safe_mode.activate("Test")
    # Even if activated internally, should return false if flag is off
    assert not safe_mode.is_active()
    assert safe_mode.can_open()
