# Cozytouch — Sauter Pagosa fork

This branch is a fork of [gduteil/cozytouch](https://github.com/gduteil/cozytouch) **1.4**
that adds the **Sauter / Atlantic Pagosa** thermodynamic water heater.

The Pagosa does not show up in the Cozytouch setup (`setupviewv2`) that the
integration reads. It lives on Atlantic's **Overkiz** plane instead, reached
with the same account: `/users/token`, then `/magellan/accounts/jwt`, then
`ha110-1.overkiz.com/enduser-mobile-web/enduserAPI/login`. When the Cozytouch
setup has no device, the integration now falls back to Overkiz and picks up
the heater (`io:AtlanticDomesticHotWaterProductionV3IOComponent`) and its
energy meter (`io:DHWCumulatedElectricalEnergyConsumptionIOSystemDeviceSensor`).
Other devices keep the original behaviour.

Tested on one Sauter Pagosa 270 L. Discussion upstream: gduteil/cozytouch issues.

## What the Pagosa gets

| Feature | Entities |
| ------- | -------- |
| Operating mode (auto / manual) | select *Mode de fonctionnement* |
| Target temperature (manual mode, limits read from the device) | number *Température de consigne* |
| Eco (manual mode only) | switch *Mode Eco* |
| Boost, 1 to 7 days | switch *Boost ECS*, number *Durée Boost* |
| Absence, 2 days minimum, as the Atlantic app does it (setup period **and** Overkiz commands) | switch *Mode absence*, number *Durée Absence*, calendar *Absence (48 h minimum)* |
| Weekly programming | time *Programmation n - début / fin* |
| Device clock | datetime *Date et heure de l'appareil* |
| Temperatures, water use, heat pump and electric back-up run time, energy, settings, radio signal, errors | sensors |
| Manual refreshes, identify the heater | buttons |

How it behaves:

- Commands are serialized; the Pagosa takes minutes to report a change, so the
  requested state is shown until the real one matches or a grace period ends,
  then one delayed refresh confirms it.
- Overkiz rate limits (HTTP 429 and `Retry-After`) are respected and an expired
  session is renewed once on HTTP 401, never retried in a loop.
- Eco and the target temperature are refused in automatic mode, as in the app;
  Boost works in both. An absence overrides everything.

Entity names are in French for now.

## Install this fork

HACS: add `https://github.com/Daelle84/Pagosa` as a custom repository
(category *Integration*) and pick the `pagosa-1.4` branch. Manually: copy
`custom_components/cozytouch` to `config/custom_components/cozytouch`.
A full Home Assistant restart is needed after any update.

---

# Cozytouch
This is an Atlantic Cozytouch cloud integration. Atlantic use multiple protocols, in my case the protocol is different than the one implemented by official integration (overkiz).

This has been tested using on : 
  - `Atlantic Naema 2 Micro 25` gas boiler using a `Ǹavilink Radio-Connect 128` thermostat
  - `Atlantic Naema 2 Duo 25` gas boiler using a `Ǹavilink Radio-Connect 128` thermostat
  - `Atlantic Naia 2 Micro 25` gas boiler using a `Ǹavilink Radio-Connect 128` thermostat
  - `Atlantic Loria Duo 6006 R32` heat pump using a `Navilink Radio-Connect 128` thermostat
  - `Takao M3` air conditionning
  - `Kelud 1750W` towel rack
  - `Sauter Asama Connecté II Ventilo 1750W` towel rack

A special mapping needs to be done for each model type, feel free to create an issue to help supporting your device.


## Installation

You can install it using HACS or manually.

#### With HACS

[![Add HACS repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gduteil&repository=cozytouch&category=integration)

More informations about HACS [here](https://hacs.xyz/).

#### Manually

Clone this repository and copy `custom_components/cozytouch` to your Home Assistant config durectory (ex : `config/custom_components/cozytouch`)

Restart Home Assistant.

## Configuration

Once your Home Assistant has restarted, go to `Settings -> Devices & Services -> Add an  integration`.

Search for `cozytouch` and select the `Atlantic Cozytouch` integration.

Enter your Cozytouch credentials.

If connection is working, you should have a list of devices configured on your account.

Select the device you want to add.

Only some values are mapped for now, you can select `Create entities for unknown capabilities` if you want to add all detected capabilities (this can be useful to help mapping).

