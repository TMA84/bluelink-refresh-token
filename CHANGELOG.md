# Changelog

## 3.2.0

### Neu
- **Standalone Startup Script** — `run-standalone.sh` für Docker ohne Home Assistant
- Docker Compose nutzt jetzt das richtige Script mit DBUS-Fix und openbox-Konfiguration

### Fix
- "Chrome instance exited" Fehler bei Docker-Standalone behoben

## 3.1.1

### Fix
- Browser füllt gesamten Bildschirm im noVNC (keine Fenster-Dekorationen, maximiert)
- VNC-Frame mit `aspect-ratio: 16/10` statt fixer Höhe — keine schwarzen Balken mehr

## 3.1.0

### Neu
- **Auto-Reset** — Seite wird nach erfolgreichem Transfer automatisch nach 30s zurückgesetzt (oder sofort per Button)

### Fix
- Optionale Felder in config.yaml — Addon startet ohne Zugangsdaten

## 3.0.0

### Neu
- **evcc Integration** — Refresh Token direkt an evcc übertragen
  - evcc URL und Passwort über HA Addon-Konfiguration oder Docker Env-Variablen
  - Automatische Erkennung vorhandener Hyundai/Kia Fahrzeuge
  - Ein Fahrzeug → vollautomatisch: Token senden + evcc Restart
  - Mehrere Fahrzeuge → Checkbox-Auswahl, alle vorausgewählt, Auto-Restart nach Transfer
  - evcc Restart über HA Supervisor API (Addon) oder Shutdown-Endpoint (Docker/nativ)
- **Brand-Option "auto"** — Hersteller-Auswahl nur wenn nötig
  - `auto` (Default): Dropdown auf der Startseite
  - `hyundai` / `kia`: Auswahl wird übersprungen
- **Alle Konfigurationsfelder optional** — Addon startet auch komplett ohne Zugangsdaten
- **evcc-inspiriertes Design** — Montserrat Font, evcc-Grün, runde Boxen, kompaktes Layout
- **Versionsnummer im Footer**
- **Auto-Connect** — evcc wird automatisch verbunden wenn URL konfiguriert ist

### Verbessert
- evcc Auth-Prüfung: Login nur wenn nötig (`/api/auth/status` Check)
- Bessere Fehlermeldungen bei evcc-Verbindungsproblemen
- `DBUS_SESSION_BUS_ADDRESS=/dev/null` für stabilen Chromium-Start
- `run.sh` prüft optionale Felder mit `bashio::config.has_value`

### Fix
- Null-Check für Connect-Button bei Auto-Connect (Button ist ausgeblendet)
- Auto-Restart auch bei teilweisem Transfer-Erfolg

## 2.9.0

### Neu
- **evcc Integration** — Refresh Token direkt an eine evcc-Instanz im Netzwerk übertragen
  - Login mit evcc Admin-Passwort
  - Automatische Erkennung vorhandener Hyundai/Kia Fahrzeuge
  - Token wird getestet und dann als Passwort im Fahrzeug aktualisiert

## 2.8.3

### Fix
- Image-Tags ohne `v` Prefix — HA Supervisor sucht nach `2.8.3`, nicht `v2.8.3`

## 2.8.2

### Fix
- Checkout Step im Manifest-Job für `gh release edit`
- README im Home Assistant Addon-Stil mit Badges und One-Click Install
- MIT LICENSE Datei hinzugefügt

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
