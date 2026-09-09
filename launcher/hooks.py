"""Best-effort provider lifecycle notifications."""
import logging
import os
import subprocess

LOG = logging.getLogger(__name__)

def notify(providers, event):
    for provider in providers:
        command = provider.hooks.get(event)
        if not command: continue
        environment = os.environ.copy(); environment["PI_GAMES_EVENT"] = event; environment["PI_GAMES_PROVIDER"] = provider.id
        try:
            subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)
        except OSError as exc:
            LOG.warning("provider %s hook %s failed: %s", provider.id, event, exc)
