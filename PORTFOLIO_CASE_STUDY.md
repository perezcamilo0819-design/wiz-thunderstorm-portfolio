# WiZ Thunderstorm Simulator

## Connected smart-home product prototype

### Overview

An independent local prototype that turns two WiZ smart bulbs and a computer's speakers into a customizable thunderstorm ambience. The Python engine coordinates lighting and layered audio; a browser-based control panel provides presets, strike timing and distance mix, rain and wind intensity, thunder volume, lightning brightness, and timed or unlimited sessions. Audio-only operation is available when the bulbs are unavailable or not wanted.

### Product opportunity

I wanted a more immersive and adjustable storm ambience than a fixed recording: lightning should feel synchronized with thunder, thunder should have a sense of distance and movement, and listeners should be able to adjust the mix for their room. This began as a personal product hypothesis, not validated market demand.

### My role

I conceived the experience and acted as the product owner for this personal prototype. I defined the desired behavior and controls, made feature and sound-design decisions, tested the experience with my bulbs and speakers, used feedback to guide revisions, and documented setup and asset provenance. I used AI assistance extensively to generate and troubleshoot code. I am not presenting this as software I wrote entirely from scratch or as professional software-engineering experience.

### Product decisions and iteration

- Moved the interface from a basic desktop control surface to a local browser interface while keeping the storm engine in Python.
- Added sound-only operation so the experience remains usable when smart bulbs are not reachable.
- Separated close, medium, and distant thunder and paired strikes with lightning behavior.
- Adjusted audio balance and strike contrast in response to listening tests, including the audibility of background wind and rain and the difference between medium and close thunder.
- Added audio source and license records so project distribution can be reviewed.

### Current state

The project runs locally on Windows with Python, speakers or headphones, and optional WiZ bulbs on the same network. It includes adjustable audio and lighting controls, presets, strike mix, and session timers. It has been exercised by me on my home setup; it has not been evaluated with a representative set of users or at commercial scale.

### Evidence and limitations

The accompanying research note separates findings about nature sounds, sleep and sound masking from consumer interest in long-form rain and thunder media. Large view counts indicate attention to the broader ambience category, not that this simulator improves sleep or that viewers would adopt a smart-lighting product. The product has not been clinically tested. Wind-Down Mode is a possible future feature, not a current capability.

### What I would validate next

1. Interview a small range of people who use ambience audio and observe them trying the controls.
2. Test whether users understand strike distance, can quickly create a preferred mix, and can recover from unavailable bulbs or interrupted playback.
3. Use those observations to prioritize one next feature, such as a user-controlled gradual wind-down, and test its usefulness before expanding the product.

### Career relevance

This project is evidence of product framing, requirements thinking, hands-on acceptance testing, iterative problem-solving, technical communication, and responsible use of AI-assisted prototyping. It is a supporting portfolio example; it does not demonstrate a commercial launch, measured customer outcomes, or advanced software engineering.

