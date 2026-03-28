import socket
import threading
import random
import hashlib
import time

import game_logic as gl

HOST = "0.0.0.0"
PORT = 8080
SECRET = "network_secret"

GRID_WIDTH = 10
GRID_HEIGHT = 10
COIN_COUNT = 5

TICK_RATE = 20
SNAPSHOT_RATE = 10
MAX_PLAYERS = 20

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))

clients = {}
seq_map = {}

lock = threading.Lock()


def generate_token():
    return hashlib.md5(str(random.random()).encode()).hexdigest()[:16]


def random_position():
    return (
        random.randint(0, GRID_WIDTH - 1),
        random.randint(0, GRID_HEIGHT - 1)
    )


def send_with_delay(addr, msg):
    delay = random.uniform(0, 0.2)
    time.sleep(delay)
    server.sendto(msg.encode(), addr)


def broadcast(msg):
    for addr in clients.values():
        if random.random() < 0.1:
            continue
        threading.Thread(target=send_with_delay, args=(addr, msg), daemon=True).start()


def broadcast_state():
    broadcast(gl.get_world_state_message())


def broadcast_scores():
    broadcast(gl.get_scoreboard_message())


def handle_packet(data, addr, current_tick):
    try:
        msg = data.decode()

        # JOIN
        if msg == "JOIN":
            token = generate_token()
            name = f"Player{len(clients) + 1}"

            with lock:
                if len(clients) >= MAX_PLAYERS:
                    server.sendto("CLOSE".encode(), addr)
                    return
                clients[token] = addr
                seq_map[token] = 0
                if not gl.add_player(token, name):
                    server.sendto("CLOSE".encode(), addr)
                    return

            server.sendto(f"WELCOME|{token}|{name}".encode(), addr)
            return

        try:
            token, seq, move, recv_hash = msg.split("|")
            seq = int(seq)
        except:
            return

        payload = f"{token}|{seq}|{move}"
        valid_hash = hashlib.sha256((SECRET + payload).encode()).hexdigest()

        if recv_hash != valid_hash:
            return

        with lock:

            if token not in clients:
                return

            # sequence check
            if seq <= seq_map[token]:
                server.sendto(f"ACK|{seq}".encode(), addr)
                return
            seq_map[token] = seq

            status, new_pos, _collected = gl.move_player(token, move, current_tick)

            server.sendto(f"ACK|{seq}".encode(), addr)

            if status != "OK":
                server.sendto(status.encode(), addr)
                return

            player_name = gl.get_player_name(token)
            print(f"MOVE {player_name} seq={seq} cmd={move} pos={new_pos}")

            victims = gl.detect_collisions_at(new_pos, excluding_token=token)

            for victim_token in victims:
                killer = gl.get_player_name(token)
                victim = gl.get_player_name(victim_token)

                print(f"{killer} killed {victim}")

                gl.award_kill(token, points=20)

                server.sendto("YOU_ELIMINATED".encode(), clients[victim_token])
                server.sendto(f"YOU_ELIMINATED|{killer}".encode(), clients[victim_token])
                server.sendto(f"KILL|{victim}".encode(), clients[token])

                gl.remove_player(victim_token)
                del clients[victim_token]
                del seq_map[victim_token]

            # WIN CONDITION
            winner_name = gl.check_winner()
            if winner_name:
                broadcast(f"GAME_OVER|{winner_name}")

    except Exception as e:
        print("SERVER ERROR:", e)


gl.configure(GRID_WIDTH, GRID_HEIGHT, COIN_COUNT)
gl.spawn_coins()
print("Server running...")

tick_interval = 1.0 / TICK_RATE
snapshot_interval = 1.0 / SNAPSHOT_RATE

current_tick = 0
next_tick = time.time() + tick_interval
next_snapshot = time.time() + snapshot_interval

while True:
    now = time.time()
    wait_until = min(next_tick, next_snapshot)
    timeout = max(0.0, wait_until - now)

    server.settimeout(timeout)

    try:
        data, addr = server.recvfrom(1024)
        handle_packet(data, addr, current_tick)
    except socket.timeout:
        pass
    except ConnectionResetError:
        pass

    now = time.time()

    while now >= next_tick:
        current_tick += 1
        next_tick += tick_interval

    if now >= next_snapshot:
        broadcast_state()
        broadcast_scores()
        next_snapshot += snapshot_interval