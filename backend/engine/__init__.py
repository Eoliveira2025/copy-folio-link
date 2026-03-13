"""
CopyTrade Pro — Trade Copy Engine Service

Event-driven microservice that monitors master MT5 accounts for trade events
and replicates them to connected client accounts via Redis queues.

Architecture:
  Master Listener (1 per master) → Redis pub/sub → Trade Distributor → Worker Pool → MT5 Execution

Run: python -m engine.main
"""
