# WiZ Thunderstorm

A local browser-based thunderstorm studio that pairs two WiZ smart bulbs with layered rain, wind, spatial thunder, and lightning effects. The Python audio and lighting engine runs on your computer; the interface is served locally and works without a cloud account.

> **Independent portfolio project:** This is a personal prototype and is not affiliated with or endorsed by Signify or WiZ. The implementation was developed with substantial AI assistance. My contribution focused on the product concept, requirements, feature choices, hands-on testing, feedback, and iteration; I do not claim to have written all of the code from scratch.

## Features

- Optional synchronized WiZ smart bulbs
- Adjustable rain and wind intensity
- Spatial close, medium, and far thunder
- Lightning flashes timed to thunder distance
- Relaxing, Summer Storm, and Severe presets
- Adjustable strike intervals and strike mix
- Timed or unlimited sessions
- Responsive browser interface with live storm status
- Local audio playback and controls
- Sound-only mode when bulbs are unavailable or not wanted

## Requirements

- Windows with Python 3 installed
- Speakers or headphones
- Two WiZ bulbs on the same network for synchronized lighting (optional; the current lighting integration is WiZ-specific)

## Setup

1. Download or clone this repository.
2. Open Command Prompt in the project folder.
3. Create a virtual environment:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```

4. Install the dependencies:

   ```bat
   python -m pip install -r requirements.txt
   ```

5. Copy `config.example.json` to `config.json`.
6. Replace the `REPLACE_WITH_..._IP` values in `config.json` with the local IP addresses of your two WiZ bulbs.
7. Run the application. It opens the local control panel in your browser:

   ```bat
   python wiz_thunderstorm_ui.py
   ```

The panel runs at `http://127.0.0.1:8765` and is available only on this computer. Keep the command window open while using the storm. Press `Ctrl+C` there to close the local server.

If the bulbs cannot be reached, the storm continues with audio and the panel reports that lighting is unavailable. Turn on **Sound only** to deliberately run without bulb effects.

An IP address only identifies a device on your network; it does not provide a universal way to control it. This version sends commands through the WiZ local-control integration, so a different smart-light brand will need its own protocol integration before it can control the lighting. Audio-only operation works without any bulbs.

`config.json` is excluded from Git so personal network settings are not published.

## Audio

The included audio files are loaded from `assets/audio`. Their source and license details are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Product positioning

The research notes, evidence limits, suggested product language, and feature implications are in [`PRODUCT_VALUE_PROPOSITION_RESEARCH.md`](PRODUCT_VALUE_PROPOSITION_RESEARCH.md).

For the project story, my role, product decisions, limitations, and next steps, see [`PORTFOLIO_CASE_STUDY.md`](PORTFOLIO_CASE_STUDY.md).

## Code and audio rights

Audio sources and their licenses are documented separately in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). No open-source license is currently granted for the project code. WiZ is a trademark of its respective owner.

