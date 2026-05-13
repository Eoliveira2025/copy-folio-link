"""Test for Execution Deduplication."""

import pytest
from uuid import uuid4
from backend.agent_v2.pool.execution_deduplication_service import ExecutionDeduplicationService

def test_deduplication():
    service = ExecutionDeduplicationService()
    service.settings.V2_EXECUTION_DEDUP_ENABLED = True
    
    aid = uuid4()
    sid = uuid4()
    
    # First execution
    is_dup = service.is_duplicate(aid, 12345, "OPEN", "EURUSD", 0.1, sid)
    assert not is_dup
    
    # Second execution (exact same params)
    is_dup = service.is_duplicate(aid, 12345, "OPEN", "EURUSD", 0.1, sid)
    assert is_dup
    
    # Different ticket
    is_dup = service.is_duplicate(aid, 12346, "OPEN", "EURUSD", 0.1, sid)
    assert not is_dup
    
    # Different volume
    is_dup = service.is_duplicate(aid, 12345, "OPEN", "EURUSD", 0.11, sid)
    assert not is_dup
