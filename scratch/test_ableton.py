import socket
import json
import sys

def test_command(command_type, params=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('localhost', 9877))
        command = {
            'type': command_type,
            'params': params or {}
        }
        s.sendall(json.dumps(command).encode('utf-8'))
        response = s.recv(8192).decode('utf-8')
        print(f"Command: {command_type}")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    test_command("get_selected_clip", {"include_notes": True})
    test_command("get_session_info")
