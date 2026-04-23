# AbletonMCP API Robustness Improvements

## Context
During the development of rhythm mapping workflows, several edge cases were encountered while making manual socket calls and manipulating clips in the Ableton Live Object Model (LOM):

1. **JSON Schema Rigidity**: The `AbletonMCP_Remote_Script` strictly expected parameters to be flattened at the top level of the JSON payload (e.g. `{"command": "foo", "track_index": 0}`). Sending standard JSON-RPC payloads like `{"command": "foo", "params": {"track_index": 0}}` caused `unknown command` exceptions.
2. **Clip Overwrite Failures**: The `create_clip` LOM method throws an unhandled `RuntimeError` if called on a clip slot that already contains a clip. This meant `create_clip` could not be used to reset/clear an existing clip.
3. **Missing Deletion Tooling**: There was no explicit way to clear or delete a clip from a slot using the MCP server, requiring manual intervention or workarounds.

## Solutions Implemented

### 1. Robust Payload Parsing
The `_process_command` routing method in `AbletonMCP_Remote_Script/__init__.py` was updated to merge nested `"params"` dictionaries into the main payload context. This allows the API to accept both flat schemas and nested JSON-RPC schemas interchangeably.

### 2. Idempotent Clip Creation
The `_create_clip` handler in the Remote Script was updated to verify if the target `clip_slot` already `has_clip`. If true, it preemptively calls `clip_slot.delete_clip()` before invoking `clip_slot.create_clip(length)`. This makes the command idempotent and safe to fire repeatedly.

### 3. Explicit `delete_clip` Command
- **Remote Script**: Added `_delete_clip` command handler to cleanly delete clips from slots.
- **MCP Server**: Added a corresponding `@mcp.tool() delete_clip(track_index, clip_index)` to expose this functionality to the LLM agent, allowing for automated clean-up workflows.
