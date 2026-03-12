"""
OVOS GUI API Client
===================

This module provides the public interface for OVOS skills and plugins to
interact with the GUI layer.

Design contract
---------------
* Skills may ONLY display pre-defined page templates (see `PageTemplates`).
* All session data set via ``gui[key] = value`` is synced to the GUI service
  in real time and made available to the active display layer.
* A single `GUIInterface` instance is bound to one skill / namespace.
* The message-bus must be set (via constructor or `set_bus`) before any
  display call is made.

Typical usage inside a skill::

    gui = GUIInterface("my.skill.id", bus=my_bus)
    gui["temperature"] = 22
    gui.show_text("Hello world", title="Greeting")

    # later …
    gui.release()
"""
import base64
import enum
import mimetypes
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from ovos_config import Configuration
from ovos_utils.log import LOG

from ovos_bus_client.message import Message
from ovos_bus_client.util import dig_for_message, get_mycroft_bus


# ---------------------------------------------------------------------------
# Page template registry
# ---------------------------------------------------------------------------

class PageTemplates(str, enum.Enum):
    """Enumeration of all pre-defined GUI page templates.

    Skills and plugins may only display pages from this set.  Custom
    display-layer pages are not supported through this interface by design.

    Attributes:
        IDLE:           Default resting state – reserved for the ovos-gui
                        service itself; skills must not use this directly.
        LOADING:        Generic loading / spinner animation.
        STATUS:         Success or failure result animation.
        ERROR:          Error message with optional detail text.
        TEXT:           Scrollable plain-text view.
        IMAGE:          Static image viewer.
        ANIMATED_IMAGE: Animated GIF/WebP viewer.
        LIST:           Scrollable list of labelled items.
        GRID:           2-D tile grid of image-primary items.
        TABLE:          Columnar data table with named headers.
        HTML:           In-process HTML renderer.
        URL:            Full web-page renderer.
        CLOCK:          Clock / time display (self-updating).
        TIMER:          Countdown / count-up display (self-updating).
        WEATHER:        Weather summary card.
        MAP:            Geographic location view.
        CONFIRM:        Visual accompaniment to a yes/no voice dialogue.
        SELECT:         Visual accompaniment to a choice voice dialogue.
        FACE:           Avatar face (awake / sleeping states).
    """
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
    MEDIA_PLAYER    = "SYSTEM_media_player"
    CLOCK           = "SYSTEM_clock"
    TIMER           = "SYSTEM_timer"
    WEATHER         = "SYSTEM_weather"
    MAP             = "SYSTEM_map"
    CONFIRM         = "SYSTEM_confirm"
    SELECT          = "SYSTEM_select"
    FACE            = "SYSTEM_face"


class FillMode(str, enum.Enum):
    """How an image should be scaled to fit its display area.

    The display layer is responsible for mapping these values to its own
    rendering primitives (e.g. Qt's ``Image.fillMode`` property).

    Attributes:
        FIT:    Scale the image to fit entirely within the area, preserving
                the aspect ratio.  Letterboxing may appear.
        CROP:   Scale the image to fill the area entirely, cropping any
                overflow, preserving the aspect ratio.
        STRETCH: Stretch the image to fill the area exactly, ignoring the
                 aspect ratio.
    """
    FIT     = "fit"
    CROP    = "crop"
    STRETCH = "stretch"


# ---------------------------------------------------------------------------
# Data structures for template payloads
# ---------------------------------------------------------------------------

@dataclass
class ListItem:
    """A single entry in a :attr:`PageTemplates.LIST` page.

    Attributes:
        title:    Primary label (required).
        subtitle: Secondary label shown below the title.
        image:    URL or local path to a thumbnail image.
    """
    title: str
    subtitle: Optional[str] = None
    image: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class GridItem:
    """A single tile in a :attr:`PageTemplates.GRID` page.

    The grid is image-primary: all tiles are equal in visual weight and the
    display layer determines column count based on screen dimensions.

    Attributes:
        image:  URL or local path to the tile image (required).
        title:  Optional label shown below the image.
    """
    image: str
    title: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SelectItem:
    """A single option in a :attr:`PageTemplates.SELECT` dialogue page.

    Attributes:
        label: Human-readable text shown to the user.
        value: Machine-readable value sent back with the touch event.
    """
    label: str
    value: Any

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _GUIDict(dict):
    """A ``dict`` subclass that propagates every mutation to the GUI service.

    This is used automatically when a skill assigns a ``dict`` value to a
    session-data key so that nested key changes are also synced::

        gui["info"] = {"city": "Berlin", "temp": 12}
        gui["info"]["temp"] = 13  # <- triggers sync without extra code
    """

    def __init__(self, gui: "GUIInterface", **kwargs: Any) -> None:
        self._gui = gui
        super().__init__(**kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        if self.get(key) != value:
            super().__setitem__(key, value)
            self._gui._sync_data()

    def update(self, other: Optional[Dict] = None, **kwargs: Any) -> None:  # type: ignore[override]
        """Bulk-update and sync once after all changes are applied."""
        changed = False
        items = dict(other or {}, **kwargs)
        for key, value in items.items():
            if self.get(key) != value:
                super().__setitem__(key, value)
                changed = True
        if changed:
            self._gui._sync_data()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class GUIInterface:
    """Interface between an OVOS skill / plugin and the GUI service.

    Session data set on this object is forwarded to the GUI service and made
    available to the active display layer under each key's name.

    Args:
        skill_id:   Unique identifier for the skill owning this interface.
                    This is also used as the *namespace* in GUI protocol
                    messages.
        bus:        Optional :class:`MessageBusClient`.  When omitted the
                    bus must be supplied later via :meth:`set_bus`.
        config:     Optional GUI configuration dict.  Defaults to the
                    ``[gui]`` section of the global OVOS configuration.

    Example::

        gui = GUIInterface("my.skill.id", bus=bus)
        gui["answer"] = 42
        gui.show_text("The answer is 42")
    """

    def __init__(
        self,
        skill_id: str,
        bus=None,
        config: Optional[Dict] = None,
    ) -> None:
        self._skill_id: str = skill_id
        self._bus = None
        self.config: Dict = config or Configuration().get("gui", {})

        self._session_data: Dict[str, Any] = {}
        self._pages: List[PageTemplates] = []
        self.current_page_idx: int = -1
        self._events: List[tuple] = []
        self._on_gui_changed_callback: Optional[Callable] = None

        if bus:
            self.set_bus(bus)

    # ------------------------------------------------------------------
    # Bus
    # ------------------------------------------------------------------

    def set_bus(self, bus=None) -> None:
        """Attach a message-bus client and register default event handlers.

        Args:
            bus: :class:`MessageBusClient` instance.  Falls back to the
                 shared/global bus when ``None``.
        """
        self._bus = bus or get_mycroft_bus()
        self._setup_default_handlers()

    @property
    def bus(self):
        """The attached :class:`MessageBusClient`, or ``None``."""
        return self._bus

    @bus.setter
    def bus(self, val) -> None:
        self.set_bus(val)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        """Unique identifier / namespace for this interface."""
        return self._skill_id

    @skill_id.setter
    def skill_id(self, val: str) -> None:
        self._skill_id = val

    # ------------------------------------------------------------------
    # GUI availability
    # ------------------------------------------------------------------

    @property
    def gui_disabled(self) -> bool:
        """``True`` when the GUI service is explicitly disabled in config.

        When disabled all display calls are silently no-ops so that the
        same skill code works on headless devices.
        """
        return bool(self.config.get("disable_gui", False))

    # ------------------------------------------------------------------
    # Active pages
    # ------------------------------------------------------------------

    @property
    def page(self) -> Optional[PageTemplates]:
        """The currently active page, or ``None`` when the GUI is idle."""
        if not self._pages or self.current_page_idx >= len(self._pages):
            return None
        return self._pages[self.current_page_idx]

    @property
    def pages(self) -> List[PageTemplates]:
        """All pages currently managed by this interface."""
        return list(self._pages)

    # ------------------------------------------------------------------
    # Dict-like session data access
    # ------------------------------------------------------------------

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a session-data value and sync it to the GUI if a page is active."""
        if self._session_data.get(key) == value:
            return

        if isinstance(value, dict) and not isinstance(value, _GUIDict):
            value = _GUIDict(self, **value)

        self._session_data[key] = value

        if self.page:
            self._sync_data()

    def __getitem__(self, key: str) -> Any:
        return self._session_data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._session_data

    def __len__(self) -> int:
        return len(self._session_data)

    def __repr__(self) -> str:
        return f"GUIInterface(skill_id={self._skill_id!r}, data={self._session_data!r})"

    def get(self, key: str, default: Any = None) -> Any:
        """Return ``self[key]`` or *default* when the key is absent."""
        return self._session_data.get(key, default)

    def keys(self):
        return self._session_data.keys()

    def values(self):
        return self._session_data.values()

    def items(self):
        return self._session_data.items()

    def update(self, data: Dict[str, Any]) -> None:
        """Bulk-set session data and emit a single sync message.

        Prefer this over repeated ``gui[key] = value`` assignments when
        updating several keys at once.

        Args:
            data: Key/value pairs to merge into the session data.
        """
        changed = False
        for key, value in data.items():
            if self._session_data.get(key) != value:
                if isinstance(value, dict) and not isinstance(value, _GUIDict):
                    value = _GUIDict(self, **value)
                self._session_data[key] = value
                changed = True

        if changed and self.page:
            self._sync_data()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _setup_default_handlers(self) -> None:
        """Register built-in message-bus handlers for this namespace."""
        event = f"{self.skill_id}.set"
        self._bus.on(event, self._on_gui_set)
        self._events.append((event, self._on_gui_set))

    def register_handler(self, event: str, handler: Callable) -> None:
        """Register a handler for a GUI-originated event.

        The ``event`` string will be automatically prefixed with
        ``<skill_id>.`` when not already present, matching the convention
        used by the display layer to fire events back to the skill.

        Args:
            event:   Event name (with or without namespace prefix).
            handler: Callable that accepts a single :class:`Message` arg.

        Raises:
            RuntimeError: When no bus has been set.
        """
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")
        if not event.startswith(f"{self.skill_id}."):
            event = f"{self.skill_id}.{event}"
        self._events.append((event, handler))
        self._bus.on(event, handler)

    def set_on_gui_changed(self, callback: Callable) -> None:
        """Register a callback to invoke whenever the display layer changes a session value.

        Args:
            callback: Zero-argument callable.
        """
        self._on_gui_changed_callback = callback

    def _on_gui_set(self, message: Message) -> None:
        """Handle a ``<skill_id>.set`` message from the GUI service.

        The display layer can push value changes back to the skill via this
        channel (e.g. when the user interacts with an input element).
        """
        for key, value in message.data.items():
            # Use dict.__setitem__ directly to avoid double-sync; we sync once
            # after all keys are applied.
            if isinstance(value, dict) and not isinstance(value, _GUIDict):
                value = _GUIDict(self, **value)
            self._session_data[key] = value

        self._sync_data()

        if self._on_gui_changed_callback:
            self._on_gui_changed_callback()

    # ------------------------------------------------------------------
    # Data sync
    # ------------------------------------------------------------------

    def _sync_data(self) -> None:
        """Emit a ``gui.value.set`` message with the current session data.

        No-op when the GUI is disabled or no bus is attached.
        """
        if self.gui_disabled:
            return
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")
        msg = dig_for_message()
        ctx = msg.context if msg else {}
        data = dict(self._session_data, __from=self.skill_id)
        self._bus.emit(Message("gui.value.set", data, ctx))

    # ------------------------------------------------------------------
    # Page management (internal)
    # ------------------------------------------------------------------

    def _show_page(
        self,
        page: PageTemplates,
        override_idle: Union[bool, int, None] = None,
        override_animations: bool = False,
        index: int = 0,
        remove_others: bool = False,
    ) -> None:
        """Show a single page.  Delegates to :meth:`_show_pages`."""
        self._show_pages([page], index, override_idle, override_animations, remove_others)

    def _show_pages(
        self,
        page_names: List[PageTemplates],
        index: int = 0,
        override_idle: Union[bool, int, None] = None,
        override_animations: bool = False,
        remove_others: bool = False,
    ) -> None:
        """Request the GUI service to display one or more pages.

        Args:
            page_names:           Ordered list of pages to show.
            index:                Which page in the list to make active
                                  (0-based).
            override_idle:        ``True`` to take over the idle display
                                  indefinitely; an ``int`` to do so for that
                                  many seconds; ``None`` to use the default
                                  timeout.
            override_animations:  ``True`` to suppress platform animations.
            remove_others:        When ``True``, all pages *not* in
                                  *page_names* are removed first.

        Raises:
            RuntimeError: When no bus has been set.
            ValueError:   When *page_names* is not a list.
        """
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")

        if isinstance(page_names, (str, PageTemplates)):
            page_names = [page_names]
        if not isinstance(page_names, list):
            raise ValueError(f"page_names must be a list, got {type(page_names).__name__}")

        if index >= len(page_names):
            LOG.warning(
                f"index={index} is out of range for page list of length "
                f"{len(page_names)}; clamping to last page."
            )
            index = len(page_names) - 1

        if remove_others:
            self._remove_all_pages(except_pages=page_names)

        self._pages = page_names
        self.current_page_idx = index

        if self.gui_disabled:
            return

        # Sync data first so the page renders with the latest values.
        self._sync_data()

        msg = dig_for_message()
        ctx = msg.context if msg else {}
        self._bus.emit(
            Message(
                "gui.page.show",
                {
                    "page_names": page_names,
                    "index": index,
                    "__from": self.skill_id,
                    "__idle": override_idle,
                    "__animations": override_animations,
                },
                ctx,
            )
        )

    def _remove_page(self, page: PageTemplates) -> None:
        """Remove a single page from the GUI display stack."""
        self._remove_pages([page])

    def _remove_pages(self, page_names: List[PageTemplates]) -> None:
        """Remove specific pages from the GUI display stack.

        Args:
            page_names: Pages to remove.

        Raises:
            RuntimeError: When no bus has been set.
        """
        if self.gui_disabled:
            return
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")
        if isinstance(page_names, (str, PageTemplates)):
            page_names = [page_names]
        if not isinstance(page_names, list):
            raise ValueError(f"page_names must be a list, got {type(page_names).__name__}")

        self._bus.emit(
            Message("gui.page.delete", {"page_names": page_names, "__from": self.skill_id})
        )

    def _remove_all_pages(self, except_pages: Optional[List[PageTemplates]] = None) -> None:
        """Remove all pages managed by this interface.

        Args:
            except_pages: Optional list of pages to keep.
        """
        if self.gui_disabled:
            return
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")
        self._bus.emit(
            Message(
                "gui.page.delete.all",
                {"__from": self.skill_id, "except": except_pages or []},
            )
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all session data and remove all pages from the GUI.

        This resets the interface to its initial state without releasing
        the namespace.  Use :meth:`release` to fully hand back control.
        """
        self._session_data = {}
        self._pages = []
        self.current_page_idx = -1
        if self.gui_disabled:
            return
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")
        self._bus.emit(Message("gui.clear.namespace", {"__from": self.skill_id}))

    def release(self) -> None:
        """Signal that this skill is done with the GUI.

        Clears all session data and pages, then notifies the GUI service so
        that it can return to the idle/resting screen or the previous view.
        """
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")
        self.clear()
        self._bus.emit(Message("ovos.gui.screen.close", {"skill_id": self.skill_id}))

    def shutdown(self) -> None:
        """Shut down this interface and deregister all event handlers.

        Called automatically when the owning skill is unloaded.
        """
        if self._bus:
            self.release()
            for event, handler in self._events:
                self._bus.remove(event, handler)
        self._events.clear()

    # ------------------------------------------------------------------
    # High-level display helpers
    # ------------------------------------------------------------------

    def send_event(
        self,
        event_name: str,
        params: Union[Dict, list, str, int, float, bool, None] = None,
    ) -> None:
        """Trigger a named event in the active display-layer page.

        Args:
            event_name: Name of the event to fire.
            params:     JSON-serialisable payload delivered alongside the
                        event.  Defaults to an empty dict.

        Raises:
            RuntimeError: When no bus has been set.
        """
        if self.gui_disabled:
            return
        if not self._bus:
            raise RuntimeError("Bus not set – call set_bus() or pass bus= to the constructor.")
        self._bus.emit(
            Message(
                "gui.event.send",
                {
                    "__from": self.skill_id,
                    "event_name": event_name,
                    "params": params or {},
                },
            )
        )

    # ------------------------------------------------------------------
    # Template helpers
    # ------------------------------------------------------------------

    def show_face(
        self,
        awake: bool = True,
        override_idle: Union[int, bool] = True,
        override_animations: bool = True,
    ) -> None:
        """Display an avatar face in awake or sleeping state.

        Intended for GUI frontends that render a character/avatar rather
        than a traditional screen layout.

        Args:
            awake:               ``True`` for open eyes, ``False`` for
                                 sleeping / closed eyes.
            override_idle:       ``True`` to hold the display indefinitely;
                                 an ``int`` for a timed override.
            override_animations: ``True`` to suppress platform animations.
        """
        self["sleeping"] = not awake
        self._show_page(PageTemplates.FACE, override_idle, override_animations)

    def show_loading(
        self,
        text: str = "",
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a loading / progress animation with an optional label.

        Args:
            text:                Label shown below the spinner.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["label"] = text
        self._show_page(PageTemplates.LOADING, override_idle, override_animations)

    def show_status(
        self,
        text: str,
        success: bool,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a success or failure result animation.

        Args:
            text:                Message to display.
            success:             ``True`` for success, ``False`` for failure.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["success"] = success
        self["label"] = text
        self._show_page(PageTemplates.STATUS, override_idle, override_animations)

    def show_error(
        self,
        text: str,
        detail: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display an error message.

        Args:
            text:                Primary error message.
            detail:              Optional secondary detail / traceback text.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["label"] = text
        self["detail"] = detail
        self._show_page(PageTemplates.ERROR, override_idle, override_animations)

    def show_text(
        self,
        text: str,
        title: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a scrollable text view.

        Args:
            text:                Body text (auto-paginates for long content).
            title:               Optional heading displayed above the text.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["text"] = text
        self["title"] = title
        self._show_page(PageTemplates.TEXT, override_idle, override_animations)

    def show_image(
        self,
        url: str,
        caption: Optional[str] = None,
        title: Optional[str] = None,
        fill: Optional[FillMode] = None,
        background_color: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
        animated: bool = False,
    ) -> None:
        """Display a static or animated image.

        Accepts a remote URL or a path to a local file.  Local file paths
        must exist at call time.

        Args:
            url:                 HTTP(S) URL or absolute local file path.
            caption:             Caption shown below the image.
            title:               Heading shown above the image.
            fill:                How to scale the image within its display
                                 area (see :class:`FillMode`).  Defaults to
                                 the display layer's own default.
            background_color:    Page background colour as a hex string,
                                 e.g. ``"#000000"``.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
            animated:            Set ``True`` to use the animated-image
                                 template (GIF / WebP).
        """
        if not url.startswith(("http://", "https://", "data:")):
            if not os.path.isfile(url):
                LOG.error(f"Image not found: '{url}'")
                return
            mime, _ = mimetypes.guess_type(url)
            mime = mime or "image/png"
            with open(url, "rb") as f:
                url = f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"

        self["image"] = url
        self["title"] = title
        self["caption"] = caption
        self["fill"] = fill.value if isinstance(fill, FillMode) else fill
        self["background_color"] = background_color

        template = PageTemplates.ANIMATED_IMAGE if animated else PageTemplates.IMAGE
        self._show_page(template, override_idle, override_animations)

    def show_animated_image(
        self,
        url: str,
        caption: Optional[str] = None,
        title: Optional[str] = None,
        fill: Optional[FillMode] = None,
        background_color: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display an animated image (GIF or WebP).

        Convenience wrapper around :meth:`show_image` with ``animated=True``.

        Args:
            url:                 HTTP(S) URL or absolute local file path.
            caption:             Caption shown below the image.
            title:               Heading shown above the image.
            fill:                How to scale the image (see :class:`FillMode`).
            background_color:    Page background colour as a hex string.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self.show_image(
            url, caption, title, fill, background_color,
            override_idle, override_animations, animated=True,
        )

    def show_html(
        self,
        html: str,
        resource_url: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Render an HTML string in the GUI.

        Args:
            html:                Raw HTML content to display.
            resource_url:        Base URL used to resolve relative resource
                                 references inside the HTML.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["html"] = html
        self["resource_url"] = resource_url
        self._show_page(PageTemplates.HTML, override_idle, override_animations)

    def show_url(
        self,
        url: str,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Open a URL in the GUI's web renderer.

        Args:
            url:                 Fully-qualified URL to load.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["url"] = url
        self._show_page(PageTemplates.URL, override_idle, override_animations)

    def show_weather(
        self,
        current_temp: Union[int, float],
        min_temp: Union[int, float],
        max_temp: Union[int, float],
        condition: str,
        icon: Optional[str] = None,
        location: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a weather summary card.

        Args:
            current_temp:        Current temperature value.
            min_temp:            Daily low temperature.
            max_temp:            Daily high temperature.
            condition:           Human-readable weather condition label
                                 (e.g. ``"Partly cloudy"``).
            icon:                Optional URL or path to a weather icon.
            location:            Optional location name to display.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["current_temp"] = current_temp
        self["min_temp"] = min_temp
        self["max_temp"] = max_temp
        self["condition"] = condition
        self["icon"] = icon
        self["location"] = location
        self._show_page(PageTemplates.WEATHER, override_idle, override_animations)

    def show_list(
        self,
        items: List[Union[ListItem, Dict[str, Any]]],
        title: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a scrollable list of items.

        Each item must have at least a ``title``.  An optional ``subtitle``
        and ``image`` thumbnail are also supported.

        Args:
            items:               List of :class:`ListItem` instances or plain
                                 dicts with at minimum a ``"title"`` key.
            title:               Optional heading for the list page.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        serialised = [
            i.as_dict() if isinstance(i, ListItem) else i
            for i in items
        ]
        self["title"] = title
        self["items"] = serialised
        self._show_page(PageTemplates.LIST, override_idle, override_animations)

    def show_grid(
        self,
        items: List[Union[GridItem, Dict[str, Any]]],
        title: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a 2-D tile grid of image-primary items.

        Unlike :meth:`show_list`, items in a grid carry no inherent hierarchy.
        They are visually equal-weight tiles; the display layer decides the
        column count based on the screen size.  Use a grid for content where
        the image is the primary identifier — album covers, photo libraries,
        skill icons.

        Args:
            items:               List of :class:`GridItem` instances or plain
                                 dicts with at minimum an ``"image"`` key.
            title:               Optional heading for the grid page.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        serialised = [
            i.as_dict() if isinstance(i, GridItem) else i
            for i in items
        ]
        self["title"] = title
        self["items"] = serialised
        self._show_page(PageTemplates.GRID, override_idle, override_animations)

    def show_table(
        self,
        columns: List[str],
        rows: List[List[Any]],
        title: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a columnar data table with named headers.

        Use a table for relational or comparative data where column identity
        is meaningful — schedules, scores, comparisons, prices.  Each row
        must have the same number of values as there are columns.

        Args:
            columns:             Ordered list of column header strings.
            rows:                List of rows; each row is an ordered list of
                                 values aligned to *columns*.  Values must be
                                 JSON-serialisable.
            title:               Optional heading for the table page.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).

        Raises:
            ValueError: When any row length does not match the column count.
        """
        col_count = len(columns)
        for i, row in enumerate(rows):
            if len(row) != col_count:
                raise ValueError(
                    f"Row {i} has {len(row)} value(s) but there are "
                    f"{col_count} column(s)."
                )
        self["title"] = title
        self["columns"] = columns
        self["rows"] = rows
        self._show_page(PageTemplates.TABLE, override_idle, override_animations)

    def show_media_player(
        self,
        now_playing: Optional[Dict[str, Any]] = None,
        playlist: Optional[List[Dict[str, Any]]] = None,
        search_results: Optional[List[Dict[str, Any]]] = None,
        state: str = "playing",
        override_idle: Union[int, bool, None] = True,
        override_animations: bool = False,
    ) -> None:
        """Display the OCP media player UI: now-playing metadata, playlist queue,
        and search results in a single unified surface.

        Args:
            now_playing: Current track metadata dict with keys:
                title, artist, album, image (URL or data: URI),
                uri, position (ms), duration (ms; -1 for live streams).
            playlist: Ordered queue. Each item: {title, artist, image, uri, duration}.
            search_results: Search hits. Each item:
                {title, artist, image, uri, skill_id, match_confidence}.
            state: One of "playing", "paused", "stopped", "loading", "error".
            override_idle: How long to keep the display (True=persistent, int=seconds).
            override_animations: Skip transition animations if True.
        """
        np = now_playing or {}
        self["ocp_title"] = np.get("title", "")
        self["ocp_artist"] = np.get("artist", "")
        self["ocp_album"] = np.get("album", "")
        self["ocp_image"] = np.get("image", "")
        self["ocp_uri"] = np.get("uri", "")
        self["ocp_position"] = int(np.get("position", 0))
        self["ocp_duration"] = int(np.get("duration", -1))
        self["ocp_playback_state"] = state
        self["ocp_playlist"] = playlist or []
        self["ocp_search_results"] = search_results or []
        # index of current track in playlist
        uri = np.get("uri", "")
        playlist_uris = [item.get("uri", "") for item in (playlist or [])]
        self["ocp_playlist_position"] = playlist_uris.index(uri) if uri in playlist_uris else 0
        self._show_page(PageTemplates.MEDIA_PLAYER, override_idle, override_animations)

    def show_clock(
        self,
        override_idle: Union[int, bool, None] = True,
        override_animations: bool = False,
    ) -> None:
        """Display the clock / time page.

        The clock page is self-updating on the display layer; no session data
        is required.

        Args:
            override_idle:       Idle override (see :meth:`_show_pages`).
                                 Defaults to ``True`` (hold indefinitely).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self._show_page(PageTemplates.CLOCK, override_idle, override_animations)

    def show_timer(
        self,
        end_time: float,
        label: Optional[str] = None,
        count_up: bool = False,
        override_idle: Union[int, bool, None] = True,
        override_animations: bool = False,
    ) -> None:
        """Display a countdown or count-up timer.

        The display layer is responsible for updating the displayed time; it
        derives the remaining/elapsed duration from ``end_time`` and the
        device clock, so no polling from the skill is needed.

        Args:
            end_time:            Unix timestamp (seconds since epoch) at which
                                 the timer expires.  Use
                                 ``time.time() + seconds`` to set a countdown.
            label:               Optional label shown alongside the timer
                                 (e.g. ``"Pasta"``).
            count_up:            ``False`` (default) counts down to zero;
                                 ``True`` counts up from zero (stopwatch mode,
                                 where ``end_time`` is the start time).
            override_idle:       Idle override (see :meth:`_show_pages`).
                                 Defaults to ``True`` (hold until dismissed).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["end_time"] = end_time
        self["label"] = label
        self["count_up"] = count_up
        self._show_page(PageTemplates.TIMER, override_idle, override_animations)

    def show_map(
        self,
        latitude: float,
        longitude: float,
        zoom: int = 12,
        label: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a geographic location on a map.

        The display layer is responsible for choosing the map provider and
        rendering strategy.

        Args:
            latitude:            WGS-84 latitude in decimal degrees.
            longitude:           WGS-84 longitude in decimal degrees.
            zoom:                Map zoom level (1 = whole world,
                                 20 = building detail).  Default 12.
            label:               Optional place name or annotation shown on
                                 the map.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["latitude"] = latitude
        self["longitude"] = longitude
        self["zoom"] = zoom
        self["label"] = label
        self._show_page(PageTemplates.MAP, override_idle, override_animations)

    def show_confirm(
        self,
        question: str,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a yes/no confirmation page alongside a voice dialogue.

        OVOS is voice-first.  This method only provides a visual accompaniment
        to a spoken question that the skill must ask concurrently.  On
        display-only devices the voice response is the only available path.

        A touch shortcut (if supported by the display layer) fires:
        ``<skill_id>.confirm.response`` with ``{"confirmed": bool}``.

        The skill is responsible for registering a handler for that event
        *and* for the spoken yes/no response, and must not block waiting
        exclusively for a GUI event.

        Args:
            question:            The question being spoken to the user.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        self["question"] = question
        self._show_page(PageTemplates.CONFIRM, override_idle, override_animations)

    def show_select(
        self,
        items: List[Union[SelectItem, Dict[str, Any]]],
        prompt: Optional[str] = None,
        override_idle: Union[int, bool, None] = None,
        override_animations: bool = False,
    ) -> None:
        """Display a list of options alongside a voice choice dialogue.

        OVOS is voice-first.  This method only provides a visual accompaniment
        to spoken options that the skill must present concurrently.  On
        display-only devices the voice response is the only available path.

        A touch shortcut (if supported by the display layer) fires:
        ``<skill_id>.select.response`` with ``{"value": <selected value>}``.

        The skill is responsible for registering a handler for that event
        *and* for the spoken selection, and must not block waiting exclusively
        for a GUI event.

        Args:
            items:               Ordered list of :class:`SelectItem` instances
                                 or plain dicts with ``"label"`` and
                                 ``"value"`` keys.
            prompt:              Optional spoken prompt echoed on screen.
            override_idle:       Idle override (see :meth:`_show_pages`).
            override_animations: Animation override (see :meth:`_show_pages`).
        """
        serialised = [
            i.as_dict() if isinstance(i, SelectItem) else i
            for i in items
        ]
        self["prompt"] = prompt
        self["items"] = serialised
        self._show_page(PageTemplates.SELECT, override_idle, override_animations)
