
# Skill Integration Guide

This page describes how OVOS skills use `GUIInterface` from
`ovos-gui-api-client`.

---

## Import patterns

### In `ovos-workshop` skills (recommended)

Skills that extend `OVOSSkill` (from `ovos-workshop`) already have a
`self.gui` attribute of type `GUIInterface`. The attribute is created by
`ovos-workshop`'s base class, which imports `GUIInterface` from this
package. No manual instantiation is needed.

```python
from ovos_workshop.skills.ovos import OVOSSkill

class MySkill(OVOSSkill):
    def handle_show_info(self, message):
        self.gui.show_text("Hello from my skill", title="Greeting")
```

### Standalone usage (plugins, tests)

```python
from ovos_gui_api_client import GUIInterface

gui = GUIInterface("my.skill.id", bus=my_bus)
gui["temperature"] = 22
gui.show_text("Hello world", title="Greeting")
# later…
gui.release()
```

The bus can also be supplied after construction:

```python
gui = GUIInterface("my.skill.id")
# … later, after the bus is available …
gui.set_bus(bus)
```

---

## Session data

Session data is the key/value store that the display layer reads to render
a page. Write to it with dict-style syntax; reads are also dict-style.

```python
self.gui["answer"] = 42
self.gui["unit"] = "°C"
```

Every write immediately emits `gui.value.set` on the message bus. To batch
multiple updates into a single sync message, use `update()`:

```python
self.gui.update({
    "current_temp": 14,
    "min_temp": 9,
    "max_temp": 18,
    "condition": "Partly cloudy",
})
```

When a `dict` value is assigned it is wrapped in `_GUIDict`
(`ovos_gui_api_client/__init__.py:188`), which propagates nested mutations
automatically:

```python
self.gui["forecast"] = {"day": "Monday", "temp": 12}
self.gui["forecast"]["temp"] = 13  # also syncs to the GUI
```

---

## Displaying content

Call a `show_*` method after setting any session data. The method sets its
own session keys and calls `_show_pages()`, which:

1. Calls `_sync_data()` to push the current session state.
2. Emits `gui.page.show` with the template name.

```python
# Minimal text page
self.gui.show_text("The sky is blue")

# With title and a timed hold
self.gui.show_text("The sky is blue", title="Sky colour", override_idle=30)

# Weather card
self.gui.show_weather(
    current_temp=14,
    min_temp=9,
    max_temp=18,
    condition="Partly cloudy",
    icon="https://cdn.example.com/icons/partly_cloudy.png",
    location="London",
)
```

See [`page-templates.md`](page-templates.md) for the complete method
reference.

---

## Local image files

`show_image()` accepts an absolute local file path. The client
automatically reads the file, detects its MIME type via `mimetypes`, and
encodes it as a `data:` URI before placing it in session data. Display
adapters therefore receive a self-contained value and do not need access
to the skill's filesystem.

```python
import os

logo = os.path.join(self.root_dir, "res", "img", "logo.png")
self.gui.show_image(logo, title="Welcome")
```

If the file does not exist at call time, `show_image()` logs an error and
returns without displaying anything.

---

## `override_idle`

Every `show_*` method accepts `override_idle`:

| Value | Behaviour |
|---|---|
| `None` (default on most methods) | Use the platform's default timeout |
| `True` | Hold the display indefinitely |
| `int` | Hold for that many seconds, then return to idle |

Some methods default to `True` (e.g. `show_clock()`, `show_timer()`,
`show_audio_player()`, `show_video_player()`) because those views are
meant to remain on screen until explicitly dismissed.

---

## Session context propagation

`dig_for_message()` from `ovos_bus_client.util` is called inside both
`_sync_data()` and `_show_pages()`. It walks the current Python call stack
looking for a `Message` object. When the skill is executing inside a bus
handler (the normal case), the original message's `context` — which
carries `session_id` and `site_id` — is forwarded automatically in every
`gui.value.set` and `gui.page.show` message.

This means the `ovos-gui` namespace manager can route each display call to
the correct physical screen without any skill code changes. Skills do not
need to pass session context explicitly.

```
Skill handler  (has Message with session_id="abc123", site_id="kitchen")
  └─ self.gui.show_text("Recipe step 2")
       └─ dig_for_message()  →  recovers the session context
       └─ gui.page.show  {context: {session_id: "abc123", site_id: "kitchen"}}
                                │
                    ovos-gui routes to the "kitchen" display
```

---

## Registering GUI event handlers

The display layer can fire events back to the skill (e.g. when the user
touches a button). Use `register_handler()`:

```python
# Within skill __init__ or initialize():
self.gui.register_handler("action.triggered", self.handle_gui_action)
```

`register_handler()` automatically prefixes the event with `<skill_id>.`
if not already present, so the full event name on the bus is
`my.skill.id.action.triggered`.

For dialogue templates, the display layer fires standardised events:

| Template | Touch event | Payload |
|---|---|---|
| `show_confirm()` | `<skill_id>.confirm.response` | `{"confirmed": bool}` |
| `show_select()` | `<skill_id>.select.response` | `{"value": <selected value>}` |

The skill **must** also listen for the spoken answer in parallel. Do not
block waiting exclusively for a GUI event.

---

## Reacting to display-layer value pushes

The display layer can push value changes back to the skill via
`<skill_id>.set`. Register a zero-argument callback with
`set_on_gui_changed()`:

```python
self.gui.set_on_gui_changed(self.on_gui_changed)

def on_gui_changed(self):
    LOG.debug(f"GUI changed: {dict(self.gui.items())}")
```

---

## Lifecycle management

| Call | When to use |
|---|---|
| `self.gui.clear()` | Clear session data and remove all pages, but keep the namespace |
| `self.gui.release()` | Done with the GUI — returns to idle or homescreen |
| `self.gui.shutdown()` | Called automatically by `ovos-workshop` when the skill is unloaded |

---

## Headless devices

When `disable_gui: true` is set in the `[gui]` section of
`mycroft.conf`, `gui.gui_disabled` returns `True` and all display calls
are silent no-ops. Skills can therefore use the same code on both headed
and headless devices without conditional checks.

---

## Complete skill example

```python
import time
from ovos_workshop.skills.ovos import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_gui_api_client import ListItem


class TimerSkill(OVOSSkill):

    def initialize(self):
        self._timers = {}

    @intent_handler("set.timer.intent")
    def handle_set_timer(self, message):
        duration = 300  # 5 minutes in seconds
        label = message.data.get("label", "Timer")
        end = time.time() + duration

        self._timers[label] = end
        self.speak(f"Setting a {label} timer for 5 minutes.")
        self.gui.show_timer(end_time=end, label=label)

    @intent_handler("list.timers.intent")
    def handle_list_timers(self, message):
        if not self._timers:
            self.speak("You have no active timers.")
            return
        items = [
            ListItem(name, subtitle=f"{max(0, int(end - time.time()))}s remaining")
            for name, end in self._timers.items()
        ]
        self.gui.show_list(items, title="Active Timers")
        self.speak(f"You have {len(items)} active timer(s).")

    def shutdown(self):
        self.gui.release()
        super().shutdown()
```
