from __future__ import annotations

import asyncio
import os
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

import reflex as rx
from reflex_audio_capture import AudioRecorderPolyfill, get_codec, strip_codec_part
from reflex_intersection_observer import intersection_observer

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover
    WhisperModel = None

WHISPER_BACKEND = os.getenv("WHISPER_BACKEND", "openai").strip().lower()
OPENAI_WHISPER_MODEL = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
FASTER_WHISPER_MODEL = os.getenv("FASTER_WHISPER_MODEL", "base")
FASTER_WHISPER_DEVICE = os.getenv("FASTER_WHISPER_DEVICE", "cpu")
FASTER_WHISPER_COMPUTE_TYPE = os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "int8")

openai_client = AsyncOpenAI() if AsyncOpenAI is not None else None
faster_whisper_model: WhisperModel | None = None

REF = "myaudio"


def get_backend_error(backend: str) -> str:
    if backend == "openai" and openai_client is None:
        return "Backend 'openai' ist aktiv, aber das Paket 'openai' ist nicht installiert."
    if backend == "faster-whisper" and WhisperModel is None:
        return (
            "Backend 'faster-whisper' ist aktiv, aber das Paket "
            "'faster-whisper' ist nicht installiert."
        )
    if backend not in {"openai", "faster-whisper"}:
        return "Unbekanntes Backend. Erlaubt sind 'openai' und 'faster-whisper'."
    return ""


def get_faster_whisper_model() -> WhisperModel:
    global faster_whisper_model
    if WhisperModel is None:
        raise RuntimeError(
            "faster-whisper backend requested, but package is not installed.",
        )
    if faster_whisper_model is None:
        faster_whisper_model = WhisperModel(
            FASTER_WHISPER_MODEL,
            device=FASTER_WHISPER_DEVICE,
            compute_type=FASTER_WHISPER_COMPUTE_TYPE,
        )
    return faster_whisper_model


def transcribe_with_faster_whisper(audio_bytes: bytes, suffix: str) -> str:
    model = get_faster_whisper_model()
    with NamedTemporaryFile(suffix=suffix, delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_path = temp_audio.name
    try:
        segments, _ = model.transcribe(temp_path)
        return " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


class State(rx.State):
    """The app state."""

    has_error: bool = False
    processing: bool = False
    transcript: list[str] = []
    timeslice: int = 0
    device_id: str = ""
    use_mp3: bool = True
    whisper_backend: str = WHISPER_BACKEND
    backend_error: str = get_backend_error(WHISPER_BACKEND)

    @rx.event(background=True)
    async def on_data_available(self, chunk: str):
        mime_type = get_codec(chunk)
        audio_type = mime_type.partition("/")[2]
        if audio_type == "mpeg":
            audio_type = "mp3"
        with urlopen(strip_codec_part(chunk)) as audio_data:
            audio_bytes = audio_data.read()
            try:
                async with self:
                    self.processing = True
                backend = self.whisper_backend
                backend_error = get_backend_error(backend)
                if backend_error:
                    raise RuntimeError(backend_error)
                if backend == "faster-whisper":
                    transcription_text = await asyncio.to_thread(
                        transcribe_with_faster_whisper,
                        audio_bytes,
                        "." + audio_type,
                    )
                elif backend == "openai":
                    if openai_client is None:
                        raise RuntimeError(
                            "openai backend requested, but package is not installed.",
                        )
                    transcription = await openai_client.audio.transcriptions.create(
                        model=OPENAI_WHISPER_MODEL,
                        file=("temp." + audio_type, audio_bytes, mime_type),
                    )
                    transcription_text = transcription.text
                else:
                    raise ValueError(
                        "Unsupported WHISPER_BACKEND value. Use 'openai' or"
                        " 'faster-whisper'.",
                    )
            except Exception:
                async with self:
                    self.has_error = True
                    self.backend_error = get_backend_error(self.whisper_backend)
                yield capture.stop()
                raise
            finally:
                async with self:
                    self.processing = False
            async with self:
                self.transcript.append(transcription_text)

    @rx.event
    def set_transcript(self, value: list[str]):
        self.transcript = value

    @rx.event
    def set_timeslice(self, value: list[int | float]):
        self.timeslice = int(value[0])

    @rx.event
    def set_device_id(self, value: str):
        self.device_id = value
        yield capture.stop()

    @rx.event
    def set_whisper_backend(self, value: str):
        self.whisper_backend = value.strip().lower()
        self.backend_error = get_backend_error(self.whisper_backend)

    @rx.event
    def on_error(self, err):
        print(err)  # noqa: T201

    @rx.event
    def on_load(self):
        # We can start the recording immediately when the page loads
        return capture.start()


capture = AudioRecorderPolyfill.create(
    id=REF,
    on_data_available=State.on_data_available,
    on_error=State.on_error,
    timeslice=State.timeslice,
    device_id=State.device_id,
    use_mp3=State.use_mp3,
)


def input_device_select() -> rx.Component:
    return rx.select.root(
        rx.select.trigger(placeholder="Select Input Device"),
        rx.select.content(
            rx.foreach(
                capture.media_devices,
                lambda device: rx.cond(
                    device.deviceId & device.kind == "audioinput",
                    rx.select.item(device.label, value=device.deviceId),
                ),
            ),
        ),
        on_change=State.set_device_id,
    )


def transcript() -> rx.Component:
    return rx.scroll_area(
        rx.vstack(
            rx.foreach(State.transcript, rx.text),
            intersection_observer(
                height="1px",
                id="end-of-transcript",
                root="#scroller",
                # Remove lambda after reflex-dev/reflex#4552
                on_non_intersect=lambda _: rx.scroll_to("end-of-transcript"),
                visibility="hidden",
            ),
        ),
        id="scroller",
        width="100%",
        height="50vh",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Whisper Demo"),
            rx.hstack(
                rx.text("Backend"),
                rx.select(
                    ["openai", "faster-whisper"],
                    value=State.whisper_backend,
                    on_change=State.set_whisper_backend,
                    width="220px",
                ),
                align="center",
                spacing="2",
            ),
            rx.cond(
                State.backend_error,
                rx.box(
                    rx.text(State.backend_error, color="orange"),
                    border="1px solid",
                    border_color="orange",
                    border_radius="8px",
                    padding="10px",
                ),
            ),
            rx.card(
                rx.vstack(
                    f"Timeslice: {State.timeslice} ms",
                    rx.slider(
                        min=0,
                        max=10000,
                        value=[State.timeslice],
                        on_change=State.set_timeslice,
                    ),
                    rx.cond(
                        capture.media_devices,
                        input_device_select(),
                    ),
                ),
            ),
            capture,
            rx.text(f"Recorder Status: {capture.recorder_state}"),
            rx.cond(
                capture.is_recording,
                rx.button("Stop Recording", on_click=capture.stop()),
                rx.button(
                    "Start Recording",
                    on_click=capture.start(),
                ),
            ),
            rx.card(
                rx.hstack(
                    rx.text("Transcript"),
                    rx.spinner(loading=State.processing),
                    rx.spacer(),
                    rx.icon_button(
                        "trash-2",
                        on_click=State.set_transcript([]),
                        margin_bottom="4px",
                    ),
                    align="center",
                ),
                rx.divider(),
                transcript(),
            ),
            style=rx.Style({"width": "100%", "> *": {"width": "100%"}}),
        ),
        size="2",
        margin_y="2em",
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)
