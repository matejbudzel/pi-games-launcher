"""INI configuration for the appliance; compatible with older Python versions."""
from configparser import ConfigParser
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
    if not parser.read(str(path), encoding="utf-8"):
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
    return Settings(tuple(providers), general.get("tty", "/dev/tty1"),
                    general.get("display_cec", "0").lower() in ("1", "true", "yes"),
                    general.get("confirm_key", "SPACE").upper(), general.get("up_key", "UP").upper(),
                    general.get("down_key", "DOWN").upper())
