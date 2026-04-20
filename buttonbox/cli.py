"""
CLI entry point.  Usage:
  buttonbox start          — run the daemon
  buttonbox list           — show current config
  buttonbox set <btn> <event> <type>
  buttonbox clear <btn> <event>
  buttonbox wizard         — interactive setup wizard
  buttonbox device         — show detected device port
"""
import asyncio
import json
import logging
import sys

import click

from . import actions as _actions_pkg  # noqa: F401 — ensure registry is populated
from .actions.base import ACTION_REGISTRY
from .config import ConfigManager


def _make_config(ctx: click.Context) -> ConfigManager:
    return ctx.obj["config"]


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--config", "config_path", default=None, type=click.Path(), help="Path to config.json")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, config_path, verbose: bool) -> None:
    """ButtonBox — configure and run your Raspberry Pi Pico button box."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s  %(message)s",
    )
    ctx.ensure_object(dict)
    from pathlib import Path
    path = Path(config_path) if config_path else None
    ctx.obj["config"] = ConfigManager(path)


# ── start ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def start(ctx: click.Context) -> None:
    """Start the ButtonBox daemon (blocks until Ctrl+C)."""
    from .daemon import ButtonBoxDaemon

    config = _make_config(ctx)
    daemon = ButtonBoxDaemon(config)
    click.echo("ButtonBox started.  Press Ctrl+C to stop.")
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        daemon.stop()
        click.echo("\nStopped.")


# ── list ──────────────────────────────────────────────────────────────────────

@cli.command(name="list")
@click.pass_context
def list_buttons(ctx: click.Context) -> None:
    """Show current button → action mapping."""
    config = _make_config(ctx)
    click.echo("\nButton configuration\n" + "─" * 52)
    for btn_id, data in sorted(config.config["buttons"].items(), key=lambda x: int(x[0])):
        name = data.get("name", f"Button {btn_id}")
        click.echo(f"\n[{btn_id}] {name}")
        for ev in ("press", "hold", "release"):
            act = data.get(ev)
            label = json.dumps(act) if act else "(none)"
            click.echo(f"    {ev:8s}: {label}")
    click.echo()


# ── set ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("button_id", type=int)
@click.argument("event",     type=click.Choice(["press", "hold", "release"]))
@click.argument("action_type", type=click.Choice(sorted(ACTION_REGISTRY)))
@click.pass_context
def set(ctx: click.Context, button_id: int, event: str, action_type: str) -> None:  # noqa: A001
    """Assign an action to a button event.

    \b
    Example:
      buttonbox set 1 press keyboard
      buttonbox set 2 hold  command
    """
    config = _make_config(ctx)
    cls    = ACTION_REGISTRY[action_type]

    click.echo(f"\nConfiguring  BTN{button_id}  {event}  →  {action_type}")
    click.echo(f"Example:\n{json.dumps(cls.example(), indent=2)}\n")

    raw = click.prompt("Enter action config (JSON)", default=json.dumps(cls.example()))
    try:
        action_cfg = json.loads(raw)
        action_cfg["type"] = action_type  # ensure type field is present
        config.set_button_action(button_id, event, action_cfg)
        click.secho(f"✓  Saved  BTN{button_id} / {event}", fg="green")
    except json.JSONDecodeError as exc:
        click.secho(f"Invalid JSON: {exc}", fg="red", err=True)
        sys.exit(1)


# ── clear ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("button_id", type=int)
@click.argument("event",     type=click.Choice(["press", "hold", "release"]))
@click.pass_context
def clear(ctx: click.Context, button_id: int, event: str) -> None:
    """Remove the action assigned to a button event."""
    config = _make_config(ctx)
    config.set_button_action(button_id, event, None)
    click.secho(f"✓  Cleared  BTN{button_id} / {event}", fg="green")


# ── device ────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def device(ctx: click.Context) -> None:
    """Show which serial port the Pico is connected to."""
    from .device import _find_pico_port

    cfg  = _make_config(ctx)
    port = cfg.get_device_config().get("port") or _find_pico_port()
    if port:
        click.secho(f"Pico found at: {port}", fg="green")
    else:
        click.secho("Pico not detected.  Is it plugged in?", fg="yellow")


# ── wizard ────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def wizard(ctx: click.Context) -> None:
    """Interactive wizard to configure every button step by step."""
    config = _make_config(ctx)

    click.clear()
    click.echo("╔══════════════════════════════════════════╗")
    click.echo("║      ButtonBox  Configuration Wizard     ║")
    click.echo("╚══════════════════════════════════════════╝\n")

    click.echo("Available action types:\n")
    for name, cls in sorted(ACTION_REGISTRY.items()):
        click.echo(f"  {name:<12}  {cls.describe()}")
    click.echo()

    while True:
        click.echo("─" * 44)
        choice = click.prompt(
            "What would you like to do?\n"
            "  1  Configure a button\n"
            "  2  View current config\n"
            "  3  Exit wizard\n"
            "Choice",
            type=click.Choice(["1", "2", "3"]),
            show_choices=False,
        )

        if choice == "1":
            btn_id = click.prompt("\nButton ID (1-6)", type=int)
            event  = click.prompt(
                "Event", type=click.Choice(["press", "hold", "release"])
            )
            atype  = click.prompt(
                "Action type", type=click.Choice(sorted(ACTION_REGISTRY))
            )
            cls = ACTION_REGISTRY[atype]
            click.echo(f"\nExample config:\n{json.dumps(cls.example(), indent=2)}\n")
            raw = click.prompt("Enter config (JSON)", default=json.dumps(cls.example()))
            try:
                action_cfg = json.loads(raw)
                action_cfg["type"] = atype
                config.set_button_action(btn_id, event, action_cfg)
                click.secho(f"\n✓  Configured  BTN{btn_id} / {event}\n", fg="green")
            except json.JSONDecodeError as exc:
                click.secho(f"Invalid JSON: {exc}\n", fg="red")

        elif choice == "2":
            click.echo()
            for bid, data in sorted(config.config["buttons"].items(), key=lambda x: int(x[0])):
                click.echo(f"  BTN{bid}  {data.get('name', '')}")
                for ev in ("press", "hold", "release"):
                    act = data.get(ev)
                    if act:
                        click.echo(f"    {ev}: {json.dumps(act)}")
            click.echo()

        else:
            click.echo("Goodbye!")
            break
