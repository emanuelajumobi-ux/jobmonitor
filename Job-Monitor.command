#!/bin/zsh
# Doppelklick im Finder startet die Lebenslauf-Werkstatt im Browser. Fenster schließen = beenden.
cd "${0:A:h}" || exit 1
exec .venv/bin/python -m jobmonitor gui
