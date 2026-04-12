# Changelog

## 2.8.1

### Fix
- **Lowercase Registry Prefix** — `github.repository_owner` wird jetzt zu lowercase konvertiert, da Docker keine Großbuchstaben in Image-Namen erlaubt

## 2.8.0

### Neu
- **Release Notes aus CHANGELOG** — GitHub Releases werden automatisch mit Inhalten aus CHANGELOG.md befüllt

## 2.7.0

### Neu
- **Brand-Auswahl im Web UI** — Hyundai oder Kia direkt auf der Startseite wählbar, ohne Addon-Konfiguration ändern zu müssen
- **Brand-Dropdown in der Addon-Konfiguration** — `list(hyundai|kia)` statt Freitextfeld
- **Production WSGI Server** — Flask Dev-Server durch gunicorn ersetzt
- **GitHub Actions CI/CD** — Automatischer Multi-Arch Container-Build (amd64, aarch64) mit Push zu ghcr.io
- **Docker Standalone-Anleitung** — README enthält jetzt `docker run` Beispiele für Nutzung ohne Home Assistant

### Verbessert
- **Schnelleres Credential Autofill** — `time.sleep(3)` durch `WebDriverWait` ersetzt, Felder werden befüllt sobald sie im DOM sind
- **Schnellere Texteingabe** — xdotool type delay von 50ms auf 12ms pro Zeichen reduziert
- **Neuer HA Builder** — Migration auf Composite Actions (`home-assistant/builder@2026.03.2`), `build.yaml` entfernt
- **Multi-Arch Manifest** — Ein Image-Name `ghcr.io/tma84/bluelink-token` für alle Architekturen

### Entfernt
- `build.yaml` — nicht mehr benötigt, Inhalte ins Dockerfile migriert
- Architekturen `i386`, `armhf`, `armv7` — für Chromium/Selenium nicht relevant
