# NS vertrekbord

A Home Assistant integration that shows the **departure board of a Dutch railway station** (NS), like the yellow/white boards on the platform: minutes until departure, train type, final destination, via stations, track (and track changes), delays, cancellations and NS messages, plus the next trains.

Pair it with the [NS Vertrekbord Card](https://github.com/nosehook/ns-vertrekbord-card) to show it as a station board on your dashboard.

## Features

- Pick any NS station and optionally a **direction**: only trains that call at or go to e.g. *Utrecht Centraal*.
- Optional filter on **train type** (Sprinter, Intercity, …).
- Entities per board:
  - **Vertrek over** — minutes until the next running train (counts down locally between updates)
  - **Vertrektijd** — expected departure time
  - **Eindbestemming** — final destination
  - **Spoor** — track (with planned track and a *changed* flag)
  - **Vertraagd** — next train is delayed
  - **Rijdt niet** — the first train on the board is cancelled
- The *Vertrek over* sensor carries the whole board as attributes: train type, destination, via stations (full names), planned/expected time, delay in minutes, planned/actual track, cancellation, NS messages and the next departures.
- Reuses the API key of the built-in *Nederlandse Spoorwegen* integration when present.
- One API call per board per minute. Change direction and train types later via **Configure**.
- Dutch and English.

## Requirements

An NS API key (free) from [apiportal.ns.nl](https://apiportal.ns.nl/), product **Ns-App** (Reisinformatie API). If you already use the built-in *Nederlandse Spoorwegen* integration, its key is reused automatically.

## Installation

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=nosehook&repository=ns-vertrekbord&category=integration)

<!-- ha-marketplace:exclude-start -->
### Marketplace (Home Assistant 2026.11 and later)
1. Click the button above, or open the **Marketplace** and add `https://github.com/nosehook/ns-vertrekbord` by its link, category **Integration**.
2. Install **NS vertrekbord** and restart Home Assistant.

### HACS (Home Assistant before 2026.11)
Add `https://github.com/nosehook/ns-vertrekbord` as a custom repository, category **Integration**, install and restart.

### Manual
Copy `custom_components/ns_vertrekbord` to `/config/custom_components/` and restart.
<!-- ha-marketplace:exclude-end -->

Then add a board under **Settings → Devices & services → Add integration → NS vertrekbord**.

## Data

Departure data from the NS Reisinformatie API. This integration is not affiliated with or endorsed by NS.

## License

MIT
