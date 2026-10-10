import asyncio
import json
import random
import threading
import queue
import math
import struct
import array
from pathlib import Path

import pygame
from pywizlight import wizlight, PilotBuilder


# ============================================================
# DEVICE / AUDIO FILES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
AUDIO_DIR = BASE_DIR / "assets" / "audio"


def load_config():

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            "Missing config.json. Copy config.example.json to "
            "config.json and enter your WiZ bulb IP addresses."
        )

    with CONFIG_FILE.open(
        "r",
        encoding="utf-8"
    ) as config_file:
        return json.load(config_file)


config = load_config()

BULB_1 = config["bulb_1"]
BULB_2 = config["bulb_2"]

LIGHT_RAIN_FILE = str(
    AUDIO_DIR / "Light Rain.wav"
)
NORMAL_RAIN_FILE = str(
    AUDIO_DIR / "Normal Rain.mp3"
)
HEAVY_RAIN_FILE = str(
    AUDIO_DIR / "Heavy Rain.mp3"
)

WIND_FILE = str(
    AUDIO_DIR / "Wind.mp3"
)

THUNDER_CLOSE_FILE = str(
    AUDIO_DIR / "thunder_close.mp3"
)
THUNDER_MEDIUM_FILE = str(
    AUDIO_DIR / "thunder_medium.wav"
)
THUNDER_FAR_FILE = str(
    AUDIO_DIR / "thunder_far.wav"
)


def make_seamless_loop(
    sound,
    crossfade_ms=2000,
    loudness_curve=1.0,
):
    """Crossfade a sound's end into its beginning for smoother ambience loops."""

    mixer_format = pygame.mixer.get_init()

    if mixer_format is None:
        return sound

    sample_rate, sample_format, channels = mixer_format

    # pygame's default mixer format is signed 16-bit PCM. Leave other formats
    # untouched rather than interpreting their raw sample data incorrectly.
    if sample_format != -16 or channels not in (1, 2):
        return sound

    frame_bytes = channels * 2
    raw = bytearray(sound.get_raw())

    # Apply an upward loudness curve to quiet ambience sources whose encoded
    # preview is much quieter than the other project tracks. This preserves
    # full-scale peaks while making low-level texture easier to hear.
    if 0 < loudness_curve < 1:
        curve = array.array(
            "h",
            (
                round(
                    math.copysign(
                        (abs(sample) / 32768) ** loudness_curve
                        * 32767,
                        sample,
                    )
                )
                for sample in range(-32768, 32768)
            ),
        )
        samples = memoryview(raw).cast("h")

        for index, sample in enumerate(samples):
            samples[index] = curve[sample + 32768]

        del samples

    frame_count = len(raw) // frame_bytes
    overlap_frames = min(
        int(sample_rate * crossfade_ms / 1000),
        frame_count // 4,
    )

    if overlap_frames < 2:
        return sound

    overlap_bytes = overlap_frames * frame_bytes
    tail_start = len(raw) - overlap_bytes

    for frame in range(overlap_frames):
        progress = frame / (overlap_frames - 1)
        tail_gain = math.cos(progress * math.pi / 2)
        head_gain = math.sin(progress * math.pi / 2)
        head_frame = frame * frame_bytes
        tail_frame = tail_start + head_frame

        for channel in range(channels):
            sample_offset = channel * 2
            head_sample = struct.unpack_from(
                "<h",
                raw,
                head_frame + sample_offset,
            )[0]
            tail_sample = struct.unpack_from(
                "<h",
                raw,
                tail_frame + sample_offset,
            )[0]
            mixed_sample = round(
                tail_sample * tail_gain
                + head_sample * head_gain
            )
            mixed_sample = max(
                -32768,
                min(32767, mixed_sample),
            )

            struct.pack_into(
                "<h",
                raw,
                tail_frame + sample_offset,
                mixed_sample,
            )

    # The blended tail now leads back into the retained audio after the
    # overlapped head, with no abrupt restart at the loop point.
    del raw[:overlap_bytes]

    return pygame.mixer.Sound(buffer=raw)


# ============================================================
# SHARED SETTINGS
# ============================================================

settings_lock = threading.Lock()

storm_settings = {
    "min_interval": 5.0,
    "max_interval": 14.0,

    "rain_intensity": 55,
    "wind_intensity": 35,

    "thunder_volume": 0.42,
    "lightning_brightness": 240,

    "close_weight": 20,
    "medium_weight": 45,
    "far_weight": 35,
    "audio_only": False,
}

command_queue = queue.Queue()
app_state_lock = threading.Lock()
app_state = {
    "storm": "Stopped",
    "strike": "Idle",
    "next": "--",
    "timer": "--",
    "event": "Ready",
    "preset": "custom",
    "ready": False,
    "bulbs": "Ready to check",
}


# ============================================================
# RAIN MIXING
# ============================================================

def calculate_rain_mix(intensity):
    """
    Rain slider:
    0   = silence
    1-35 = Light Rain
    35-65 = crossfade Light -> Normal
    65-100 = crossfade Normal -> Heavy
    """

    intensity = max(
        0,
        min(100, intensity)
    )

    light = 0.0
    normal = 0.0
    heavy = 0.0

    if intensity == 0:
        return light, normal, heavy

    elif intensity <= 35:
        light = intensity / 35

    elif intensity <= 65:
        progress = (
            intensity - 35
        ) / 30

        light = 1.0 - progress
        normal = progress

    else:
        progress = (
            intensity - 65
        ) / 35

        normal = 1.0 - progress
        heavy = progress

    return (
        max(0.0, min(1.0, light)),
        max(0.0, min(1.0, normal)),
        max(0.0, min(1.0, heavy)),
    )


# ============================================================
# STORM ENGINE
# ============================================================

async def storm_engine():

    bulb1 = wizlight(BULB_1)
    bulb2 = wizlight(BULB_2)

    pygame.mixer.init()
    pygame.mixer.set_num_channels(10)

    light_rain = make_seamless_loop(
        pygame.mixer.Sound(LIGHT_RAIN_FILE)
    )

    normal_rain = make_seamless_loop(
        pygame.mixer.Sound(NORMAL_RAIN_FILE)
    )

    heavy_rain = make_seamless_loop(
        pygame.mixer.Sound(HEAVY_RAIN_FILE),
        crossfade_ms=8000,
    )

    wind = make_seamless_loop(
        pygame.mixer.Sound(WIND_FILE),
        loudness_curve=0.70,
    )

    thunder_close = pygame.mixer.Sound(
        THUNDER_CLOSE_FILE
    )

    thunder_medium = pygame.mixer.Sound(
        THUNDER_MEDIUM_FILE
    )

    thunder_far = pygame.mixer.Sound(
        THUNDER_FAR_FILE
    )

    light_rain_channel = pygame.mixer.Channel(0)
    normal_rain_channel = pygame.mixer.Channel(1)
    heavy_rain_channel = pygame.mixer.Channel(2)

    wind_channel = pygame.mixer.Channel(3)
    thunder_channel = pygame.mixer.Channel(4)

    storm_active = False
    storm_end_time = None
    next_strike_at = None
    current_event_task = None
    bulbs_available = True

    running = True

    last_timer_display = None
    last_next_display = None


    def get_settings():
        with settings_lock:
            return dict(storm_settings)


    async def set_both_lights(pilot):

        await asyncio.gather(
            bulb1.turn_on(pilot),
            bulb2.turn_on(pilot)
        )


    def send_ui(kind, value):
        with app_state_lock:
            app_state[kind] = value


    send_ui("ready", True)


    def update_ambience():

        current = get_settings()

        light_vol, normal_vol, heavy_vol = (
            calculate_rain_mix(
                current["rain_intensity"]
            )
        )

        light_rain_channel.set_volume(
            light_vol
        )

        normal_rain_channel.set_volume(
            normal_vol
        )

        heavy_rain_channel.set_volume(
            heavy_vol
        )

        # Wind.mp3 has a much lower average level than the rain assets, so
        # use a square-root taper to make low and medium slider settings audible.
        wind_intensity = max(
            0.0,
            min(100.0, current["wind_intensity"]),
        ) / 100

        wind_volume = math.sqrt(wind_intensity)

        wind_channel.set_volume(
            wind_volume
        )


    def pan_values(position, volume):

        position = max(
            -1.0,
            min(1.0, position)
        )

        if position < 0:

            left = volume

            right = volume * (
                1.0 + position
            )

        else:

            left = volume * (
                1.0 - position
            )

            right = volume

        return left, right


    async def lightning_flash(strike_type):

        nonlocal bulbs_available

        current = get_settings()

        if current.get("audio_only") or not bulbs_available:
            return

        max_brightness = int(
            current["lightning_brightness"]
        )

        if strike_type == "close":

            flashes = random.choice(
                [2, 3, 3]
            )

            minimum = max(
                100,
                max_brightness - 10
            )

        elif strike_type == "medium":

            flashes = random.choice(
                [1, 2, 2]
            )

            minimum = max(
                90,
                max_brightness - 30
            )

        else:

            flashes = random.choice(
                [1, 1, 2]
            )

            minimum = max(
                80,
                max_brightness - 60
            )

        for flash_number in range(flashes):

            flash = PilotBuilder(
                rgb=(255, 255, 255),
                brightness=random.randint(
                    minimum,
                    max_brightness
                )
            )

            try:
                await asyncio.wait_for(
                    set_both_lights(flash),
                    timeout=2.5,
                )
            except Exception:
                bulbs_available = False
                send_ui("bulbs", "Offline · sound only")
                return

            await asyncio.sleep(
                random.uniform(
                    0.05,
                    0.13
                )
            )

            storm_light = PilotBuilder(
                rgb=(120, 140, 180),
                brightness=35
            )

            try:
                await asyncio.wait_for(
                    set_both_lights(storm_light),
                    timeout=2.5,
                )
            except Exception:
                bulbs_available = False
                send_ui("bulbs", "Offline · sound only")
                return

            if flash_number < flashes - 1:

                await asyncio.sleep(
                    random.uniform(
                        0.05,
                        0.20
                    )
                )


    async def move_thunder(
        channel,
        start_position,
        end_position,
        duration,
        volume
    ):

        steps = 40

        for step in range(
            steps + 1
        ):

            progress = (
                step / steps
            )

            position = (
                start_position
                + (
                    end_position
                    - start_position
                )
                * progress
            )

            left, right = pan_values(
                position,
                volume
            )

            channel.set_volume(
                left,
                right
            )

            await asyncio.sleep(
                duration / steps
            )


    async def play_thunder(
        strike_type
    ):

        current = get_settings()

        base_volume = current[
            "thunder_volume"
        ]

        if strike_type == "close":

            sound = thunder_close

            volume = (
                base_volume * 1.65
            )

            start_position = (
                random.uniform(
                    -0.20,
                    0.20
                )
            )

            end_position = (
                random.uniform(
                    -0.08,
                    0.08
                )
            )

            movement_duration = (
                random.uniform(
                    1.0,
                    2.0
                )
            )

        elif strike_type == "medium":

            sound = thunder_medium
            volume = (
                base_volume * 0.85
            )

            start_position = (
                random.choice([
                    -0.9,
                    -0.7,
                    0.7,
                    0.9
                ])
            )

            if random.random() < 0.65:
                end_position = (
                    -start_position
                )
            else:
                end_position = (
                    random.uniform(
                        -0.25,
                        0.25
                    )
                )

            movement_duration = (
                random.uniform(
                    2.5,
                    4.5
                )
            )

        else:

            sound = thunder_far

            volume = (
                base_volume * 0.60
            )

            start_position = (
                random.choice([
                    -1.0,
                    -0.85,
                    0.85,
                    1.0
                ])
            )

            if random.random() < 0.80:
                end_position = (
                    -start_position
                )
            else:
                end_position = (
                    random.uniform(
                        -0.4,
                        0.4
                    )
                )

            movement_duration = (
                random.uniform(
                    5.0,
                    8.0
                )
            )

        volume = min(
            1.0,
            volume
        )

        left, right = pan_values(
            start_position,
            volume
        )

        thunder_channel.set_volume(
            left,
            right
        )

        thunder_channel.play(
            sound
        )

        await move_thunder(
            thunder_channel,
            start_position,
            end_position,
            movement_duration,
            volume
        )


    async def run_strike_event(
        strike_type
    ):

        name = strike_type.capitalize()

        send_ui(
            "strike",
            name
        )

        await lightning_flash(
            strike_type
        )

        if strike_type == "close":
            delay = random.uniform(
                0.4,
                1.3
            )

        elif strike_type == "medium":
            delay = random.uniform(
                2.0,
                4.0
            )

        else:
            delay = random.uniform(
                5.0,
                8.0
            )

        send_ui(
            "event",
            f"{name} lightning — thunder in {delay:.1f}s"
        )

        await asyncio.sleep(
            delay
        )

        send_ui(
            "event",
            f"{name} thunder"
        )

        await play_thunder(
            strike_type
        )

        send_ui(
            "strike",
            "Waiting"
        )

        send_ui(
            "event",
            "Waiting for next strike..."
        )


    async def start_storm(
        duration_minutes
    ):

        nonlocal storm_active
        nonlocal storm_end_time
        nonlocal next_strike_at
        nonlocal bulbs_available

        if storm_active:
            return

        # Start every ambience track silently.
        light_rain_channel.set_volume(0)
        normal_rain_channel.set_volume(0)
        heavy_rain_channel.set_volume(0)
        wind_channel.set_volume(0)

        light_rain_channel.play(
            light_rain,
            loops=-1,
            fade_ms=1000
        )

        normal_rain_channel.play(
            normal_rain,
            loops=-1,
            fade_ms=1000
        )

        heavy_rain_channel.play(
            heavy_rain,
            loops=-1,
            fade_ms=1000
        )

        wind_channel.play(
            wind,
            loops=-1,
            fade_ms=1000
        )

        update_ambience()

        storm_light = PilotBuilder(
            rgb=(120, 140, 180),
            brightness=35
        )

        current = get_settings()

        if current.get("audio_only"):
            bulbs_available = False
            send_ui("bulbs", "Sound only")
        else:
            try:
                await asyncio.wait_for(
                    set_both_lights(storm_light),
                    timeout=2.5,
                )
                bulbs_available = True
                send_ui("bulbs", "Connected")
            except Exception:
                bulbs_available = False
                send_ui("bulbs", "Offline · sound only")

        storm_active = True

        now = (
            asyncio.get_running_loop().time()
        )

        if duration_minutes is None:

            storm_end_time = None

        else:

            storm_end_time = (
                now
                + duration_minutes * 60
            )

        current = get_settings()

        next_strike_at = (
            now
            + random.uniform(
                current["min_interval"],
                current["max_interval"]
            )
        )

        send_ui(
            "storm",
            "Running"
        )

        send_ui(
            "strike",
            "Waiting"
        )

        if current.get("audio_only"):
            event_message = "Sound-only storm active"
        elif bulbs_available:
            event_message = "Storm ambience active"
        else:
            event_message = "WiZ bulbs unavailable · sound is running"

        send_ui("event", event_message)


    async def stop_storm(
        reason="Stopped"
    ):

        nonlocal storm_active
        nonlocal storm_end_time
        nonlocal next_strike_at
        nonlocal current_event_task
        nonlocal bulbs_available

        storm_active = False

        storm_end_time = None
        next_strike_at = None

        if (
            current_event_task
            and not current_event_task.done()
        ):

            current_event_task.cancel()

            try:
                await current_event_task

            except asyncio.CancelledError:
                pass

        current_event_task = None

        light_rain_channel.fadeout(1000)
        normal_rain_channel.fadeout(1000)
        heavy_rain_channel.fadeout(1000)

        wind_channel.fadeout(1000)
        thunder_channel.fadeout(600)

        normal_light = PilotBuilder(
            rgb=(255, 220, 180),
            brightness=120
        )

        current = get_settings()

        if bulbs_available and not current.get("audio_only"):
            try:
                await asyncio.wait_for(
                    set_both_lights(normal_light),
                    timeout=2.5,
                )
            except Exception:
                bulbs_available = False
                send_ui("bulbs", "Offline")

        send_ui(
            "storm",
            "Stopped"
        )

        send_ui(
            "strike",
            "Idle"
        )

        send_ui(
            "event",
            reason
        )

        send_ui(
            "next",
            "--"
        )

        send_ui(
            "timer",
            "--"
        )


    while running:

        now = (
            asyncio.get_running_loop().time()
        )

        # ----------------------------------------------------
        # UI COMMANDS
        # ----------------------------------------------------

        while True:

            try:

                command, payload = (
                    command_queue.get_nowait()
                )

            except queue.Empty:

                break

            if command == "start":

                await start_storm(
                    payload
                )

            elif command == "stop":

                await stop_storm(
                    "Storm stopped"
                )

            elif command == "test_lightning":

                if (
                    current_event_task is None
                    or current_event_task.done()
                ):

                    current_event_task = (
                        asyncio.create_task(
                            lightning_flash(
                                payload
                            )
                        )
                    )

            elif command == "test_thunder":

                if (
                    current_event_task is None
                    or current_event_task.done()
                ):

                    current_event_task = (
                        asyncio.create_task(
                            play_thunder(
                                payload
                            )
                        )
                    )

            elif command == "shutdown":

                if storm_active:

                    await stop_storm(
                        "Application closing"
                    )

                running = False


        # ----------------------------------------------------
        # FINISHED EVENT
        # ----------------------------------------------------

        if (
            current_event_task
            and current_event_task.done()
        ):

            try:
                current_event_task.result()

            except asyncio.CancelledError:
                pass

            except Exception as error:

                send_ui(
                    "event",
                    f"Error: {error}"
                )

            current_event_task = None

            if storm_active:

                current = get_settings()

                next_strike_at = (
                    now
                    + random.uniform(
                        current["min_interval"],
                        current["max_interval"]
                    )
                )


        # ----------------------------------------------------
        # TIMER
        # ----------------------------------------------------

        if (
            storm_active
            and storm_end_time is not None
            and now >= storm_end_time
        ):

            await stop_storm(
                "Storm timer finished"
            )


        # ----------------------------------------------------
        # NEW STRIKE
        # ----------------------------------------------------

        if (
            storm_active
            and current_event_task is None
            and next_strike_at is not None
            and now >= next_strike_at
        ):

            current = get_settings()

            weights = [
                current["close_weight"],
                current["medium_weight"],
                current["far_weight"]
            ]

            if sum(weights) <= 0:

                weights = [
                    1,
                    1,
                    1
                ]

            strike_type = random.choices(
                [
                    "close",
                    "medium",
                    "far"
                ],
                weights=weights,
                k=1
            )[0]

            next_strike_at = None

            current_event_task = (
                asyncio.create_task(
                    run_strike_event(
                        strike_type
                    )
                )
            )


        # ----------------------------------------------------
        # LIVE AMBIENCE
        # ----------------------------------------------------

        if storm_active:

            update_ambience()


        # ----------------------------------------------------
        # NEXT STRIKE DISPLAY
        # ----------------------------------------------------

        if (
            storm_active
            and next_strike_at is not None
        ):

            seconds = max(
                0,
                int(
                    next_strike_at
                    - now
                )
            )

            if seconds != last_next_display:

                send_ui(
                    "next",
                    f"{seconds}s"
                )

                last_next_display = (
                    seconds
                )


        # ----------------------------------------------------
        # TIMER DISPLAY
        # ----------------------------------------------------

        if (
            storm_active
            and storm_end_time is not None
        ):

            remaining = max(
                0,
                int(
                    storm_end_time
                    - now
                )
            )

            minutes = remaining // 60
            seconds = remaining % 60

            display = (
                f"{minutes:02d}:{seconds:02d}"
            )

            if display != last_timer_display:

                send_ui(
                    "timer",
                    display
                )

                last_timer_display = (
                    display
                )

        elif storm_active:

            send_ui(
                "timer",
                "Unlimited"
            )


        await asyncio.sleep(
            0.10
        )

    pygame.mixer.quit()


# ============================================================
# ENGINE THREAD
# ============================================================

def engine_thread():
    try:
        asyncio.run(storm_engine())
    except Exception as error:
        with app_state_lock:
            app_state["event"] = f"Storm engine error: {error}"


threading.Thread(
    target=engine_thread,
    daemon=True,
).start()

from web_server import run_web_app

run_web_app(
    command_queue,
    settings_lock,
    storm_settings,
    app_state_lock,
    app_state,
)
