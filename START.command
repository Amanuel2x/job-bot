#!/bin/bash
# Mac launcher — double-click this file to start the bot dashboard
cd "$(dirname "$0")"
source venv/bin/activate
python server.py &
sleep 1.5
open http://localhost:8765
wait
