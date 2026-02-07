# faster-whisper-demo

Kleine Reflex-Webapp zur Live-Transkription von Mikrofon-Chunks mit `faster-whisper`.

## Start (uv)

```bash
cd faster_whisper_demo
uv sync
uv run reflex run
```

Wenn du bereits eine aktive `.venv` verwenden willst:

```bash
uv sync --active
uv run --active reflex run
```

## Optionale Konfiguration

- `FASTER_WHISPER_MODEL` (Default: `base`)
- `FASTER_WHISPER_DEVICE` (Default: `cpu`)
- `FASTER_WHISPER_COMPUTE_TYPE` (Default: `int8`)
- `FASTER_WHISPER_LANGUAGE` (Default: `de`)
