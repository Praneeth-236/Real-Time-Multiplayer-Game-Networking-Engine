import socket
import hashlib
import secrets
import game_logic

HOST = "0.0.0.0"
PORT = 8080
SECRET = "network_secret"

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))

tokens = {}        # addr -> token
player_count = 0


def log(msg):
    print(f"[SERVER] {msg}")


def broadcast(msg):
    for addr in tokens:
        try:
            server.sendto(msg.encode(), addr)
        except:
            pass


log("Server running")


while True:

    data, addr = server.recvfrom(1024)
    msg = data.decode()


    # PLAYER JOIN
    if msg == "JOIN":

        player_count += 1
        name = f"Player{player_count}"

        token = secrets.token_hex(8)
        tokens[addr] = token

        game_logic.add_player(addr, name)

        server.sendto(f"WELCOME|{token}|{name}".encode(), addr)

        log(f"{name} joined")

        broadcast(game_logic.get_world_state())

        continue


    try:
        token, seq, command, received_hash = msg.split("|")
        seq = int(seq)
    except:
        continue


    if addr not in tokens:
        continue


    if token != tokens[addr]:
        continue


    payload = f"{token}|{seq}|{command}"
    expected_hash = hashlib.sha256((SECRET + payload).encode()).hexdigest()

    if expected_hash != received_hash:
        continue


    if seq <= game_logic.players[addr]["seq"]:
        continue


    game_logic.players[addr]["seq"] = seq


    # MOVE PLAYER
    game_logic.move_player(addr, command)

    p = game_logic.players[addr]
    log(f"{p['name']} moved {command} -> ({p['x']},{p['y']})")


    # COLLISION DETECTION
    loser = game_logic.check_collision(addr)

    if loser:

        loser_name = game_logic.players[loser]["name"]

        # notify eliminated player
        server.sendto("YOU_ELIMINATED".encode(), loser)

        # notify others
        broadcast(f"ELIMINATED|{loser_name}")

        game_logic.eliminate_player(loser)

        log(f"{loser_name} eliminated")


    # CHECK WINNER
    winner = game_logic.check_winner()

    if winner:

        broadcast(f"GAME_OVER|{winner} wins")

        log(f"Winner: {winner}")

        # CLOSE CONNECTION FOR EVERY CLIENT
        for addr in list(tokens.keys()):
            try:
                server.sendto("CLOSE".encode(), addr)
            except:
                pass

        server.close()
        break


    # SEND UPDATED WORLD STATE
    broadcast(game_logic.get_world_state())