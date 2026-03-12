import socket
import hashlib
import threading
import os

SERVER_IP = "127.0.0.1"
PORT = 8080
SECRET = "network_secret"

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# join server
client.sendto("JOIN".encode(), (SERVER_IP, PORT))

data, _ = client.recvfrom(1024)
msg = data.decode()

_, token, name = msg.split("|")

print("Connected as", name)

seq = 0
alive = True


def receive():
    global alive

    while True:

        try:
            data, _ = client.recvfrom(1024)
        except:
            break

        msg = data.decode()

        if msg.startswith("STATE"):

            state = msg.split("|")[1]
            players = state.split(";")

            print("\nWorld State")

            for p in players:
                n, pos = p.split(":")
                x, y = pos.split(",")
                print(f"{n} -> ({x},{y})")

        elif msg.startswith("ELIMINATED"):

            print("\n", msg)

        elif msg == "YOU_ELIMINATED":

            print("\nYou have been eliminated!")
            alive = False

        elif msg.startswith("GAME_OVER"):

            print("\n", msg)

        elif msg == "CLOSE":

            print("\nConnection closed by server")

            client.close()

            os._exit(0)


# start receive thread
threading.Thread(target=receive, daemon=True).start()


while True:

    if not alive:
        continue

    cmd = input("\nMove (UP/DOWN/LEFT/RIGHT): ").upper()

    seq += 1

    payload = f"{token}|{seq}|{cmd}"

    h = hashlib.sha256((SECRET + payload).encode()).hexdigest()

    packet = f"{payload}|{h}"

    client.sendto(packet.encode(), (SERVER_IP, PORT))