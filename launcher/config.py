"""INI configuration for the appliance; compatible with older Python versions."""
from configparser import ConfigParser, Error as ConfigError
from dataclasses import dataclass, field
from pathlib import Path
import shlex


@dataclass(frozen=True)
class Provider:
    id: str
    manifest_command: tuple
    hooks: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    providers: tuple
    tty: str = "/dev/tty1"
    display_cec: bool = False
    confirm_key: str = "SPACE"
    up_key: str = "UP"
    down_key: str = "DOWN"
    audio_volume_percent: int = 96
    last_selected_item: str = ""


def _command(value, section, key):
    try:
        command = tuple(shlex.split(value))
    except ValueError as exc:
        raise ValueError("%s.%s has invalid quoting" % (section, key)) from exc
    if not command:
        raise ValueError("%s.%s must not be empty" % (section, key))
    return command


def load(path):
    parser = ConfigParser(interpolation=None)
    try:
        loaded = parser.read(str(path), encoding="utf-8")
    except (ConfigError, OSError, UnicodeError) as exc:
        raise ValueError("configuration cannot be read: %s" % exc) from exc
    if not loaded:
        raise ValueError("configuration file is missing: %s" % path)
    providers = []
    for section in parser.sections():
        if not section.startswith("provider "):
            continue
        provider_id = section[len("provider "):].strip()
        if not provider_id or any(ch.isspace() for ch in provider_id):
            raise ValueError("provider section has invalid id: %s" % section)
        if not parser.has_option(section, "manifest_command"):
            raise ValueError("%s.manifest_command is required" % section)
        hooks = {key[5:].replace("_", "-"): _command(value, section, key)
                 for key, value in parser.items(section) if key.startswith("hook_")}
        providers.append(Provider(provider_id, _command(parser.get(section, "manifest_command"), section, "manifest_command"), hooks))
    if len({item.id for item in providers}) != len(providers):
        raise ValueError("provider IDs must be unique")
    general = parser["launcher"] if parser.has_section("launcher") else {}
    try:
        volume = max(0, min(100, int(general.get("audio_volume_percent", "96"))))
    except ValueError:
        volume = 96
    return Settings(tuple(providers), general.get("tty", "/dev/tty1"),
                    general.get("display_cec", "0").lower() in ("1", "true", "yes"),
                    general.get("confirm_key", "SPACE").upper(), general.get("up_key", "UP").upper(),
                    general.get("down_key", "DOWN").upper(), volume,
                    general.get("last_selected_item", ""))


def save_launcher_value(path, key, value):
    """Update one [launcher] value without rewriting user comments or providers."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else ["[launcher]"]
    start = next((index for index, line in enumerate(lines) if line.strip().lower() == "[launcher]"), None)
    if start is None:
        lines = ["[launcher]", "%s=%s" % (key, value), ""] + lines
    else:
        end = next((index for index in range(start + 1, len(lines)) if lines[index].strip().startswith("[")), len(lines))
        for index in range(start + 1, end):
            if lines[index].strip().startswith(key + "="):
                lines[index] = "%s=%s" % (key, value)
                break
        else:
            lines.insert(end, "%s=%s" % (key, value))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
