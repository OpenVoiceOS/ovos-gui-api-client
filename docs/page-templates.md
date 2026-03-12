
# Page Templates — Complete Reference

This page documents every `show_*` method on `GUIInterface`
(`ovos_gui_api_client/__init__.py`) and the `PageTemplates` enum members
they map to.

---

## `PageTemplates` enum

```python
class PageTemplates(str, enum.Enum):
    IDLE            = "SYSTEM_idle"
    LOADING         = "SYSTEM_loading"
    STATUS          = "SYSTEM_status"
    ERROR           = "SYSTEM_error"
    TEXT            = "SYSTEM_text"
    IMAGE           = "SYSTEM_image"
    ANIMATED_IMAGE  = "SYSTEM_animated_image"
    LIST            = "SYSTEM_list"
    GRID            = "SYSTEM_grid"
    TABLE           = "SYSTEM_table"
    HTML            = "SYSTEM_html"
    URL             = "SYSTEM_url"
    AUDIO_PLAYER    = "SYSTEM_audio_player"
    VIDEO_PLAYER    = "SYSTEM_video_player"
    CLOCK           = "SYSTEM_clock"
    TIMER           = "SYSTEM_timer"
    WEATHER         = "SYSTEM_weather"
    MAP             = "SYSTEM_map"
    CONFIRM         = "SYSTEM_confirm"
    SELECT          = "SYSTEM_select"
    FACE            = "SYSTEM_face"
    OCP_NOW_PLAYING = "SYSTEM_ocp_now_playing"
    OCP_SEARCH      = "SYSTEM_ocp_search"
    OCP_PLAYLIST    = "SYSTEM_ocp_playlist"
```

`IDLE` is reserved — the `ovos-gui` service manages it; skills must not
call it directly. All other templates are available to skills.

---

## Common parameters

Every `show_*` method accepts these two trailing parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `override_idle` | `bool \| int \| None` | varies | `True` = hold the display indefinitely; `int` = hold for that many seconds; `None` = use the platform timeout |
| `override_animations` | `bool` | `False` | When `True` suppresses the platform's page-transition animations |

---

## System group

### `show_loading()`

Displays a loading / spinner animation with an optional label.

```python
def show_loading(
    text: str = "",
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | `""` | Label shown below the spinner |

**Session data set:** `label`

**Template:** `SYSTEM_loading`

**Example:**
```python
gui.show_loading("Fetching weather data…")
```

---

### `show_status()`

Displays a success or failure result animation.

```python
def show_status(
    text: str,
    success: bool,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | Message to display |
| `success` | `bool` | required | `True` for success, `False` for failure |

**Session data set:** `label`, `success`

**Template:** `SYSTEM_status`

**Example:**
```python
gui.show_status("Timer set!", success=True)
gui.show_status("Failed to connect", success=False)
```

---

### `show_error()`

Displays an error message with an optional detail string.

```python
def show_error(
    text: str,
    detail: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | Primary error message |
| `detail` | `str \| None` | `None` | Optional secondary detail text or traceback excerpt |

**Session data set:** `label`, `detail`

**Template:** `SYSTEM_error`

**Example:**
```python
gui.show_error("Service unavailable", detail="HTTP 503 from api.example.com")
```

---

## Content group

### `show_text()`

Displays a scrollable plain-text view, auto-paginated for long content.

```python
def show_text(
    text: str,
    title: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | Body text |
| `title` | `str \| None` | `None` | Optional heading shown above the text |

**Session data set:** `text`, `title`

**Template:** `SYSTEM_text`

**Example:**
```python
gui.show_text(
    "The Battle of Hastings was fought on 14 October 1066…",
    title="Battle of Hastings"
)
```

---

### `show_image()`

Displays a static or animated image. Accepts a remote URL or an absolute
local file path. Local files are automatically base64-encoded into a
`data:` URI so adapters receive a self-contained value without needing
access to the skill's filesystem.

```python
def show_image(
    url: str,
    caption: Optional[str] = None,
    title: Optional[str] = None,
    fill: Optional[FillMode] = None,
    background_color: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
    animated: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | required | HTTP(S) URL, absolute local file path, or `data:` URI |
| `caption` | `str \| None` | `None` | Caption shown below the image |
| `title` | `str \| None` | `None` | Heading shown above the image |
| `fill` | `FillMode \| None` | `None` | How to scale the image; see `FillMode` below |
| `background_color` | `str \| None` | `None` | Page background as a hex string, e.g. `"#000000"` |
| `animated` | `bool` | `False` | When `True`, uses `SYSTEM_animated_image` instead |

**Session data set:** `image`, `title`, `caption`, `fill`, `background_color`

**Template:** `SYSTEM_image` (or `SYSTEM_animated_image` when `animated=True`)

**`FillMode` values:**

| Value | String | Behaviour |
|---|---|---|
| `FillMode.FIT` | `"fit"` | Scale to fit within the area; letterboxing may appear |
| `FillMode.CROP` | `"crop"` | Scale to fill, cropping overflow; aspect ratio preserved |
| `FillMode.STRETCH` | `"stretch"` | Stretch to fill exactly, ignoring aspect ratio |

**Example:**
```python
from ovos_gui_api_client import FillMode

gui.show_image(
    "https://example.com/photo.jpg",
    title="Eiffel Tower",
    caption="Paris, France",
    fill=FillMode.CROP,
)

# Local file — automatically base64-encoded
gui.show_image(
    f"{self.root_dir}/res/logo.png",
    title="Logo",
)
```

---

### `show_animated_image()`

Convenience wrapper around `show_image(animated=True)` for GIF or WebP files.

```python
def show_animated_image(
    url: str,
    caption: Optional[str] = None,
    title: Optional[str] = None,
    fill: Optional[FillMode] = None,
    background_color: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

Parameters are identical to `show_image()` except `animated` is not
exposed (it is always `True`).

**Template:** `SYSTEM_animated_image`

---

### `show_html()`

Renders an HTML string inside the GUI.

```python
def show_html(
    html: str,
    resource_url: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `html` | `str` | required | Raw HTML string to render |
| `resource_url` | `str \| None` | `None` | Base URL used to resolve relative resources (images, CSS) inside the HTML |

**Session data set:** `html`, `resource_url`

**Template:** `SYSTEM_html`

**Example:**
```python
gui.show_html(
    "<h1>Hello</h1><p>World</p>",
    resource_url="https://cdn.example.com/",
)
```

---

### `show_url()`

Opens a URL in the GUI's full web renderer.

```python
def show_url(
    url: str,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | required | Fully-qualified URL to load |

**Session data set:** `url`

**Template:** `SYSTEM_url`

**Example:**
```python
gui.show_url("https://openweathermap.org/city/2643743")
```

---

### `show_list()`

Displays a scrollable list of labelled items. Each item has a required
title, and optional subtitle and thumbnail image.

```python
def show_list(
    items: List[Union[ListItem, Dict[str, Any]]],
    title: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `items` | `List[ListItem \| dict]` | required | List entries; each must have at minimum a `"title"` key |
| `title` | `str \| None` | `None` | Optional heading for the list page |

**`ListItem` dataclass:**

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | `str` | yes | Primary label |
| `subtitle` | `str \| None` | no | Secondary label below the title |
| `image` | `str \| None` | no | URL or path to a thumbnail image |

**Session data set:** `items` (serialised list of dicts), `title`

**Template:** `SYSTEM_list`

**Example:**
```python
from ovos_gui_api_client import ListItem

gui.show_list(
    items=[
        ListItem("Morning alarm", subtitle="07:30", image="/icons/alarm.png"),
        ListItem("Pasta timer", subtitle="12 minutes remaining"),
    ],
    title="Active alarms",
)
```

---

### `show_grid()`

Displays a 2-D tile grid of image-primary items. The display layer
determines column count based on screen size.

```python
def show_grid(
    items: List[Union[GridItem, Dict[str, Any]]],
    title: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `items` | `List[GridItem \| dict]` | required | Grid tiles; each must have at minimum an `"image"` key |
| `title` | `str \| None` | `None` | Optional heading for the grid page |

**`GridItem` dataclass:**

| Field | Type | Required | Description |
|---|---|---|---|
| `image` | `str` | yes | URL or path to the tile image |
| `title` | `str \| None` | no | Optional label shown below the image |

**Session data set:** `items` (serialised list of dicts), `title`

**Template:** `SYSTEM_grid`

**Example:**
```python
from ovos_gui_api_client import GridItem

gui.show_grid(
    items=[
        GridItem("https://example.com/album1.jpg", title="Abbey Road"),
        GridItem("https://example.com/album2.jpg", title="Dark Side"),
    ],
    title="Recent albums",
)
```

---

### `show_table()`

Displays a columnar data table with named headers. Each row must have the
same number of values as there are columns.

```python
def show_table(
    columns: List[str],
    rows: List[List[Any]],
    title: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `columns` | `List[str]` | required | Ordered list of column header strings |
| `rows` | `List[List[Any]]` | required | Rows; each row is a list of values aligned to `columns` |
| `title` | `str \| None` | `None` | Optional heading for the table page |

Raises `ValueError` when any row length does not match the column count.

**Session data set:** `columns`, `rows`, `title`

**Template:** `SYSTEM_table`

**Example:**
```python
gui.show_table(
    columns=["City", "Temp", "Condition"],
    rows=[
        ["Berlin", "8°C", "Cloudy"],
        ["London", "12°C", "Rain"],
        ["Madrid", "22°C", "Sunny"],
    ],
    title="Europe weather",
)
```

---

## Media group

### `show_audio_player()`

Displays a now-playing card for audio playback. The actual audio is
managed by the audio service; this call only updates the visual layer.
Call again on track changes or pause/resume to keep the display in sync.

```python
def show_audio_player(
    title: str,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    image: Optional[str] = None,
    position: float = 0.0,
    duration: float = 0.0,
    playing: bool = True,
    override_idle: Union[int, bool, None] = True,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | required | Track title |
| `artist` | `str \| None` | `None` | Artist name |
| `album` | `str \| None` | `None` | Album name |
| `image` | `str \| None` | `None` | URL or path to album art |
| `position` | `float` | `0.0` | Current playback position in seconds |
| `duration` | `float` | `0.0` | Total track duration in seconds; `0` = unknown / streaming |
| `playing` | `bool` | `True` | `True` if currently playing, `False` if paused |

`override_idle` defaults to `True` (hold display while playing).

**Session data set:** `title`, `artist`, `album`, `image`, `position`, `duration`, `playing`

**Template:** `SYSTEM_audio_player`

**Example:**
```python
gui.show_audio_player(
    title="Comfortably Numb",
    artist="Pink Floyd",
    album="The Wall",
    image="https://example.com/wall.jpg",
    position=45.2,
    duration=382.0,
    playing=True,
)
```

---

### `show_video_player()`

Displays an embedded video playback surface. Unlike `show_audio_player`,
the display layer is responsible for rendering the video stream.

```python
def show_video_player(
    uri: str,
    title: Optional[str] = None,
    playing: bool = True,
    override_idle: Union[int, bool, None] = True,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `uri` | `str` | required | URI of the video stream or file to play |
| `title` | `str \| None` | `None` | Optional title overlay |
| `playing` | `bool` | `True` | `True` to start playing immediately |

`override_idle` defaults to `True`.

**Session data set:** `uri`, `title`, `playing`

**Template:** `SYSTEM_video_player`

**Example:**
```python
gui.show_video_player(
    uri="https://example.com/news.mp4",
    title="Evening news",
)
```

---

## Utility group

### `show_clock()`

Displays the clock / time page. The display layer updates the time
autonomously; no session data is required.

```python
def show_clock(
    override_idle: Union[int, bool, None] = True,
    override_animations: bool = False,
) -> None
```

`override_idle` defaults to `True` (hold indefinitely).

**Session data set:** none

**Template:** `SYSTEM_clock`

**Example:**
```python
gui.show_clock()
```

---

### `show_timer()`

Displays a countdown or count-up timer. The display layer derives the
remaining/elapsed time from `end_time` and the device clock; the skill
does not need to update it every second.

```python
def show_timer(
    end_time: float,
    label: Optional[str] = None,
    count_up: bool = False,
    override_idle: Union[int, bool, None] = True,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `end_time` | `float` | required | Unix timestamp (seconds since epoch) when the timer expires. Use `time.time() + seconds` for a countdown. |
| `label` | `str \| None` | `None` | Optional label shown alongside the timer (e.g. `"Pasta"`) |
| `count_up` | `bool` | `False` | `False` = countdown to zero; `True` = count up from zero (stopwatch, where `end_time` is the start time) |

`override_idle` defaults to `True`.

**Session data set:** `end_time`, `label`, `count_up`

**Template:** `SYSTEM_timer`

**Example:**
```python
import time

# 10-minute pasta countdown
gui.show_timer(
    end_time=time.time() + 600,
    label="Pasta",
)
```

---

### `show_weather()`

Displays a weather summary card.

```python
def show_weather(
    current_temp: Union[int, float],
    min_temp: Union[int, float],
    max_temp: Union[int, float],
    condition: str,
    icon: Optional[str] = None,
    location: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `current_temp` | `int \| float` | required | Current temperature value |
| `min_temp` | `int \| float` | required | Daily low temperature |
| `max_temp` | `int \| float` | required | Daily high temperature |
| `condition` | `str` | required | Human-readable condition label (e.g. `"Partly cloudy"`) |
| `icon` | `str \| None` | `None` | Optional URL or path to a weather icon |
| `location` | `str \| None` | `None` | Optional location name |

**Session data set:** `current_temp`, `min_temp`, `max_temp`, `condition`, `icon`, `location`

**Template:** `SYSTEM_weather`

**Example:**
```python
gui.show_weather(
    current_temp=14,
    min_temp=9,
    max_temp=18,
    condition="Partly cloudy",
    icon="https://example.com/icons/partly_cloudy.png",
    location="Berlin",
)
```

---

### `show_map()`

Displays a geographic location on a map. The display layer chooses the
map provider and rendering strategy.

```python
def show_map(
    latitude: float,
    longitude: float,
    zoom: int = 12,
    label: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `latitude` | `float` | required | WGS-84 latitude in decimal degrees |
| `longitude` | `float` | required | WGS-84 longitude in decimal degrees |
| `zoom` | `int` | `12` | Map zoom level (1 = whole world, 20 = building detail) |
| `label` | `str \| None` | `None` | Optional place name or annotation |

**Session data set:** `latitude`, `longitude`, `zoom`, `label`

**Template:** `SYSTEM_map`

**Example:**
```python
gui.show_map(latitude=52.5200, longitude=13.4050, label="Berlin")
```

---

## Avatar group

### `show_face()`

Displays an avatar face in awake or sleeping state. Intended for devices
that render a character/avatar rather than a traditional screen layout.

```python
def show_face(
    awake: bool = True,
    override_idle: Union[int, bool] = True,
    override_animations: bool = True,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `awake` | `bool` | `True` | `True` for open eyes, `False` for sleeping |

`override_idle` and `override_animations` both default to `True`.

**Session data set:** `sleeping` (the inverse of `awake`)

**Template:** `SYSTEM_face`

**Example:**
```python
gui.show_face(awake=True)   # wake up the avatar
gui.show_face(awake=False)  # avatar goes to sleep
```

---

## Dialogue group (voice-first)

These templates provide a **visual accompaniment** to an active voice
dialogue. OVOS is voice-first: touch is a shortcut for capable devices,
but voice must always be the primary path. The skill must never block
waiting exclusively for a GUI event.

### `show_confirm()`

Displays a yes/no confirmation page alongside a spoken question.

A touch shortcut (if the display layer supports it) fires:
`<skill_id>.confirm.response` with `{"confirmed": bool}`.

```python
def show_confirm(
    question: str,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `question` | `str` | required | The question being spoken to the user |

**Session data set:** `question`

**Template:** `SYSTEM_confirm`

**Example:**
```python
# The skill must ask via speech AND show the confirm page simultaneously.
self.speak("Do you want to delete all alarms?")
gui.show_confirm("Do you want to delete all alarms?")
# Register both voice and GUI handlers:
gui.register_handler("confirm.response", self.handle_confirm_response)
```

---

### `show_select()`

Displays a list of named options alongside a spoken choice dialogue.

A touch shortcut (if the display layer supports it) fires:
`<skill_id>.select.response` with `{"value": <selected value>}`.

```python
def show_select(
    items: List[Union[SelectItem, Dict[str, Any]]],
    prompt: Optional[str] = None,
    override_idle: Union[int, bool, None] = None,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `items` | `List[SelectItem \| dict]` | required | Options; each must have `"label"` and `"value"` keys |
| `prompt` | `str \| None` | `None` | Optional spoken prompt echoed on screen |

**`SelectItem` dataclass:**

| Field | Type | Description |
|---|---|---|
| `label` | `str` | Human-readable text shown to the user |
| `value` | `Any` | Machine-readable value sent back with the touch event |

**Session data set:** `items` (serialised list of dicts), `prompt`

**Template:** `SYSTEM_select`

**Example:**
```python
from ovos_gui_api_client import SelectItem

options = [
    SelectItem("Celsius", "celsius"),
    SelectItem("Fahrenheit", "fahrenheit"),
    SelectItem("Kelvin", "kelvin"),
]
self.speak("Which temperature unit do you prefer? Celsius, Fahrenheit, or Kelvin?")
gui.show_select(options, prompt="Choose a temperature unit")
gui.register_handler("select.response", self.handle_unit_selection)
```

---

## OCP media service group

These three templates are used by the OVOS Common Play (OCP) service and
OCP-aware skills. They carry richer media state than the generic
`show_audio_player()` / `show_video_player()` methods.

### `show_ocp_now_playing()`

Displays the OCP now-playing view with full player state for any media type.

```python
def show_ocp_now_playing(
    title: str,
    artist: Optional[str] = None,
    image: Optional[str] = None,
    bg_image: Optional[str] = None,
    uri: Optional[str] = None,
    media_type: str = "audio",
    position: float = 0.0,
    duration: float = 0.0,
    playing: bool = True,
    can_prev: bool = True,
    can_next: bool = True,
    loop_status: str = "None",
    shuffle: bool = False,
    javascript: Optional[str] = None,
    override_idle: Union[int, bool, None] = True,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | required | Track / page title |
| `artist` | `str \| None` | `None` | Artist or channel name (audio) |
| `image` | `str \| None` | `None` | Album-art URL or file path (audio) |
| `bg_image` | `str \| None` | `None` | Background image URL or file path |
| `uri` | `str \| None` | `None` | Stream URI (video / web; also carried for audio) |
| `media_type` | `str` | `"audio"` | One of `"audio"`, `"video"`, `"web"` |
| `position` | `float` | `0.0` | Current playback position in milliseconds |
| `duration` | `float` | `0.0` | Total duration in milliseconds (0 = streaming) |
| `playing` | `bool` | `True` | `True` if currently playing |
| `can_prev` | `bool` | `True` | Whether skipping to previous track is available |
| `can_next` | `bool` | `True` | Whether skipping to next track is available |
| `loop_status` | `str` | `"None"` | One of `"None"`, `"RepeatTrack"`, `"Repeat"` |
| `shuffle` | `bool` | `False` | Whether shuffle mode is active |
| `javascript` | `str \| None` | `None` | JS snippet to inject after page load (web type only) |

**Template:** `SYSTEM_ocp_now_playing`

---

### `show_ocp_search()`

Displays the OCP search-results view. Pass an empty `results` list to show
the OCP browser / featured skills (home state).

```python
def show_ocp_search(
    results: Optional[List[Dict]] = None,
    search_term: Optional[str] = None,
    skill_cards: Optional[List[Dict]] = None,
    override_idle: Union[int, bool, None] = True,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `results` | `List[dict] \| None` | `None` → `[]` | Ranked media candidates. Each entry needs at minimum `title`, `artist`, `image`, `duration` (ms), `source` (skill icon URL), `uri` |
| `search_term` | `str \| None` | `None` → `""` | The query that produced these results |
| `skill_cards` | `List[dict] \| None` | `None` → `[]` | Featured OCP skill cards for the home state. Each entry has `skill_id`, `title`, `image`, `media_type` |

**Template:** `SYSTEM_ocp_search`

---

### `show_ocp_playlist()`

Displays the OCP playlist (ordered queue of tracks).

```python
def show_ocp_playlist(
    tracks: Optional[List[Dict]] = None,
    current_index: int = 0,
    override_idle: Union[int, bool, None] = True,
    override_animations: bool = False,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tracks` | `List[dict] \| None` | `None` → `[]` | Ordered track list. Each entry needs at minimum `title`, `artist`, `image`, `duration` (ms) |
| `current_index` | `int` | `0` | Index of the currently playing track (0-based) |

**Template:** `SYSTEM_ocp_playlist`

---

## Excluded templates

The following were deliberately not included in `PageTemplates`:

| Rejected | Reason |
|---|---|
| `SYSTEM_slideshow` | Compose by calling `show_image()` at successive indices |
| `SYSTEM_notification` | System-layer concept, not a skill page |
| `SYSTEM_qr_code` | Renderable as `show_image()`; QR generation belongs in the skill |
| `SYSTEM_chart` / `SYSTEM_graph` | Too display-layer-specific; use `show_html()` or `show_image()` |
| `SYSTEM_input` | Free-text keyboard entry breaks the voice-first contract and does not work on display-only devices |
| Per-skill templates | Violates the "multiple unrelated skills" rule |
