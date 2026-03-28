players = {}

GRID_WIDTH = 10
GRID_HEIGHT = 10

# obstacles
obstacles = {(3, 0), (3, 1), (3, 2)}


def find_spawn():
    occupied = {(p["x"], p["y"]) for p in players.values()}

    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if (x, y) not in occupied and (x, y) not in obstacles:
                return x, y

    return None


def add_player(addr, name):
    pos = find_spawn()
    if pos is None:
        return False

    x, y = pos

    players[addr] = {
        "name": name,
        "x": x,
        "y": y,
        "seq": 0,
        "last_move_tick": -1,
        "score": 0
    }

    return True


def move_player(addr, command, current_tick):

    player = players[addr]

    if player["last_move_tick"] == current_tick:
        return "COOLDOWN"

    x, y = player["x"], player["y"]
    new_x, new_y = x, y

    if command == "UP":
        new_y += 1
    elif command == "DOWN":
        new_y -= 1
    elif command == "LEFT":
        new_x -= 1
    elif command == "RIGHT":
        new_x += 1

    if not (0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT):
        return "BLOCKED"

    if (new_x, new_y) in obstacles:
        return "BLOCKED"

    player["x"] = new_x
    player["y"] = new_y
    player["last_move_tick"] = current_tick

    return "OK"


def detect_collisions():
    position_map = {}

    for addr, p in players.items():
        pos = (p["x"], p["y"])

        if pos not in position_map:
            position_map[pos] = [addr]
        else:
            position_map[pos].append(addr)

    collisions = []

    for pos, addrs in position_map.items():
        if len(addrs) > 1:
            collisions.append(addrs)

    return collisions


def eliminate_players(group):
    names = []
    for addr in group:
        names.append(players[addr]["name"])
        del players[addr]
    return names


def award_score(killer_addr):
    if killer_addr in players:
        players[killer_addr]["score"] += 1


def get_world_state():
    state = []
    for p in players.values():
        state.append(f"{p['name']}:{p['x']},{p['y']}")
    return "STATE|" + ";".join(state)


def get_scoreboard():
    scores = []
    for p in players.values():
        scores.append(f"{p['name']}:{p['score']}")
    return "SCORE|" + ";".join(scores)


def check_winner():
    if len(players) == 1:
        return next(iter(players.values()))["name"]
    return None