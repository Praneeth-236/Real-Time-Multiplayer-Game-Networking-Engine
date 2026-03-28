import random

players = {}
coins = set()

GRID_WIDTH = 10
GRID_HEIGHT = 10
COIN_COUNT = 5

obstacles = set()


def configure(grid_width, grid_height, coin_count, obstacle_list=None):
    global GRID_WIDTH, GRID_HEIGHT, COIN_COUNT, obstacles
    GRID_WIDTH = grid_width
    GRID_HEIGHT = grid_height
    COIN_COUNT = coin_count
    obstacles = set(obstacle_list or [])


def reset_game():
    players.clear()
    coins.clear()


def random_position():
    return (
        random.randint(0, GRID_WIDTH - 1),
        random.randint(0, GRID_HEIGHT - 1),
    )


def occupied_positions():
    return {(p["x"], p["y"]) for p in players.values()}


def find_spawn():
    occupied = occupied_positions()

    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            pos = (x, y)
            if pos not in occupied and pos not in obstacles and pos not in coins:
                return pos

    return None


def spawn_coins():
    coins.clear()
    while len(coins) < COIN_COUNT:
        pos = random_position()
        if pos not in occupied_positions() and pos not in obstacles:
            coins.add(pos)


def spawn_coin():
    while True:
        pos = random_position()
        if pos not in occupied_positions() and pos not in coins and pos not in obstacles:
            coins.add(pos)
            return pos


def add_player(token, name):
    pos = find_spawn()
    if pos is None:
        return False

    x, y = pos

    players[token] = {
        "name": name,
        "x": x,
        "y": y,
        "last_move_tick": -1,
        "score": 0,
    }

    return True


def remove_player(token):
    return players.pop(token, None)


def get_player_name(token):
    player = players.get(token)
    return player["name"] if player else None


def move_player(token, command, current_tick):
    player = players.get(token)
    if not player:
        return "BLOCKED", (0, 0), False

    if player["last_move_tick"] == current_tick:
        return "COOLDOWN", (player["x"], player["y"]), False

    x, y = player["x"], player["y"]

    dx, dy = 0, 0

    if command == "UP":
        dy = 1
    elif command == "DOWN":
        dy = -1
    elif command == "LEFT":
        dx = -1
    elif command == "RIGHT":
        dx = 1

    new_x = x + dx
    new_y = y + dy

    if not (0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT):
        return "BLOCKED", (x, y), False

    if (new_x, new_y) in obstacles:
        return "BLOCKED", (x, y), False

    player["x"] = new_x
    player["y"] = new_y
    player["last_move_tick"] = current_tick

    collected = handle_coin_collection(token, (new_x, new_y))
    return "OK", (new_x, new_y), collected


def handle_coin_collection(token, pos):
    if pos not in coins:
        return False

    coins.remove(pos)

    player = players.get(token)
    if player:
        player["score"] += 10

    spawn_coin()
    return True


def detect_collisions_at(pos, excluding_token=None):
    victims = []
    for token, p in players.items():
        if token == excluding_token:
            continue
        if (p["x"], p["y"]) == pos:
            victims.append(token)
    return victims


def award_kill(killer_token, points=20):
    player = players.get(killer_token)
    if player:
        player["score"] += points


def get_world_state_message():
    player_data = ";".join(
        f"{p['name']}:{p['x']},{p['y']}" for p in players.values()
    )
    coin_data = ";".join(f"{x},{y}" for (x, y) in coins)
    return f"STATE|{player_data}|COINS|{coin_data}"


def get_scoreboard_message():
    return "SCORE|" + ";".join(
        f"{p['name']}:{p['score']}" for p in players.values()
    )


def check_winner():
    if len(players) == 1:
        return next(iter(players.values()))["name"]
    return None