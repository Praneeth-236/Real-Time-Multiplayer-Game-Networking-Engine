players = {}

def add_player(addr, name):
    spawn_x = len(players) * 2
    players[addr] = {
        "name": name,
        "x": spawn_x,
        "y": 0,
        "seq": 0
    }

def move_player(addr, command):

    if command == "UP":
        players[addr]["y"] += 1

    elif command == "DOWN":
        players[addr]["y"] -= 1

    elif command == "LEFT":
        players[addr]["x"] -= 1

    elif command == "RIGHT":
        players[addr]["x"] += 1


def check_collision(addr):

    p1 = players[addr]

    for other in players:

        if other == addr:
            continue

        p2 = players[other]

        if p1["x"] == p2["x"] and p1["y"] == p2["y"]:
            return other

    return None


def eliminate_player(addr):

    name = players[addr]["name"]
    del players[addr]

    return name


def get_world_state():

    state = []

    for addr in players:
        p = players[addr]
        state.append(f"{p['name']}:{p['x']},{p['y']}")

    return "STATE|" + ";".join(state)


def check_winner():

    if len(players) == 1:
        for addr in players:
            return players[addr]["name"]

    return None