
# `ovos-gui-api-client` — Documentation Index

> Template-based GUI interface for OpenVoiceOS skills

## What it is

`ovos-gui-api-client` is the **skill-side GUI API** for OVOS. It provides
two public classes:

- `GUIInterface` — the object a skill uses to display content and manage
  session data.
- `PageTemplates` — an enum of the 25 pre-defined page templates a skill
  may display.

Skills never write QML, HTML, or any renderer-specific code. They call
typed helper methods such as `gui.show_text(...)` or `gui.show_weather(...)`
and the display layer (whatever GUI adapter is loaded — Qt, PyHTMX, or a
future renderer) decides how to present it.

## Why it exists

Before this package, skills imported `GUIInterface` from
`ovos_bus_client.apis.gui`. That class referenced QML page file names
directly, coupling every skill to the Qt renderer. The introduction of
`ovos-gui-plugin-pyhtmx` and the broader `opm.gui_adapter` plug-in
architecture required a renderer-agnostic API.

`ovos-gui-api-client` provides that API. Skills import from here; the
display adapters (loaded by `ovos-gui`) receive the resulting bus messages
and handle rendering independently.

`ovos-workshop` re-exports `GUIInterface` from this package so existing
skills that use `self.gui` continue to work without code changes.

## Architecture position

```text
Skill code
  └─ GUIInterface (this package)
       ├─ gui.value.set  →  ovos-gui / NamespaceManager
       └─ gui.page.show  →  ovos-gui / NamespaceManager
                                  └─ opm.gui_adapter plugins
                                        ├─ ovos-legacy-mycroft-gui-plugin  (Qt5)
                                        └─ ovos-gui-plugin-pyhtmx           (Web)
```

Session context (`session_id`, `site_id`) is propagated automatically via
`dig_for_message()` from `ovos_bus_client.util`. This means the GUI service
can route each display call to the correct screen without any skill code
changes.

## Key design constraints

- Skills may **only** display pages from `PageTemplates`. Custom page names
  are not supported by design.
- The GUI is a voice-first *companion*. Touch is a shortcut; it must never
  be the only way to interact.
- Skills must never block waiting for a GUI event. Spoken answers and touch
  shortcuts fire the same bus message; the skill listens for both in
  parallel.
- On headless devices `gui.gui_disabled` returns `True` and all display
  calls are silent no-ops.

## Package metadata

| Field | Value |
|---|---|
| Package name | `ovos-gui-api-client` |
| Module | `ovos_gui_api_client` |
| Entry file | `ovos_gui_api_client/__init__.py` |
| Python requirement | `>=3.9` |
| Key dependencies | `ovos-bus-client>=1.3.8a1`, `ovos-config>=0.0.12`, `ovos-utils>=0.7.0` |
| Repository | https://github.com/OpenVoiceOS/ovos-gui-api-client |

## Public API summary

### Classes

| Class | Purpose |
|---|---|
| `GUIInterface` | Skill-facing GUI object; manages session data and page display |
| `PageTemplates` | Enum of all allowed page template identifiers |
| `FillMode` | Enum for image scaling modes (`FIT`, `CROP`, `STRETCH`) |
| `ListItem` | Dataclass for an item in a `show_list()` call |
| `GridItem` | Dataclass for a tile in a `show_grid()` call |
| `SelectItem` | Dataclass for an option in a `show_select()` call |

### `GUIInterface` — constructor

```python
GUIInterface(
    skill_id: str,
    bus=None,
    config: Optional[Dict] = None,
)
```

`skill_id` becomes both the skill namespace in all bus messages and the
prefix for GUI-originated event names. `bus` may be supplied later via
`set_bus()`.

### `GUIInterface` — session data

`GUIInterface` behaves like a `dict` for session data. Every write
automatically emits `gui.value.set` to the GUI service.

```python
gui["temperature"] = 22          # single key
gui.update({"temp": 22, "unit": "C"})   # bulk write — single sync message
value = gui["temperature"]       # read back
```

When a `dict` is assigned it is wrapped in `_GUIDict`, which propagates
nested mutations automatically.

### `GUIInterface` — display methods (show_*)

All 21 template show-methods plus 4 OCP-specific methods are described in
full in [`page-templates.md`](page-templates.md).

| Method | Template used |
|---|---|
| `show_face()` | `SYSTEM_face` |
| `show_loading()` | `SYSTEM_loading` |
| `show_status()` | `SYSTEM_status` |
| `show_error()` | `SYSTEM_error` |
| `show_text()` | `SYSTEM_text` |
| `show_image()` | `SYSTEM_image` or `SYSTEM_animated_image` |
| `show_animated_image()` | `SYSTEM_animated_image` |
| `show_html()` | `SYSTEM_html` |
| `show_url()` | `SYSTEM_url` |
| `show_weather()` | `SYSTEM_weather` |
| `show_list()` | `SYSTEM_list` |
| `show_grid()` | `SYSTEM_grid` |
| `show_table()` | `SYSTEM_table` |
| `show_media_player()` | `SYSTEM_media_player` |
| `show_clock()` | `SYSTEM_clock` |
| `show_timer()` | `SYSTEM_timer` |
| `show_map()` | `SYSTEM_map` |
| `show_confirm()` | `SYSTEM_confirm` |
| `show_select()` | `SYSTEM_select` |

### `GUIInterface` — lifecycle

| Method | Description |
|---|---|
| `set_bus(bus)` | Attach a bus client and register default event handlers |
| `register_handler(event, handler)` | Register a handler for a GUI-originated event |
| `set_on_gui_changed(callback)` | Callback fired when the display layer pushes a value update |
| `send_event(event_name, params)` | Trigger a named event in the active display-layer page |
| `clear()` | Clear session data and pages without releasing the namespace |
| `release()` | Signal that this skill is done — returns to idle/homescreen |
| `shutdown()` | Deregister all handlers; called when skill unloads |

### `GUIInterface` — properties

| Property | Type | Description |
|---|---|---|
| `skill_id` | `str` | Namespace identifier for this interface |
| `bus` | `MessageBusClient \| None` | Attached bus client |
| `gui_disabled` | `bool` | `True` when GUI is disabled in config |
| `page` | `PageTemplates \| None` | Currently active page |
| `pages` | `List[PageTemplates]` | All pages managed by this interface |

## Bus messages emitted

| Message type | When emitted |
|---|---|
| `gui.value.set` | On every session-data change |
| `gui.page.show` | On every `show_*()` call |
| `gui.page.delete` | When pages are removed |
| `gui.page.delete.all` | When all pages are cleared |
| `gui.clear.namespace` | On `clear()` |
| `ovos.gui.screen.close` | On `release()` |
| `gui.event.send` | On `send_event()` |

## Bus messages received

| Message type | Handler |
|---|---|
| `<skill_id>.set` | `_on_gui_set` — display layer pushes value changes back |

## Cross-references

| Component | Role |
|---|---|
| `ovos-gui` (`ovos_gui/namespace.py`) | Receives `gui.page.show` and `gui.value.set`; routes to adapters |
| `ovos-workshop` (`ovos_workshop/skills/ovos.py`) | Re-exports `GUIInterface` from this package |
| `ovos-plugin-manager` (`ovos_plugin_manager/templates/gui.py`) | Defines `AbstractGUIPlugin` that adapters implement |
| `ovos-gui-plugin-pyhtmx` | Web-based GUI adapter consuming these messages |
| `ovos-legacy-mycroft-gui-plugin` | Qt5-based GUI adapter consuming these messages |

## Documentation pages

| Page | Content |
|---|---|
| [`page-templates.md`](page-templates.md) | All 25 template methods with full parameter tables |
| [`skill-integration.md`](skill-integration.md) | How skills import and use `GUIInterface` |

## EnclosureAPI

`EnclosureAPI` is exported alongside `GUIInterface` so a skill obtains both
`self.gui` and `self.enclosure` from this one package. It is the producer side
of the legacy hardware-enclosure protocol (the `enclosure.*` bus messages —
eyes, mouth/faceplate, system LEDs); hardware GUI adapters consume it, the
Mark-1 enclosure being the reference renderer.

```python
from ovos_gui_api_client import GUIInterface, EnclosureAPI

gui = GUIInterface("my.skill", bus=bus)
enclosure = EnclosureAPI(bus=bus, skill_id="my.skill")
enclosure.eyes_color(0, 255, 0)
```
