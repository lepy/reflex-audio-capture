from __future__ import annotations

import asyncio
import os
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.request import urlopen

import reflex as rx
from reflex_audio_capture import AudioRecorderPolyfill, get_codec, strip_codec_part

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover
    WhisperModel = None

MODEL_NAME = os.getenv("FASTER_WHISPER_MODEL", "base")
MODEL_DEVICE = os.getenv("FASTER_WHISPER_DEVICE", "cpu")
MODEL_COMPUTE_TYPE = os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "int8")
MODEL_LANGUAGE = os.getenv("FASTER_WHISPER_LANGUAGE", "de")

_model: Any = None


def get_model() -> WhisperModel:
    global _model
    if WhisperModel is None:
        raise RuntimeError(
            "faster-whisper ist nicht installiert. Bitte `uv sync` im Ordner "
            "`faster_whisper_demo` ausfuehren.",
        )
    if _model is None:
        _model = WhisperModel(
            MODEL_NAME,
            device=MODEL_DEVICE,
            compute_type=MODEL_COMPUTE_TYPE,
        )
    return _model


def transcribe_bytes(audio_bytes: bytes, suffix: str) -> str:
    model = get_model()
    with NamedTemporaryFile(suffix=suffix, delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_path = temp_audio.name
    try:
        segments, _ = model.transcribe(
            temp_path,
            language=MODEL_LANGUAGE or None,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


class State(rx.State):
    """Demo state for local faster-whisper STT."""

    processing: bool = False
    has_error: bool = False
    error_message: str = ""
    transcript: list[str] = []
    timeslice: int = 2500

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
                self.has_error = False
                self.error_message = ""
            text = await asyncio.to_thread(
                transcribe_bytes,
                audio_bytes,
                "." + audio_type,
            )
            if text:
                async with self:
                    self.transcript.append(text)
        except Exception as err:
            async with self:
                self.has_error = True
                self.error_message = str(err)
            yield recorder.stop()
        finally:
            async with self:
                self.processing = False

    @rx.event
    def on_error(self, err: dict):
        self.has_error = True
        self.error_message = str(err)

    @rx.event
    def set_timeslice(self, value: list[int | float]):
        self.timeslice = int(value[0])

    @rx.event
    def clear_transcript(self):
        self.transcript = []


recorder = AudioRecorderPolyfill.create(
    id="faster_whisper_recorder",
    on_data_available=State.on_data_available,
    on_error=State.on_error,
    timeslice=State.timeslice,
    use_mp3=True,
)


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Faster-Whisper Mikrofon STT", size="6"),
            rx.text(
                f"Model: {MODEL_NAME} | Device: {MODEL_DEVICE} | Compute: {MODEL_COMPUTE_TYPE}",
                color="gray",
                size="2",
            ),
            rx.card(
                rx.vstack(
                    rx.text(f"Chunk-Intervall: {State.timeslice} ms"),
                    rx.slider(
                        min=500,
                        max=10000,
                        step=500,
                        value=[State.timeslice],
                        on_change=State.set_timeslice,
                    ),
                    rx.text(f"Recorder: {recorder.recorder_state}"),
                    rx.hstack(
                        rx.cond(
                            recorder.is_recording,
                            rx.button("Stop", on_click=recorder.stop(), color_scheme="red"),
                            rx.button(
                                "Start",
                                on_click=recorder.start(),
                                color_scheme="green",
                            ),
                        ),
                        rx.spinner(loading=State.processing),
                        align="center",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.cond(
                State.has_error,
                rx.box(
                    rx.text(State.error_message, color="red"),
                    border="1px solid",
                    border_color="red",
                    border_radius="8px",
                    padding="10px",
                    width="100%",
                ),
            ),
            rx.card(
                rx.hstack(
                    rx.heading("Transkript", size="4"),
                    rx.spacer(),
                    rx.button("Leeren", on_click=State.clear_transcript),
                    align="center",
                    width="100%",
                ),
                rx.divider(),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(State.transcript, lambda line: rx.text(line)),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    type="always",
                    scrollbars="vertical",
                    style={"height": "45vh", "width": "100%"},
                ),
                width="100%",
            ),
            recorder,
            width="100%",
            spacing="4",
        ),
        size="2",
        margin_y="2em",
    )


app = rx.App()
app.add_page(index)
