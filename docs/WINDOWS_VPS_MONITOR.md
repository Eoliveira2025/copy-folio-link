# Windows VPS Monitor Architecture

The CopyTrade Pro VPS Monitor is a local management tool for the Windows VPS.

## Core Features
1. **Headless Execution**: MT5 terminals run in background mode.
2. **Resource Monitoring**: Track PID, CPU, and RAM for every connected account.
3. **Safety First**: Prevents terminal closure if open positions exist.
4. **Strategy Guard**: Visualizes the "Upgrade Pending" state when switching strategies.

## Component Layout
- `background_terminal_manager.py`: Controls process lifecycle.
- `vps_monitor_service.py`: Exposes data to the UI.
- `monitor_app/`: (Future) Desktop UI implementation (e.g., PySide6 or simple TUI).

## Integration
The monitor talks to the same PostgreSQL and Redis as the Ubuntu backend, ensuring a single source of truth while providing a low-latency local view of the execution layer.
