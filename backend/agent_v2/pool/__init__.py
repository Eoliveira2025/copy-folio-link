"""V2 pool subsystem.

Segmented by (master_id, strategy_id). A pool created for LOW will *never*
serve PRO accounts. Cross-strategy mixing is prevented at:
  - DB level (FKs + future CHECKs)
  - Allocator level (filters by strategy_id)
  - Pool object level (refuses accounts whose strategy_id mismatches)
"""
