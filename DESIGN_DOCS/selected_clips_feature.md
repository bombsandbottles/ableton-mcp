# Add Selected Clip Interaction Feature

## Section Zero: Problem Description
We want to enable the AI assistant to automatically detect and interact with which clip the user is currently working on in Ableton Live. Currently, the assistant can only interact with clips if it knows their exact track index and clip index, which forces the user to manually look up and provide these details. By giving the MCP server the ability to read and modify the active selection directly from Ableton, the user can simply select a clip with their mouse and ask questions or issue commands like "transpose this clip up an octave" or "what notes are in here?", creating a much more fluid, context-aware workflow.

## Section One: Implementation Overview

To make this feature work, we need to bridge the gap between what you see in Ableton Live and what the AI assistant can understand. This involves updating two main pieces of our existing system so they can handle this new request, and adding direct manipulation tools to avoid complex index lookups.

1. **The Ableton Remote Script (The Inside Agent):**
Ableton Live uses built-in scripts to communicate with external software. We will update our existing script so that it knows how to find the "Target Clip"—which could be the clip currently in the "Clip Detail View", the highlighted Session View slot, or the highlighted Arrangement View clip. When asked, this script will grab the details of this clip (name, length, track location, clip type, and optionally notes) and package that data. We will also add functions to directly modify this Target Clip.

2. **The MCP Server (The Translator):**
The MCP server acts as the middleman between the AI assistant and Ableton Live. We will add new capabilities (tools) to this server:
- `get_selected_clip(include_notes: bool)`: Reads the details of the active clip.
- `update_selected_clip_notes(notes: list, expected_clip_name: str)`: Directly modifies the notes of the currently active clip, taking the expected clip name as a safety check.

**How they fit together:**
When you click on a clip in Ableton and ask the AI a question (like "transpose this up"), the AI will trigger the new `get_selected_clip` tool on the MCP Server. The Remote Script finds the active clip and sends the data back out to the MCP Server. If the AI decides to make a change, it uses the `update_selected_clip_notes` tool, which operates *directly* on the active clip in Ableton, without ever needing to map back to track or clip indices.

## Section Two: Alternatives Considered

During our research, we explored a few different ways to tackle this problem before settling on our current approach:

1. **Selecting Multiple Clips at Once**
Ideally, we wanted the ability to highlight several clips in the timeline at the same time. However, we discovered a hard limitation in Ableton's internal code: it does not provide a robust way for outside scripts to see if multiple clips are highlighted in the arrangement view. We had to rule this out and focus on single-clip interactions.

2. **Index-Based Modification (Option A)**
We initially considered having `get_selected_clip` figure out the exact `track_index` and `clip_index` of the active clip, and returning those to the AI so it could use existing tools like `add_notes_to_clip`. We rejected this because:
- Resolving indices for Arrangement vs Session clips is complex and error-prone.
- It introduces a risk where the indices might shift if the user adds/removes tracks between the AI's "read" and "write" actions.
Instead, we chose "Option B", which creates new tools that operate directly on the current Live object reference inside the script, completely bypassing the need for index lookups.

## Section Three: Detailed Implementation Plan

To implement this feature, we need to modify two existing files in our codebase. No new files need to be created. Here is the step-by-step breakdown:

### 1. `AbletonMCP_Remote_Script/__init__.py`
**Rationale:** This file contains the Python script that runs directly inside Ableton Live. We need to modify it to query and mutate the active clip.
**Changes required:**
- **Add a `_get_target_clip()` helper:** This method will determine the active clip by checking multiple sources: first `self._song.view.detail_clip`, then falling back to `self._song.view.highlighted_clip_slot.clip` (Session view), ensuring both Session and Arrangement clips are accessible. If no clip is found, it returns `(None, None)`. For robustness, it should also return the track (`self._song.view.selected_track`) to make checking for frozen tracks easier later.
- **Add `_get_selected_clip(include_notes=False)`:** Uses the helper to get the clip. If `None`, returns a friendly null state message (e.g., `{"status": "error", "message": "No clip is currently selected"}`). If found, it returns metadata in a strict schema that matches the rest of the codebase.
  *Implementation detail for view detection:* Use `getattr(clip, 'is_arrangement_clip', False)` to distinguish Arrangement from Session clips.
  *JSON Schema Expectation:*
  ```json
  {
    "name": "Clip Name",
    "length": 4.0,
    "is_audio_clip": clip.is_audio_clip,
    "is_midi_clip": clip.is_midi_clip,
    "view": "arrangement", 
    "notes": [ // Only included if include_notes=True
      {"pitch": 60, "start_time": 0.0, "duration": 0.25, "velocity": 100, "mute": false}
    ]
  }
  ```
- **Add `_update_selected_clip_notes(expected_clip_name, new_notes)`:** Uses the helper to get the target clip and track.
  *Safeguards & Edge Cases:*
  1. **Audio Clips:** Checks `clip.is_audio_clip` and returns an error if true, since we can only modify MIDI.
  2. **Frozen Tracks:** Checks `track.is_frozen` (using the track returned from `_get_target_clip()`) and returns an error if true.
  3. **Race Conditions:** Checks if the target clip's name matches `expected_clip_name`. *Note on Nameless Clips:* Since Ableton clips are often nameless, the safety check should explicitly handle empty strings or use `expected_clip_length` as an additional fallback heuristic to ensure we don't accidentally modify the wrong clip if the user changes selection rapidly.
  *Note Format:* It clears the existing notes and inserts `new_notes` using the standard format found in `_add_notes_to_clip` (`pitch`, `start_time`, `duration`, `velocity`, `mute`).
- **Update `_process_command()`:** Add routing for the `"get_selected_clip"` and `"update_selected_clip_notes"` commands. 
  *Crucial Architecture Detail:* Because `_update_selected_clip_notes` mutates Live's state, it *must* be added to the list of commands routed through the `main_thread_task` and the `response_queue` mechanism. `get_selected_clip` can be executed immediately.

### 2. `MCP_Server/server.py`
**Rationale:** This file defines the actual MCP Server and the tools exposed to the AI assistant. We must update it to define the new tools and bridge the communication.
**Changes required:**
- **Define `get_selected_clip` tool:** Create a new function `get_selected_clip(ctx: Context, include_notes: bool = False) -> str` decorated with `@mcp.tool()`. This sends the request to Ableton using `ableton.send_command()` and returns the JSON string.
- **Define `update_selected_clip_notes` tool:** Create a new function `update_selected_clip_notes(ctx: Context, expected_clip_name: str, notes: list) -> str` decorated with `@mcp.tool()`. This enables the direct-modification workflow and includes the safety check. 
  *Strong Typing:* Ensure the `notes` parameter is strictly typed as `List[Dict[str, Union[int, float, bool]]]` to match the other note manipulation tools in the server.
