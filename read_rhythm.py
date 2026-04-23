import socket, json

def send_req(cmd, params):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 9877))
    s.send((json.dumps({"command": cmd, "params": params}) + "\n").encode())
    resp = ""
    while True:
        data = s.recv(4096).decode()
        if not data: break
        resp += data
    return json.loads(resp)

res = send_req("get_clip_notes", {"track_index": 1, "clip_index": 0})
notes = res.get("result", {}).get("notes", [])
print(json.dumps([{"start": n["start_time"], "dur": n["duration"]} for n in notes]))
