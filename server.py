import socket
import threading
import random
import hashlib

HOST = "0.0.0.0"
PORT = 8080
SECRET = "network_secret"

GRID_WIDTH = 10
GRID_HEIGHT = 10
COIN_COUNT = 5

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))

clients = {}
players = {}
names = {}
scores = {}
coins = set()

lock = threading.Lock()

def generate_token():
    return hashlib.md5(str(random.random()).encode()).hexdigest()[:16]

def random_position():
    return (
        random.randint(0, GRID_WIDTH - 1),
        random.randint(0, GRID_HEIGHT - 1)
    )

def spawn_player():
    while True:
        pos = random_position()
        if pos not in players.values():
            return pos

def spawn_coins():
    coins.clear()
    while len(coins) < COIN_COUNT:
        coins.add(random_position())

def broadcast(msg):
    for addr in clients.values():
        server.sendto(msg.encode(), addr)

def broadcast_state():
    state = ";".join([
        f"{names[t]}:{x},{y}" for t, (x, y) in players.items()
    ])

    coin_data = ";".join([
        f"{x},{y}" for (x, y) in coins
    ])

    broadcast(f"STATE|{state}|COINS|{coin_data}")

def broadcast_scores():
    score_msg = ";".join([
        f"{names[t]}:{scores[t]}" for t in scores
    ])
    broadcast(f"SCORE|{score_msg}")

def move_player(pos, move):
    x, y = pos

    if move == "UP":
        y += 1
    elif move == "DOWN":
        y -= 1
    elif move == "LEFT":
        x -= 1
    elif move == "RIGHT":
        x += 1

    x = max(0, min(GRID_WIDTH - 1, x))
    y = max(0, min(GRID_HEIGHT - 1, y))

    return (x, y)

def handle_packet(data, addr):
    try:
        msg = data.decode()

        if msg == "JOIN":
            token = generate_token()
            name = f"Player{len(players) + 1}"

            with lock:
                clients[token] = addr
                players[token] = spawn_player()
                names[token] = name
                scores[token] = 0

            server.sendto(f"WELCOME|{token}|{name}".encode(), addr)
            return

        try:
            token, seq, move, recv_hash = msg.split("|")
        except:
            return

        payload = f"{token}|{seq}|{move}"
        valid_hash = hashlib.sha256((SECRET + payload).encode()).hexdigest()

        if recv_hash != valid_hash:
            return

        with lock:
            if token not in players:
                return

            new_pos = move_player(players[token], move)
            players[token] = new_pos

            # COINS
            if new_pos in coins:
                coins.remove(new_pos)
                scores[token] += 10

                while True:
                    c = random_position()
                    if c not in players.values() and c not in coins:
                        coins.add(c)
                        break

            # COLLISION
            hit_token = None

            for other_token, other_pos in players.items():
                if other_token == token:
                    continue
                if new_pos == other_pos:
                    hit_token = other_token
                    break

            if hit_token:
                killer = names[token]
                victim = names[hit_token]

                print(f"{killer} killed {victim}")

                scores[token] += 20

                # notify victim
                server.sendto("YOU_ELIMINATED".encode(), clients[hit_token])

                # notify killer
                server.sendto(f"KILL|{victim}".encode(), clients[token])

                # remove victim
                del players[hit_token]
                del clients[hit_token]
                del names[hit_token]
                del scores[hit_token]

            # WIN CONDITION
            if len(players) == 1:
                winner_token = list(players.keys())[0]
                winner_name = names[winner_token]
                broadcast(f"GAME_OVER|{winner_name}")

            broadcast_state()
            broadcast_scores()

    except Exception as e:
        print("SERVER ERROR:", e)

spawn_coins()
print("Server running...")

while True:
    data, addr = server.recvfrom(1024)
    threading.Thread(target=handle_packet, args=(data, addr)).start()
