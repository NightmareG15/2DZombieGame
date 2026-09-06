import pygame
import socket
import json
import threading
import time
import struct


class NetworkManager:
    def __init__(self):
        self.is_host = False
        self.is_client = False
        self.connected = False
        self.server_socket = None
        self.client_socket = None
        self.clients = {}
        self.host_addr = ("0.0.0.0", 5555)
        self.player_data = {}
        self.received_data = {}
        self.running = False
        self.lock = threading.Lock()
        self.send_thread = None
        self.recv_thread = None
        self.pending_shots = []
        self.pending_events = []

    def start_host(self, port=5555):
        self.is_host = True
        self.is_client = False
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(0.1)
        self.server_socket.bind(("0.0.0.0", port))
        self.server_socket.listen(4)
        self.recv_thread = threading.Thread(target=self._host_listen, daemon=True)
        self.recv_thread.start()
        self.send_thread = threading.Thread(target=self._host_broadcast_loop, daemon=True)
        self.send_thread.start()
        return True, f"Servidor iniciado na porta {port}"

    def _host_listen(self):
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                conn.settimeout(0.1)
                client_id = len(self.clients)
                with self.lock:
                    self.clients[client_id] = {
                        "socket": conn,
                        "addr": addr,
                        "data": {},
                        "name": f"User {client_id + 1}",
                    }
                print(f"[HOST] User connected: {addr} (ID: {client_id})")
                threading.Thread(
                    target=self._handle_client, args=(client_id,), daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[HOST] Failed to accept connection: {e}")

    def _handle_client(self, client_id):
        while self.running and client_id in self.clients:
            try:
                data = self.clients[client_id]["socket"].recv(4096)
                if data:
                    msg = json.loads(data.decode("utf-8"))
                    with self.lock:
                        self.clients[client_id]["data"] = msg
                        if "name" in msg:
                            self.clients[client_id]["name"] = msg["name"]
                        if "shot" in msg:
                            self.pending_shots.append((client_id, msg["shot"]))
                        if "event" in msg:
                            self.pending_events.append((client_id, msg["event"]))
                else:
                    break
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError):
                break
            except Exception as e:
                if self.running:
                    pass

        with self.lock:
            if client_id in self.clients:
                try:
                    self.clients[client_id]["socket"].close()
                except:
                    pass
                del self.clients[client_id]
        print(f"[HOST] User {client_id} disconnected")

    def _host_broadcast_loop(self):
        while self.running:
            state = self._get_game_state()
            state_bytes = json.dumps(state).encode("utf-8")
            with self.lock:
                disconnected = []
                for cid, client in self.clients.items():
                    try:
                        client["socket"].sendall(state_bytes)
                    except:
                        disconnected.append(cid)
                for cid in disconnected:
                    try:
                        self.clients[cid]["socket"].close()
                    except:
                        pass
                    del self.clients[cid]
            time.sleep(1 / 30)

    def _get_game_state(self):
        state = {"type": "state", "players": {}, "enemies": []}
        with self.lock:
            state["host_data"] = self.player_data
            for cid, client in self.clients.items():
                state["players"][cid] = client["data"]
        return state

    def connect_to_host(self, host_ip, port=5555, player_name="Player"):
        self.is_host = False
        self.is_client = True
        self.running = True
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)
            self.client_socket.connect((host_ip, port))
            self.client_socket.settimeout(0.1)
            init_msg = json.dumps({"type": "join", "name": player_name}).encode("utf-8")
            self.client_socket.sendall(init_msg)
            self.connected = True
            self.recv_thread = threading.Thread(target=self._client_recv_loop, daemon=True)
            self.recv_thread.start()
            self.send_thread = threading.Thread(target=self._client_send_loop, daemon=True)
            self.send_thread.start()
            return True, "Connected to host."
        except Exception as e:
            return False, f"Failed to connect: {e}"

    def _client_recv_loop(self):
        buffer = ""
        while self.running and self.connected:
            try:
                data = self.client_socket.recv(8192)
                if data:
                    buffer += data.decode("utf-8")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        msg = json.loads(line)
                        with self.lock:
                            self.received_data = msg
                else:
                    self.connected = False
                    break
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError):
                self.connected = False
                break
            except Exception:
                if self.running:
                    continue

    def _client_send_loop(self):
        while self.running and self.connected:
            try:
                data = json.dumps(self.player_data).encode("utf-8")
                self.client_socket.sendall(data)
            except:
                self.connected = False
                break
            time.sleep(1 / 30)

    def send_player_data(self, data):
        with self.lock:
            self.player_data = data

    def send_shot(self, shot_data):
        msg = json.dumps({"shot": shot_data}).encode("utf-8")
        try:
            if self.is_host:
                with self.lock:
                    for cid, client in self.clients.items():
                        try:
                            client["socket"].sendall(msg)
                        except:
                            pass
            elif self.client_socket:
                self.client_socket.sendall(msg)
        except:
            pass

    def send_event(self, event_data):
        msg = json.dumps({"event": event_data}).encode("utf-8")
        try:
            if self.is_host:
                with self.lock:
                    for cid, client in self.clients.items():
                        try:
                            client["socket"].sendall(msg)
                        except:
                            pass
            elif self.client_socket:
                self.client_socket.sendall(msg)
        except:
            pass

    def get_remote_players(self):
        with self.lock:
            if self.is_host:
                return {
                    cid: client["data"]
                    for cid, client in self.clients.items()
                    if client["data"]
                }
            else:
                return self.received_data.get("players", {})

    def get_pending_shots(self):
        with self.lock:
            shots = self.pending_shots[:]
            self.pending_shots.clear()
            return shots

    def get_pending_events(self):
        with self.lock:
            events = self.pending_events[:]
            self.pending_events.clear()
            return events

    def get_connected_count(self):
        with self.lock:
            return len(self.clients)

    def disconnect(self):
        self.running = False
        self.connected = False
        try:
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        with self.lock:
            for cid, client in self.clients.items():
                try:
                    client["socket"].close()
                except:
                    pass
            self.clients.clear()
        self.is_host = False
        self.is_client = False
