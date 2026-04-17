## Update: v3.0 — Direkte evcc-Anbindung

Kurzes Update: Ab v3.0 kann der Token **direkt an evcc übertragen** werden — kein Copy-Paste mehr nötig.

### Was ist neu?

- **Automatische Token-Übertragung an evcc** — evcc-URL konfigurieren, nach dem Login wird der Token automatisch ins richtige Fahrzeug eingetragen und evcc neugestartet
- **Mehrere Fahrzeuge** — wer z.B. einen EV6 und einen Niro mit dem gleichen Account hat, kann per Checkbox auswählen welche den Token bekommen
- **Hersteller vorkonfigurierbar** — Brand kann in der Config auf `hyundai` oder `kia` gesetzt werden, dann entfällt die Auswahl im UI
- **Alle Felder optional** — das Addon startet auch komplett ohne Zugangsdaten
- **Docker Compose** — `docker-compose.yaml` liegt jetzt im Repo

### Konfiguration (HA Addon)

In der Addon-Konfiguration einfach die evcc-URL eintragen:

| Option | Beschreibung |
|--------|-------------|
| `evcc_url` | z.B. `http://192.168.1.100:7070` |
| `evcc_password` | evcc Admin-Passwort (leer lassen wenn keins gesetzt) |

Danach läuft der Flow so: Token generieren → evcc verbindet automatisch → Token wird übertragen → evcc wird neugestartet.

### Konfiguration (Docker)

```yaml
services:
  bluelink-token:
    image: ghcr.io/tma84/bluelink-token:latest
    ports:
      - "9876:9876"
      - "6080:6080"
    environment:
      - BRAND=hyundai
      - EVCC_URL=http://192.168.1.100:7070
      - EVCC_PASSWORD=
    shm_size: 256m
    restart: unless-stopped
```

Alle Env-Variablen sind optional.

**GitHub:** https://github.com/TMA84/bluelink-refresh-token
