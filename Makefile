# Lokale Befehle. Die Pipeline (GitHub Actions) nutzt nur `python -m jobmonitor run`.
PY ?= .venv/bin/python

.PHONY: cv cv-clean gui app test setup-cv setup-app

## make cv              → allgemeiner Lebenslauf in cv/out/lebenslauf.pdf
## make cv JOB=a1b2c3d4 → auf die Stelle mit dieser ID (aus dem Bericht) zugeschnitten
## make cv STELLE=cv/stellen/firma.txt [FIRMA="Firma GmbH"] [LINK=https://…] → selbst gefundene Stelle (Text)
## make cv URL=https://firma.de/jobs/… [FIRMA="Firma GmbH"]                → selbst gefundene Stelle (Link)
cv:
	$(PY) -m jobmonitor cv $(if $(JOB),--job "$(JOB)",) $(if $(STELLE),--stelle "$(STELLE)",) \
		$(if $(URL),--url "$(URL)",) $(if $(FIRMA),--firma "$(FIRMA)",) $(if $(LINK),--link "$(LINK)",)

## make gui             → Oberfläche im Browser (auch per Doppelklick auf Job-Monitor.command)
gui:
	$(PY) -m jobmonitor gui

## make app             → Job-Monitor.app erzeugen (eigenes App-Fenster mit Icon, ins Dock ziehen)
app: setup-app
	$(PY) -m jobmonitor app

cv-clean:
	rm -rf cv/out

setup-cv:
	$(PY) -m pip install -r requirements-cv.txt

setup-app:
	$(PY) -m pip install -q -r requirements-app.txt

test:
	$(PY) -m pytest -q
