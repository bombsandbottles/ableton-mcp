# Implementation Plan: Arrangement Clips Integration

This document outlines the changes made to add support for creating and analyzing MIDI clips directly in the Arrangement View via the Ableton MCP Server.

## 1. Goal Description
The objective was to expand the Ableton MCP integration beyond the Session View. Specifically, allowing the AI to:
1. Programmatically create MIDI clips at specific times on the Arrangement timeline.
2. Read and analyze the notes inside existing Arrangement View MIDI clips.
3. Modify or replace notes inside existing Arrangement View MIDI clips (follow-up actions).

Because Ableton's LOM does not directly support creating arrangement clips from scratch, we used a "Staging Clip" workaround combined with the `duplicate_clip_to_arrangement` backdoor method.

## 2. Implemented Changes

### `AbletonMCP_Remote_Script/__init__.py`
Added the backend Python logic inside Ableton to handle arrangement clips, utilizing the Live 11+ Extended API (`get_notes_extended`, `add_new_notes`).

*   **Updated `_add_notes_to_clip` to use Extended API**:
    *   Changed from `clip.set_notes` to `clip.add_new_notes` using `Live.Clip.MidiNoteSpecification` to preserve MPE data.

*   **Added `_create_arrangement_clip` method**:
    *   Finds the last empty `ClipSlot` in the Session View for the given `track_index`.
    *   Creates a temporary clip using `clip_slot.create_clip(length)`.
    *   Duplicates the empty temporary clip to the arrangement timeline using `track.duplicate_clip_to_arrangement(clip_slot.clip, start_time)`. 
    *   Cleans up by deleting the temporary session clip (`clip_slot.delete_clip()`).

*   **Added `_get_arrangement_clips` method**:
    *   Reads `song.tracks[track_index].arrangement_clips`.
    *   Returns a list of clip metadata (index, name, start_time, end_time, length).

*   **Added `_get_arrangement_clip_notes` method**:
    *   Accesses the specific clip via `song.tracks[track_index].arrangement_clips[clip_index]`.
    *   Extracts notes using `clip.get_notes_extended(0, 128, 0, clip.length)` (Live 11+ API).
    *   Formats the notes into a JSON-friendly array.

*   **Added `_set_arrangement_clip_notes` method**:
    *   Accesses the specific clip.
    *   Clears existing notes using `clip.remove_notes_extended(0, 128, 0, clip.length)`.
    *   Adds new notes using `clip.add_new_notes(...)`.

*   **Updated `_process_command`**:
    *   Routed the new commands to their respective methods on the main thread via `response_queue`.

### `MCP_Server/server.py`
Exposed the new backend methods as tools to the Claude LLM.

*   **`@mcp.tool() get_arrangement_clips`**:
    *   Parameters: `track_index: int`

*   **`@mcp.tool() get_arrangement_clip_notes`**:
    *   Parameters: `track_index: int`, `clip_index: int`

*   **`@mcp.tool() set_arrangement_clip_notes`**:
    *   Parameters: `track_index: int`, `clip_index: int`, `notes: List[Dict]`

*   **`@mcp.tool() create_arrangement_clip`**:
    *   Parameters: `track_index: int`, `start_time: float`, `length: float`, `name: str`, `notes: List[Dict]`
    *   *Implementation Note*: See Section 3 regarding the race condition fix implemented here.

## 3. Race Condition Discovery & Fix
During implementation, a critical race condition in the Ableton Live Object Model was discovered. 

**The Bug:**
If the script attempts to add notes (`add_new_notes`) to a clip *immediately* after it is created and projected to the arrangement timeline (`duplicate_clip_to_arrangement`) within the same execution cycle, the Ableton LOM thread crashes and hangs indefinitely, failing to return a response to the TCP socket.

**The Fix:**
To bypass this limitation without modifying the core threading model of the remote script, the fix was implemented at the MCP server level (`server.py`). The `create_arrangement_clip` tool now splits the process into two separate API calls:
1.  **Creation**: Send the `create_arrangement_clip` command to Ableton with an *empty* list of notes. This successfully projects a blank clip onto the timeline.
2.  **Yield**: The MCP server thread sleeps for `0.1` seconds, allowing the Ableton main thread to finish its current event loop cycle and fully register the new arrangement clip.
3.  **Population**: The server sends a `get_arrangement_clips` command to find the `clip_index` of the newly created clip by matching its `start_time`, and then sequentially fires a `set_arrangement_clip_notes` command to safely populate it with the requested MIDI data.

## 4. Decisions Reached
* **API Versioning Risks**: We proceeded with the undocumented `duplicate_clip_to_arrangement` method. Testing proved it is highly stable as long as the race condition mentioned above is avoided.
* **Legacy vs Extended**: Successfully transitioned to the Live 11+ Extended API (`get_notes_extended`, `add_new_notes`). We chose not to support older versions of Live.
* **Staging Slot Collisions**: We effectively minimized user disruption by utilizing the last empty clip slot in a track as the invisible staging ground.
