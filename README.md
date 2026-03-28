# Real-Time-Multiplayer-Game-Networking-Engine

UDP-based real-time multiplayer grid game with a lightweight server and a Pygame client.

## Features
- Real-time movement over UDP with sequence/ACK handling
- Coin collection and scoring
- Player elimination and win condition
- Client UI with minimap, kill feed, and latency graph

## Requirements
- Python 3.9+
- pygame

Install pygame:
```bash
pip install pygame
```

## How to Run
1) Start the server:
```bash
python server.py
```

2) In a new terminal, start the client UI:
```bash
python client_ui.py
```

## Controls
- Move: `WASD` or arrow keys

## Notes
- Default host: `127.0.0.1`, port: `8080`
- Runs on a 10x10 grid with coin spawning and scoring



