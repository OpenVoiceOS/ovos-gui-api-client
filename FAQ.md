
# FAQ — `ovos-gui-api-client`

## What is `ovos-gui-api-client`?
`ovos-gui-api-client` is Template-based GUI interface for OpenVoiceOS skills.

## How do I install it?
```bash
pip install ovos-gui-api-client
```
Or for development:
```bash
uv pip install -e .
```

## Where do I report bugs?
Open an issue on the GitHub repository. Ensure you are targeting the `dev` branch for fixes.

## How do I run tests?
```bash
uv run pytest test/ --cov=ovos_gui_api_client
```

## How do I contribute?
1. Fork the repository and create a feature branch from `dev`.
2. Write tests for your changes.
3. Open a PR targeting the `dev` branch.
4. Ensure CI passes before requesting review.

## How does OCP update the media player display?
OCPMediaPlayer calls `GUIInterface.show_media_player()` with `now_playing`, `playlist`, `search_results`, and `state`. The method sets the `ocp_*` session keys and calls `_show_page(PageTemplates.MEDIA_PLAYER, ...)`. Individual backend plugins handle video/web rendering separately via `show_video_player()` or `show_url()`.

## What Python versions are supported?
See `QUICK_FACTS.md` — currently `>=3.9`.
