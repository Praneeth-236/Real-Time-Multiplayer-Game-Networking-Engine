import os
import sys

if sys.platform.startswith("linux"):
    os.environ.setdefault("SDL_VIDEODRIVER", "x11")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import socket
import threading
import hashlib
import time
import math

SERVER_IP = "127.0.0.1"
PORT = 8080
SECRET = "network_secret"

GRID_WIDTH = 10
GRID_HEIGHT = 10
CELL_SIZE = 50

WIDTH = GRID_WIDTH * CELL_SIZE
HEIGHT = GRID_HEIGHT * CELL_SIZE

players = {}
display_positions = {}
scores = {}
coins = set()

last_world_print = None
last_score_print = None

local_pred = None
pending_moves = []
move_send_times = {}
move_retries = {}
RESEND_TIMEOUT = 0.3
MAX_RETRIES = 5
last_ack_seq = 0
send_times = {}
latency = 0
jitter = 0
last_rtt = None

seq = 0
alive = True
game_over = False
winner = ""
eliminated_by = ""

kill_message = ""
kill_timer = 0
kill_feed = []

latency_history = []
last_latency_push = 0

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(3)

print("Connecting...")
token = None
name = None

for _ in range(10):
    try:
        client.sendto("JOIN".encode(), (SERVER_IP, PORT))
        data, _ = client.recvfrom(1024)
        msg = data.decode()
        if msg == "CLOSE":
            print("Server refused connection")
            sys.exit(1)
        _, token, name = msg.split("|")
        break
    except (socket.timeout, ConnectionResetError):
        time.sleep(0.5)

if token is None:
    print("Unable to connect to server")
    sys.exit(1)

print("Connected as", name)


def apply_move(x, y, command):
    if command == "UP":
        y += 1
    elif command == "DOWN":
        y -= 1
    elif command == "LEFT":
        x -= 1
    elif command == "RIGHT":
        x += 1

    x = max(0, min(GRID_WIDTH - 1, x))
    y = max(0, min(GRID_HEIGHT - 1, y))
    return x, y


def receive():
    global alive, game_over, winner, kill_message, kill_timer
    global local_pred, last_ack_seq, latency, jitter, last_rtt
    global last_world_print, last_score_print
    global kill_feed, latency_history, last_latency_push

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

                        # initialize display pos if new
                        if n not in display_positions:
                            display_positions[n] = [x, y]

                # drop display positions for removed players
                for n in list(display_positions.keys()):
                    if n not in new_players:
                        del display_positions[n]

                players.clear()
                players.update(new_players)

                # reconcile local prediction
                if name in new_players:
                    auth_x, auth_y = new_players[name]
                    local_pred = [auth_x, auth_y]
                    for move_seq, move_cmd in pending_moves:
                        if move_seq > last_ack_seq:
                            local_pred[0], local_pred[1] = apply_move(local_pred[0], local_pred[1], move_cmd)

                coins.clear()
                for c in coin_data.split(";"):
                    if "," in c:
                        x, y = map(int, c.split(","))
                        coins.add((x, y))

                world_snapshot = tuple(sorted(new_players.items()))
                if world_snapshot != last_world_print:
                    print("\n--- WORLD ---")
                    for n, (px, py) in new_players.items():
                        if n == name:
                            print(f"YOU ({px},{py})")
                        else:
                            print(f"{n} -> ({px},{py})")
                    print(f"Latency: {latency:.1f} ms | Jitter: {jitter:.1f} ms")
                    last_world_print = world_snapshot

            elif msg.startswith("SCORE"):
                scores.clear()
                for s in msg.split("|")[1].split(";"):
                    if ":" in s:
                        n, sc = s.split(":")
                        scores[n] = sc

                score_snapshot = tuple(sorted(scores.items()))
                if score_snapshot != last_score_print:
                    print("\n--- SCOREBOARD ---")
                    for n, sc in scores.items():
                        print(f"{n}: {sc}")
                    last_score_print = score_snapshot

            elif msg == "YOU_ELIMINATED":
                alive = False
                game_over = True
                eliminated_by = ""
                print("\nYou have been eliminated")

            elif msg.startswith("YOU_ELIMINATED|"):
                alive = False
                game_over = True
                eliminated_by = msg.split("|")[1]
                print(f"\nYou were eliminated by {eliminated_by}")
                kill_feed.insert(0, f"You were eliminated by {eliminated_by}")

            elif msg.startswith("KILL"):
                victim = msg.split("|")[1]
                kill_message = f"You eliminated {victim}"
                kill_timer = 90
                print(f"You eliminated {victim}")
                kill_feed.insert(0, f"You eliminated {victim}")

            elif msg.startswith("GAME_OVER"):
                winner = msg.split("|")[1]
                game_over = True
                print("\nGAME_OVER|" + winner)

            elif msg.startswith("ACK"):
                try:
                    ack_seq = int(msg.split("|")[1])
                except:
                    continue

                last_ack_seq = max(last_ack_seq, ack_seq)

                pending_moves[:] = [(s, c) for (s, c) in pending_moves if s > ack_seq]
                move_send_times.pop(ack_seq, None)
                move_retries.pop(ack_seq, None)

                sent_time = send_times.pop(ack_seq, None)
                if sent_time is None:
                    continue

                rtt = (time.time() - sent_time) * 1000
                latency = rtt

                now = time.time()
                if now - last_latency_push > 0.1:
                    latency_history.append(latency)
                    latency_history[:] = latency_history[-60:]
                    last_latency_push = now

                if last_rtt is None:
                    last_rtt = rtt
                jitter += (abs(rtt - last_rtt) - jitter) / 16
                last_rtt = rtt

            elif msg == "CLOSE":
                print("Connection closed")
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return

        except:
            continue


threading.Thread(target=receive, daemon=True).start()


def send_move(command):
    global seq, local_pred
    if not alive:
        return

    seq += 1
    pending_moves.append((seq, command))

    if local_pred is None:
        local_pred = [0, 0]
    local_pred[0], local_pred[1] = apply_move(local_pred[0], local_pred[1], command)

    payload = f"{token}|{seq}|{command}"
    h = hashlib.sha256((SECRET + payload).encode()).hexdigest()
    packet = f"{payload}|{h}"
    client.sendto(packet.encode(), (SERVER_IP, PORT))
    now = time.time()
    send_times[seq] = now
    move_send_times[seq] = now
    move_retries[seq] = 0


def resend_pending_moves():
    now = time.time()
    for move_seq, move_cmd in list(pending_moves):
        last_sent = move_send_times.get(move_seq, 0)
        retries = move_retries.get(move_seq, 0)
        if retries >= MAX_RETRIES:
            continue
        if now - last_sent >= RESEND_TIMEOUT:
            payload = f"{token}|{move_seq}|{move_cmd}"
            h = hashlib.sha256((SECRET + payload).encode()).hexdigest()
            packet = f"{payload}|{h}"
            client.sendto(packet.encode(), (SERVER_IP, PORT))
            move_send_times[move_seq] = now
            move_retries[move_seq] = retries + 1


pygame.init()
screen = pygame.display.set_mode((WIDTH + 200, HEIGHT))
pygame.display.set_caption("Grid Game")

clock = pygame.time.Clock()
font = pygame.font.SysFont("Consolas", 22)
title_font = pygame.font.SysFont("Georgia", 28, bold=True)
hud_font = pygame.font.SysFont("Consolas", 18)
small_font = pygame.font.SysFont("Consolas", 14)

BG_TOP = (18, 22, 30)
BG_BOTTOM = (8, 10, 16)
GRID_COLOR = (50, 60, 70)
PANEL_BG = (20, 24, 32)
PANEL_BORDER = (80, 90, 110)
TEXT_DIM = (190, 190, 190)
ACCENT = (110, 180, 255)
WARN = (255, 120, 120)


def grid_to_screen(x, y):
    return x * CELL_SIZE, HEIGHT - (y + 1) * CELL_SIZE


def draw_grid():
    for x in range(GRID_WIDTH):
        for y in range(GRID_HEIGHT):
            rect = pygame.Rect(*grid_to_screen(x, y), CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, GRID_COLOR, rect, 1)


def draw_background():
    for i in range(HEIGHT):
        t = i / max(1, HEIGHT - 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        pygame.draw.line(screen, (r, g, b), (0, i), (WIDTH + 200, i))


def smooth_movement():
    for n in players:
        if n == name and local_pred is not None:
            tx, ty = local_pred
        else:
            tx, ty = players[n]
        dx, dy = display_positions[n]

        display_positions[n][0] += (tx - dx) * 0.2
        display_positions[n][1] += (ty - dy) * 0.2


def draw_players():
    pulse = (pygame.time.get_ticks() % 1000) / 1000.0
    for n, (dx, dy) in display_positions.items():

        px, py = grid_to_screen(dx, dy)
        rect = pygame.Rect(px, py, CELL_SIZE, CELL_SIZE)

        if n == name:
            color = (90, 230, 140)
            pygame.draw.rect(screen, (235, 235, 235), rect, 3)
            glow = int(6 + 3 * (0.5 + 0.5 * math.sin(pulse * 6.283)))
            pygame.draw.rect(screen, (120, 255, 180), rect.inflate(glow, glow), 2, border_radius=10)
        else:
            color = (80, 140, 255)

        pygame.draw.rect(screen, color, rect, border_radius=6)

        label = font.render(n, True, (255, 255, 255))
        screen.blit(label, (rect.x + 5, rect.y + 5))


def draw_coins():
    pulse = (pygame.time.get_ticks() % 1200) / 1200.0
    radius = int(CELL_SIZE // 4 + (CELL_SIZE // 10) * (0.5 + 0.5 * math.sin(pulse * 6.283)))
    for (x, y) in coins:
        px, py = grid_to_screen(x, y)
        center = (px + CELL_SIZE // 2, py + CELL_SIZE // 2)
        pygame.draw.circle(screen, (255, 205, 80), center, radius)
        pygame.draw.circle(screen, (255, 235, 160), center, max(2, radius - 6))


def draw_scores():
    panel_x = WIDTH + 10
    y_offset = 20

    panel_rect = pygame.Rect(WIDTH + 6, 6, 188, HEIGHT - 12)
    pygame.draw.rect(screen, PANEL_BG, panel_rect, border_radius=10)
    pygame.draw.rect(screen, PANEL_BORDER, panel_rect, 2, border_radius=10)

    title = title_font.render("SCORE", True, (240, 240, 240))
    screen.blit(title, (panel_x, 10))

    for n, sc in scores.items():
        text = font.render(f"{n}: {sc}", True, (255, 230, 120))
        screen.blit(text, (panel_x, y_offset))
        y_offset += 25

    draw_minimap(panel_x, y_offset + 10)
    draw_kill_feed(panel_x, HEIGHT - 170)
    draw_latency_graph(panel_x, HEIGHT - 95)

    net_text = hud_font.render(f"RTT {latency:.0f} ms", True, TEXT_DIM)
    screen.blit(net_text, (panel_x, HEIGHT - 60))

    jit_text = hud_font.render(f"Jitter {jitter:.0f} ms", True, TEXT_DIM)
    screen.blit(jit_text, (panel_x, HEIGHT - 35))


def draw_minimap(x, y):
    size = 150
    rect = pygame.Rect(x, y, size, size)
    pygame.draw.rect(screen, (18, 22, 30), rect, border_radius=8)
    pygame.draw.rect(screen, PANEL_BORDER, rect, 1, border_radius=8)

    for px in range(GRID_WIDTH):
        for py in range(GRID_HEIGHT):
            sx = x + int(px * (size / GRID_WIDTH))
            sy = y + int(py * (size / GRID_HEIGHT))
            screen.fill((25, 30, 38), (sx, sy, int(size / GRID_WIDTH), int(size / GRID_HEIGHT)))

    for (cx, cy) in coins:
        sx = x + int((cx + 0.5) * (size / GRID_WIDTH))
        sy = y + int((GRID_HEIGHT - cy - 0.5) * (size / GRID_HEIGHT))
        pygame.draw.circle(screen, (255, 215, 120), (sx, sy), 3)

    for n, (px, py) in players.items():
        sx = x + int((px + 0.5) * (size / GRID_WIDTH))
        sy = y + int((GRID_HEIGHT - py - 0.5) * (size / GRID_HEIGHT))
        color = (90, 230, 140) if n == name else (90, 140, 255)
        pygame.draw.circle(screen, color, (sx, sy), 4)

    label = small_font.render("Mini-map", True, TEXT_DIM)
    screen.blit(label, (x + 6, y + size + 4))


def draw_kill_feed(x, y):
    title = small_font.render("Kill feed", True, TEXT_DIM)
    screen.blit(title, (x, y))
    offset = 16
    for line in kill_feed[:4]:
        text = small_font.render(line, True, WARN)
        screen.blit(text, (x, y + offset))
        offset += 16


def draw_latency_graph(x, y):
    width = 170
    height = 40
    rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(screen, (18, 22, 30), rect, border_radius=6)
    pygame.draw.rect(screen, PANEL_BORDER, rect, 1, border_radius=6)

    if len(latency_history) < 2:
        return

    max_val = max(latency_history)
    max_val = max(50, min(500, max_val))

    points = []
    for i, v in enumerate(latency_history[-60:]):
        px = x + int(i * (width / 60))
        py = y + height - int((v / max_val) * (height - 4)) - 2
        points.append((px, py))

    if len(points) > 1:
        pygame.draw.lines(screen, ACCENT, False, points, 2)


def draw_kill_message():
    global kill_timer
    if kill_timer > 0:
        text = font.render(kill_message, True, (255, 120, 120))
        rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.blit(text, rect)
        kill_timer -= 1


def draw_game_over():
    if winner == name:
        text = title_font.render("YOU WIN!", True, (80, 255, 140))
    elif winner:
        text = title_font.render(f"{winner} WINS!", True, (255, 255, 255))
    else:
        text = title_font.render("YOU WERE ELIMINATED", True, (255, 90, 90))

    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
    screen.blit(text, rect)

    if eliminated_by:
        sub = font.render(f"by {eliminated_by}", True, (230, 230, 230))
        sub_rect = sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10))
        screen.blit(sub, sub_rect)


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

    draw_background()

    smooth_movement()
    draw_grid()
    draw_coins()
    draw_players()
    draw_scores()
    draw_kill_message()

    if game_over:
        draw_game_over()

    resend_pending_moves()

    pygame.display.update()
    clock.tick(60)

pygame.quit()