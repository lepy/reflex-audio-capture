# reflex-audio-capture

Cross-browser audio capture using audio-recorder-polyfill.

This component is highly experimental.

## Requirements

- Python 3.11+
- Reflex 0.6.6+

## Installation

```bash
pip install reflex-audio-capture
```

## Usage

```python
import reflex as rx
from reflex_audio_capture import AudioRecorderPolyfill


class State(rx.State):
    @rx.event
    def on_data_available(self, chunk: str):
        # chunk is a base64 data URI
        print(chunk)

    @rx.event
    def on_error(self, error: str):
        print(error)


capture = AudioRecorderPolyfill.create(
    id="mic",
    on_data_available=State.on_data_available,
    on_error=State.on_error,
    timeslice=1000,
    device_id="",
    use_mp3=True,
)


def index() -> rx.Component:
    return rx.vstack(
        capture,
        rx.button("Start", on_click=capture.start()),
        rx.button("Stop", on_click=capture.stop()),
        rx.text(capture.recorder_state),
    )
```

## Component API

- Props:
  - `on_data_available(data: str)`: receives recorded audio as data URI.
  - `on_error(error: str)`: receives browser/recording errors.
  - `on_start()`, `on_stop()`: optional lifecycle callbacks.
  - `timeslice: int`: chunk interval in ms (`0` means deliver on stop).
  - `device_id: str`: optional `audioinput` device id.
  - `use_mp3: bool`: enable MP3 encoder (`True` by default).
- Methods:
  - `capture.start()`
  - `capture.stop()`
- State-like vars:
  - `capture.is_recording`
  - `capture.recorder_state`
  - `capture.media_devices`

## Demo Transcription Backends

The demo app supports two transcription backends via environment variables:

- `WHISPER_BACKEND=openai` (default)
- `WHISPER_BACKEND=faster-whisper`

You can also switch the backend directly in the demo UI via the backend selector.

Optional tuning variables:

- `OPENAI_WHISPER_MODEL` (default: `whisper-1`)
- `FASTER_WHISPER_MODEL` (default: `base`)
- `FASTER_WHISPER_DEVICE` (default: `cpu`)
- `FASTER_WHISPER_COMPUTE_TYPE` (default: `int8`)

For a full app example, see `audio_capture_demo/`.
