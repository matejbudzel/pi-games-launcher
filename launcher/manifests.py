"""Provider manifest validation and fault-isolated collection."""
from dataclasses import dataclass
import json
import logging
import subprocess

LOG = logging.getLogger(__name__)
MANIFEST_VERSION = 1


@dataclass(frozen=True)
class Game:
    provider_id: str
    id: str
    title: str
    command: tuple
    testing_tool: bool = False

    @property
    def key(self):
        return "%s:%s" % (self.provider_id, self.id)


def parse(provider_id, text):
    try:
        document = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("not valid JSON") from exc
    if not isinstance(document, dict) or document.get("version") != MANIFEST_VERSION:
        raise ValueError("unsupported or missing manifest version")
    items = document.get("games")
    if not isinstance(items, list):
        raise ValueError("games must be an array")
    games, ids = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("game entry must be an object")
        game_id, title, command = item.get("id"), item.get("title"), item.get("command")
        testing_tool = item.get("testing_tool", False)
        if not isinstance(game_id, str) or not game_id or not isinstance(title, str) or not title:
            raise ValueError("game id and title must be non-empty strings")
        if game_id in ids:
            raise ValueError("duplicate game id: %s" % game_id)
        if not isinstance(command, list) or not command or not all(isinstance(arg, str) and arg for arg in command):
            raise ValueError("game command must be a non-empty string array")
        if not isinstance(testing_tool, bool):
            raise ValueError("testing_tool must be a boolean")
        ids.add(game_id); games.append(Game(provider_id, game_id, title, tuple(command), testing_tool))
    return games


def collect(providers, timeout=10):
    games, problems = [], []
    for provider in providers:
        try:
            result = subprocess.run(provider.manifest_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=timeout, check=False)
            if result.returncode:
                raise RuntimeError("exit %d%s" % (result.returncode, ": " + result.stderr.strip() if result.stderr.strip() else ""))
            games.extend(parse(provider.id, result.stdout))
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
            LOG.warning("provider %s manifest unavailable: %s", provider.id, exc)
            problems.append("%s: %s" % (provider.id, exc))
    return sorted(games, key=lambda game: (game.title.casefold(), game.provider_id, game.id)), problems
