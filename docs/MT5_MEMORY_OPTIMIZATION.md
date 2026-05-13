# MT5 Institutional Memory Optimization

To ensure the Windows VPS remains stable with many MT5 instances, we apply the following optimizations:

## 1. GUI Suppression
- Terminals are started with `/portable` mode.
- We use Windows job objects or desktop isolation (where possible) to keep terminals offscreen.
- Hidden mode via `MT5_TERMINALS_HIDDEN_MODE=true`.

## 2. Configuration (terminal.ini)
Every instance has a customized `terminal.ini` with:
- `NewsEnable=0` (Disable News)
- `SoundEnable=0` (Disable Sounds)
- `ChartsMaxBars=5000` (Reduce history bars)
- `MailEnable=0` (Disable Internal Mail)

## 3. Runtime Cleanup
- **No Charts**: We do not open any chart windows.
- **Minimal Market Watch**: Only the symbols being traded by the strategy are kept in Market Watch.
- **No Indicators/EAs**: No graphical indicators are loaded; all logic resides in the Python bridge.

## 4. Resource Guard
- Max RAM per terminal: 64MB - 128MB.
- Max CPU usage per VPS: 80% (monitored by `HealthMonitor`).
- Stale terminals (disconnected + no positions) are automatically closed.
