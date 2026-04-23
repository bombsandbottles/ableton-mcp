import socket, json

def send_req(cmd, params):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 9877))
    s.send((json.dumps({"command": cmd, "params": params}) + "\n").encode())
    
    resp = ""
    while True:
        data = s.recv(1).decode()
        if not data:
            break
        resp += data
        if data == '\n':
            break
    s.close()
    try:
        return json.loads(resp)
    except:
        return {}

# 1. Recreate the clip to clear existing notes
print("Creating clip...")
send_req("create_clip", {"track_index": 0, "clip_index": 0, "length": 32.0})

# 2. Build the notes array
bars = [
    [33, 49, 52, 54, 56, 59],
    [35, 51, 54, 56, 57, 61],
    [32, 51, 54, 58, 59, 61],
    [28, 49, 54, 56, 59, 63],
    [30, 49, 52, 56, 57, 59],
    [33, 51, 54, 56, 59, 61],
    [32, 51, 52, 54, 59, 61],
    [31, 50, 52, 57, 58, 60]
]

rhythm_offsets = [0.0, 1.0, 2.0, 2.75, 3.5]
notes = []

for b, chord in enumerate(bars):
    base_time = b * 4.0
    for offset in rhythm_offsets:
        for pitch in chord:
            notes.append({
                "pitch": pitch,
                "start_time": base_time + offset,
                "duration": 0.25,
                "velocity": 90,
                "mute": False
            })

# 3. Add notes
print(f"Adding {len(notes)} notes...")
res = send_req("add_notes_to_clip", {"track_index": 0, "clip_index": 0, "notes": notes})
print("Result:", res)

