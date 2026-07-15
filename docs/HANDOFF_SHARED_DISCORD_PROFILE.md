# Shared Discord Profile Handoff

Last updated: 2026-07-15

## Outcome

Discord Message Collection and V6 now use one authenticated Edge profile:

`C:\Users\gregd\Codex Projects\Webull Tradebot v6\local_state\edge_discord_profile_v6_readonly`

Port `9227` is the standard port. The collection sweep also detects an already-running exact Casey channel on legacy port `9225`. The same profile must not be opened on both ports simultaneously because Edge locks a user-data directory.

## Operator behavior

- `START_V6_OPERATOR.bat` continues to open the shared profile on `9227` and starts the V6 listener.
- `collect_messages.bat` checks whether the V6 listener PID belongs to a running process. If so, it blocks and tells the operator to stop V6 first.
- When the listener is stopped, collection searches `9227` and then `9225` for the exact Casey channel.
- If neither port has that channel, collection opens the shared profile on `9227`.
- The historical sweep remains read-only and writes only to `data\messages.sqlite3`.

## Files changed

- `discord_collector.py` — added exact-channel debug-port detection.
- `launch_discord.bat` — switched the default to `9227` and the V6 persistent profile.
- `collect_messages.bat` — added listener exclusion, port detection, and explicit selected-port collection.
- `tests/test_discord_collector.py` — added shared-profile assertions and preferred-port coverage.
- Collection and V6 handoff documents — recorded the unified workflow.

## Verification

- Focused collector suite: `4 passed`.
- A read-only probe against the open operator browser found the exact Casey channel on `9227`.
- The V6 listener PID file was present but stale during verification; the guard correctly treats only a PID belonging to a running process as active.
- No collection sweep was run during this implementation, so the archive was not changed.
- No existing V6 runtime code was changed.

## Boundaries

- Do not run the continuous V6 listener and a historical scroll-back sweep at the same time.
- Do not launch the shared Edge profile on `9225` and `9227` simultaneously.
- Nothing was staged, committed, pushed, or published.

## Next exact step

If message collection is needed, run `C:\Users\gregd\Codex Projects\Webull Tradebot v6\STOP_V6_OPERATOR.bat`, then run `C:\Users\gregd\Codex Projects\Webull Tradebot v5\collect_messages.bat`. After collection, reopen V6 with `START_V6_OPERATOR.bat`.

If the July 15 archive is already complete, skip collection and begin the blind chat-labeling pass.

Recommended configuration for labeling: GPT-5.6 Sol, Medium reasoning, main thread only.
