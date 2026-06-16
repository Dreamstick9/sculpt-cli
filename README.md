# sculpt

> **Free CLI for image→3D and text→3D via Hugging Face Spaces. Zero GPU, zero cost, zero accounts.**

```
$ sculpt generate shoe.png
↪ Detected: image input, 1024×768
↪ Routing to: SF3D (fastest, healthy)
↪ Queue position: 3 of 8 (~25s)
↪ (waking up the model — 12s)
↪ (running inference — 0.4s)
↪ Extracting GLB (2s)
✅ Saved to ./outputs/shoe__sf3d.glb (3.8 MB)
```

```
$ sculpt generate --prompt "a low-poly stone castle on a cliff at sunset"
↪ Detected: text-only prompt
↪ Stage 1: text → image (FLUX.1-schnell)
↪ Queue position: 6 of 15 (~40s)
↪ Stage 2: image → 3D (SF3D)
↪ Queue position: 2 of 4 (~15s)
✅ Saved to ./outputs/castle__two_stage.glb (4.2 MB)
```

---

## Why sculpt?

| Problem | sculpt |
|---|---|
| Commercial APIs charge per generation / monthly | **Free** — uses public HF Spaces |
| Open weights need GPU + Docker + env setup | **Zero setup** — `pip install sculpt3d` |
| Single model = single point of failure | **Auto-fallback** across 6 models |
| Queue times are a mystery | **Honest queue UI** — position + ETA |
| Re-generating same input wastes time | **Content-addressed cache** — instant repeat |

---

## Quickstart

```bash
# Install
pip install sculpt3d

# Generate from image
sculpt generate photo.png

# Generate from text
sculpt generate --prompt "a ceramic mug with floral pattern"

# List models
sculpt models

# Health check
sculpt doctor
```

---

## Supported Models

| Model | Speed | Quality | Best For | License |
|---|---|---|---|---|
| **SF3D** (Stable Fast 3D) | ⚡⚡⚡ <1s | Good | Default, batch, real-time | Stability Community |
| **TRELLIS.2** (Microsoft) | ⚡⚡ ~17s | Excellent (PBR) | Production assets, game-ready | MIT |
| **Hi3DGen** (ByteDance) | ⚡⚡ | Excellent (geometry) | Architecture, mechanical parts | MIT |
| **TRELLIS-text** (Microsoft) | ⚡⚡ | Good | Direct text→3D | MIT |
| **TripoSR** | ⚡⚡⚡ <1s | Fair | Fallback, low VRAM | MIT |
| **Two-Stage** (FLUX→3D) | ⚡⚡ | High | High-quality text→3D | MIT (FLUX) + MIT |

> **Note:** Hunyuan3D-2.1 is intentionally excluded — its Space is paused and weights are non-commercial.

---

## Commands

```bash
# Generate from image
sculpt generate photo.png [--model sf3d|trellis2|hi3dgen|triposr|auto]

# Generate from text
sculpt generate --prompt "a red sports car" [--pipeline 1stage|2stage]

# Batch process
sculpt generate --batch ./photos/ --delay 15 --resume

# Model management
sculpt models              # list all models + health
sculpt models use sf3d     # set default

# Utilities
sculpt doctor              # health check all models
sculpt auth <hf_token>     # optional: for private Spaces
sculpt cache stats         # cache hit rate
sculpt cache purge         # clear cache

sculpt show-config         # show current config
```

---

## How It Works

1. **You run** `sculpt generate photo.png`
2. **Auto-router picks** best model based on input + flags + live queue
3. **gradio_client** submits to Hugging Face Space API
4. **Live queue UI** shows position + ETA ("Position 4 of 12 — ~60s")
5. **Inference runs** on HF's GPUs (Microsoft/Stability/ByteDance pay)
6. **Downloads .glb immediately** before temp URL expires
7. **Saves to ./outputs/** with content-addressed cache

---

## Architecture

```
sculpt/
├── cli.py              # Click commands
├── router.py           # Auto-model picker (the brain)
├── adapters/           # Per-model Gradio clients
│   ├── sf3d.py         # stabilityai/stable-fast-3d
│   ├── trellis2.py     # microsoft/TRELLIS.2
│   ├── hi3dgen.py      # Stable-X/Hi3DGen
│   ├── trellis_text.py # JeffreyXiang/TRELLIS (text)
│   ├── triposr.py      # stabilityai/TripoSR (fallback)
│   └── two_stage.py    # FLUX → SF3D/TRELLIS.2
├── reliability/        # Production hardening
│   ├── breaker.py      # Circuit breakers (5 failures → skip)
│   ├── limiter.py      # Token buckets per Space
│   ├── health.py       # Probes + queue estimates
│   └── retry.py        # Exponential backoff (1s/5s/25s)
├── cache/              # Content-addressed SQLite
├── config.py           # ~/.sculpt/config.json
├── output.py           # Idempotent save + cache keys
└── ui.py               # Rich progress + honest queue UI
```

---

## License

MIT — free for personal and commercial use.

**Third-party model licenses:** See [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)

| Model | License |
|---|---|
| TRELLIS.2 | MIT |
| TRELLIS (orig) | MIT |
| SF3D | Stability Community License (free < $1M revenue) |
| Hi3DGen | MIT |
| TripoSR | MIT |
| TripoSG | MIT |

> We intentionally exclude Hunyuan3D-2.1 (non-commercial) and Step1X-3D (paused Space).

---

## Contributing

```bash
git clone https://github.com/Dreamstick9/sculpt-cli
cd sculpt-cli
pip install -e .[dev]
pre-commit install

# Run tests
pytest tests/
python scripts/smoke_test.py
```

---

## Credits

Built by **Kushagar Garg (dreamstrict)** with ♡

Models by: Microsoft Research, Stability AI, ByteDance (CUHKSZ + ByteDance GAP Lab), VAST-AI Research, Tripo AI.

Powered by Hugging Face Spaces + `gradio_client`.



___
---

*Free forever. No API keys. No accounts. Just 3D.*
