import socket
import hashlib
import threading
import os

SERVER_IP = "127.0.0.1"
PORT = 8080
SECRET = "network_secret"

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

client.sendto("JOIN".encode(), (SERVER_IP, PORT))

data, _ = client.recvfrom(1024)
msg = data.decode()

_, token, name = msg.split("|")

print("Connected as", name)

seq = 0
alive = True

x, y = 0, 0


def receive():
    global alive, x, y

    while True:
        try:
            data, _ = client.recvfrom(1024)
        except:
            break

        msg = data.decode()

        if msg.startswith("STATE"):

            print("\nWorld State")

            state = msg.split("|")[1].split(";")

            for p in state:
                n, pos = p.split(":")
                sx, sy = map(int, pos.split(","))

                print(f"{n} -> ({sx},{sy})")

                if n == name:
                    if sx != x or sy != y:
                        x, y = sx, sy

        elif msg.startswith("SCORE"):

            print("\nScoreboard")

            scores = msg.split("|")[1].split(";")

            for s in scores:
                n, sc = s.split(":")
                print(f"{n}: {sc}")

        elif msg == "YOU_ELIMINATED":
            print("You have been eliminated")
            alive = False

        elif msg.startswith("ELIMINATED"):
            print(msg)

        elif msg == "BLOCKED":
            print("Move blocked")

        elif msg == "COOLDOWN":
            print("Too fast")

        elif msg.startswith("GAME_OVER"):
            print(msg)

        elif msg == "CLOSE":
            print("Connection closed")
            client.close()
            os._exit(0)


threading.Thread(target=receive, daemon=True).start()


while True:

    if not alive:
        continue

    cmd = input("Move: ").upper()

    if cmd == "UP":
        y += 1
    elif cmd == "DOWN":
        y -= 1
    elif cmd == "LEFT":
        x -= 1
    elif cmd == "RIGHT":
        x += 1

    seq += 1

    payload = f"{token}|{seq}|{cmd}"
    h = hashlib.sha256((SECRET + payload).encode()).hexdigest()

    packet = f"{payload}|{h}"

    client.sendto(packet.encode(), (SERVER_IP, PORT))