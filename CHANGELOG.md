# Changelog

## 4.3.0

### Neu
- **Headless Login** für EU Kia und EU Hyundai — komplett ohne Browser
  - Durch Reverse Engineering der Kia Connect App (v2.1.27) entwickelt
  - Nutzt `curl_cffi` für Android Chrome TLS-Fingerprint
  - RSA-Passwort-Verschlüsselung wie die originale App
  - Signin direkt mit App `client_id` → Code im Redirect (kein `connector_session_key`)
- **Auto-Login** — Token wird automatisch beim Container-Start generiert wenn Credentials konfiguriert sind
- **Vereinfachte Web-UI für EU** — Credentials eingeben, "Generate Token" klicken, fertig
  - Kein "Start" Zwischenschritt, kein Remote Browser für EU Brands
  - Remote Browser nur noch für nicht-EU Regionen sichtbar
- **Quick Login API** — `/api/quicklogin` Endpoint für direkten headless Login aus der UI
- **Brand-Auswahl im Quick Login** — UI-Auswahl wird korrekt an den Login durchgereicht
- **Nicht-EU Regionen ausgeblendet** — nur über `show_all_regions` Option aktivierbar
- **evcc Passwort maskiert** — wird in HA als Passwort-Feld angezeigt (nicht Klartext)
- **Reset Button** auf Success- und Error-Seite

### Fix
- EU Hyundai: headless Token-Exchange nach Browser-Login (umgeht `connector_session_key` Block)
- Brand-Override wird bei Quick Login korrekt gesetzt

## 4.2.1

### Verbesserung
- Remote Browser (noVNC) nur noch für nicht-EU Brands sichtbar
- EU Kia/Hyundai: nur Credentials + Login Button (cleaner UI)
- "Fill only" Button nur bei nicht-EU Brands

## 4.2.0

### Neu
- **`show_all_regions` Option** — nicht-EU Regionen im Brand-Selector nur wenn aktiviert
- **evcc Passwort maskiert** — wird in HA als Passwort-Feld angezeigt (nicht Klartext)
- Brand-Schema in HA-Config auf EU reduziert

## 4.1.3

### Fix
- EU Hyundai: headless Token-Exchange nach Browser-Login (umgeht `connector_session_key` Block)

## 4.1.2

### Neu
- **Auto-Login** — headless Login startet automatisch beim Container-Start wenn `BLUELINK_USERNAME` + `BLUELINK_PASSWORD` gesetzt sind

## 4.1.1

### Fix
- Headless Login wird jetzt auch im `get_token_thread` vor dem Browser-Start versucht

## 4.1.0

### Neu
- **Headless Login** für EU Kia und EU Hyundai — komplett ohne Browser
  - Durch Reverse Engineering der Kia Connect App (v2.1.27) entwickelt
  - Nutzt `curl_cffi` für Android Chrome TLS-Fingerprint
  - RSA-Passwort-Verschlüsselung wie die originale App
  - Signin direkt mit App `client_id` → Code im Redirect
- **Fill & Login UI** — Username/Password Felder im Web-Interface
- `/api/autologin` Endpoint (xdotool + headless Fallback)
- `curl_cffi` + `pycryptodome` als neue Dependencies
- Paste-Feld durch Fill & Login ersetzt

## 4.0.2

### Fix
- Erweiterte Anti-Detection gegen Kia Abuse-Erkennung

## 4.0.1

### Fix
- Mobile User-Agent für EU Kia/Hyundai
- Bessere OAuth Fehlermeldungen

## 4.0.0

### Neu
- **Multi-Region Support** — Europa, China, Australien, Neuseeland, Indien, Brasilien
  - 12 Region/Brand-Kombinationen (eu_kia, eu_hyundai, cn_kia, cn_hyundai, au_kia, au_hyundai, nz_kia, in_kia, in_hyundai, br_hyundai)
  - Gruppierte Dropdown-Auswahl nach Region
  - Legacy-Aliase: `kia` → `eu_kia`, `hyundai` → `eu_hyundai`
- **Anti-Detection** — `--disable-blink-features=AutomationControlled` verhindert Selenium-Erkennung
- **Robustere Code-Erkennung** — `code=` in URL statt spezifischer Pfad-Patterns
- **Flexiblerer Code-Regex** — `[?&]code=([^&]+)` statt UUID-spezifisches Pattern
- **Konfigurierbarer User-Agent** — pro Region/Brand (z.B. iOS UA für Brasilien)
- **Separate Redirect-URL** — EU-Brands nutzen einen separaten Authorize-Redirect nach Login

### Fix
- Hyundai "Bad Request" nach Login behoben (robusterer Redirect-Flow)
- Non-EU Regionen ohne success_selector werden unterstützt (warten auf `code=` in URL)

## 3.4.0

### Neu
- **Country-Code konfigurierbar** — `country` Option (Default: `DE`) für die Hyundai Login-URL
  - Behebt "Bad Request" Fehler bei Hyundai-Nutzern (Login-Seite zeigte niederländische Seite statt der richtigen)

### Fix
- Hyundai Login-URL: `state=NL_` durch `state={country}_` ersetzt (basierend auf RustyDust Fix)
- Hyundai Redirect-Pattern: akzeptiert jetzt auch `/connector` Pfad neben `/token`

## 3.3.0

### Neu
- **Home Assistant Sensor** — `sensor.bluelink_token_expiry` wird nach Token-Generierung erstellt
  - Zeigt das Ablaufdatum (180 Tage)
  - Attribute: Generierungsdatum, Ablaufdatum, verbleibende Tage, Brand
  - Device Class `date` für Automationen (z.B. Erinnerung vor Ablauf)
- Ablaufdatum wird auf der Erfolgsseite angezeigt

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

## 2.6.0

### Neu
- **GitHub Actions CI/CD** — automatischer Multi-Arch Container-Build (amd64, aarch64) mit Push zu ghcr.io

## 2.5.1

### Fix
- **Production WSGI Server** — Flask Dev-Server durch gunicorn ersetzt für stabileren Betrieb

## 2.5.0

### Neu
- **Brand-Auswahl im Web UI** — Hyundai oder Kia direkt auf der Startseite wählbar
- **Schnelleres Credential Autofill** — `WebDriverWait` statt `time.sleep(3)`
- **Schnellere Texteingabe** — xdotool delay von 50ms auf 12ms reduziert

## 2.4.1

### Neu
- Initial Release: Bluelink Token Generator als Home Assistant Add-on
- Chromium Browser mit mobilem User-Agent im Container
- noVNC Remote-Viewer für Browser-Interaktion
- Automatische Token-Extraktion nach Login
- Unterstützung für Hyundai und Kia (EU)
