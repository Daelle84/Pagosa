# Cozytouch — fork Sauter Pagosa

**En bref :** ce fork de [gduteil/cozytouch](https://github.com/gduteil/cozytouch) (version 1.4)
fait apparaître dans Home Assistant le **chauffe-eau thermodynamique Sauter / Atlantic Pagosa**,
que l'intégration d'origine ne voit pas du tout.

## Pourquoi ce fork

Avec l'intégration d'origine, un compte Cozytouch qui ne contient qu'un Pagosa
n'affiche **aucun appareil** : le Pagosa n'est pas décrit dans la partie Cozytouch
que l'intégration lit. Il est géré par une autre plateforme d'Atlantic, **Overkiz**,
accessible avec le même identifiant et le même mot de passe. Ce fork va le chercher
là quand Cozytouch ne renvoie rien. Les autres appareils (chaudières, pompes à chaleur,
clim) fonctionnent exactement comme avant.

Testé sur un Sauter Pagosa 270 L.

## Ce que vous obtenez dans Home Assistant

Toutes les fonctions de l'application Atlantic, y compris celles qui ne
fonctionnaient pas au départ :

- **Mode de fonctionnement** automatique ou manuel ;
- **Température de consigne** en mode manuel (limites lues sur l'appareil) ;
- **Mode Eco** (en mode manuel, comme dans l'application) ;
- **Boost** de 1 à 7 jours ;
- **Absence** de 48 h minimum, avec durée réglable, un **calendrier** pour la planifier
  et une **date de fin** modifiable sans arrêter l'absence (pratique pour un retour
  avancé ou repoussé) ;
- **Programmation hebdomadaire** (plages de chauffe) ;
- **Date et heure** de l'appareil ;
- **Capteurs** : températures de l'eau, quantité d'eau chaude disponible, temps de
  fonctionnement de la pompe à chaleur et de l'appoint électrique, **consommation
  d'énergie** (utilisable dans le tableau Énergie), réglages, qualité radio, erreurs ;
- **Boutons** pour forcer une actualisation ou identifier l'appareil.

Côté fiabilité : le Pagosa met plusieurs minutes à confirmer un changement, donc
l'état demandé reste affiché le temps qu'il suive. Les limites d'appels d'Overkiz
sont respectées et la session est renouvelée proprement si elle expire.

## Installation

Avec HACS : *Dépôts personnalisés* → ajouter `https://github.com/Daelle84/Pagosa`
(catégorie *Intégration*), installer, puis **redémarrer complètement** Home Assistant.
Ajoutez ensuite l'intégration *Cozytouch* avec vos identifiants de l'application Atlantic.

Manuellement : copier `custom_components/cozytouch` dans `config/custom_components/cozytouch`,
puis redémarrer.

---

*English below.*

# Cozytouch — Sauter Pagosa fork (English)

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
| Absence, 2 days minimum, as the Atlantic app does it (setup period **and** Overkiz commands) | switch *Mode absence*, number *Durée Absence*, calendar *Absence (48 h minimum)*, datetime *Fin de l'absence* |
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
- The Pagosa refuses the direct absence command (`setCurrentOperatingMode`
  ends in `ERRORCOMMAND` in the Overkiz history, from the official app too).
  The Atlantic cloud starts and ends the absence itself from the period stored
  in the setup, about an hour later, and then reports the duration as
  `always`. So the absence switch shows only the real state (no requested
  state in the meantime), *Durée Absence* shows the days left, and *Fin de
  l'absence* moves the end of the period (an end in the past stops it).

Entity names are in French for now.

## Install this fork

HACS: add `https://github.com/Daelle84/Pagosa` as a custom repository
(category *Integration*); `pagosa-1.4` is the default branch. Manually: copy
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

