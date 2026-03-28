import os
os.environ["SDL_VIDEODRIVER"] = "x11"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import socket
import threading
import hashlib

SERVER_IP = "127.0.0.1"
PORT = 8080
SECRET = "network_secret"

GRID_WIDTH = 10
GRID_HEIGHT = 10
CELL_SIZE = 50

WIDTH = GRID_WIDTH * CELL_SIZE
HEIGHT = GRID_HEIGHT * CELL_SIZE

players = {}
scores = {}
coins = set()

seq = 0
alive = True
game_over = False
winner = ""

kill_message = ""
kill_timer = 0

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(3)

print("Connecting...")
client.sendto("JOIN".encode(), (SERVER_IP, PORT))

data, _ = client.recvfrom(1024)
_, token, name = data.decode().split("|")
print("Connected as", name)

def receive():
    global alive, game_over, winner, kill_message, kill_timer

    while True:
        try:
            data, _ = client.recvfrom(1024)
            msg = data.decode()
        except:
            continue

        try:
            if msg.startswith("STATE"):
                parts = msg.split("|")
                player_data = parts[1] if len(parts) > 1 else ""
                coin_data = parts[3] if len(parts) > 3 else ""

                new_players = {}
                for p in player_data.split(";"):
                    if ":" in p:
                        n, pos = p.split(":")
                        x, y = map(int, pos.split(","))
                        new_players[n] = (x, y)

                players.clear()
                players.update(new_players)

                coins.clear()
                for c in coin_data.split(";"):
                    if "," in c:
                        x, y = map(int, c.split(","))
                        coins.add((x, y))

            elif msg.startswith("SCORE"):
                scores.clear()
                for s in msg.split("|")[1].split(";"):
                    if ":" in s:
                        n, sc = s.split(":")
                        scores[n] = sc

            elif msg == "YOU_ELIMINATED":
                alive = False
                game_over = True

            elif msg.startswith("KILL"):
                victim = msg.split("|")[1]
                kill_message = f"You eliminated {victim}!"
                kill_timer = 90

            elif msg.startswith("GAME_OVER"):
                winner = msg.split("|")[1]
                game_over = True

        except:
            continue

threading.Thread(target=receive, daemon=True).start()

def send_move(command):
    global seq
    if not alive:
        return

    seq += 1
    payload = f"{token}|{seq}|{command}"
    h = hashlib.sha256((SECRET + payload).encode()).hexdigest()
    packet = f"{payload}|{h}"
    client.sendto(packet.encode(), (SERVER_IP, PORT))

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Grid Game")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)

def draw_grid():
    for x in range(GRID_WIDTH):
        for y in range(GRID_HEIGHT):
            rect = pygame.Rect(x * CELL_SIZE, HEIGHT - (y + 1) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, (50, 50, 50), rect, 1)

def draw_players():
    for n, (x, y) in players.items():
        rect = pygame.Rect(x * CELL_SIZE, HEIGHT - (y + 1) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        color = (50, 200, 50) if n == name else (50, 100, 200)
        pygame.draw.rect(screen, color, rect)

        label = font.render(n, True, (255, 255, 255))
        screen.blit(label, (rect.x + 5, rect.y + 5))

def draw_scores():
    y_offset = 5
    for n, sc in scores.items():
        text = font.render(f"{n}: {sc}", True, (255, 255, 0))
        screen.blit(text, (5, y_offset))
        y_offset += 20

def draw_coins():
    for (x, y) in coins:
        rect = pygame.Rect(x * CELL_SIZE, HEIGHT - (y + 1) * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, (255, 215, 0), rect)

def draw_kill_message():
    global kill_timer
    if kill_timer > 0:
        text = font.render(kill_message, True, (255, 100, 100))
        rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40))
        screen.blit(text, rect)
        kill_timer -= 1

def draw_game_over():
    if winner == name:
        text = font.render("YOU WIN!", True, (0, 255, 0))
    elif winner:
        text = font.render(f"{winner} WINS!", True, (255, 255, 255))
    else:
        text = font.render("YOU WERE ELIMINATED", True, (255, 50, 50))

    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    screen.blit(text, rect)

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_w, pygame.K_UP):
                send_move("UP")
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                send_move("DOWN")
            elif event.key in (pygame.K_a, pygame.K_LEFT):
                send_move("LEFT")
            elif event.key in (pygame.K_d, pygame.K_RIGHT):
                send_move("RIGHT")

    screen.fill((30, 30, 30))

    draw_grid()
    draw_coins()
    draw_players()
    draw_scores()
    draw_kill_message()

    if game_over:
        draw_game_over()

    pygame.display.update()
    clock.tick(30)

pygame.quit()
