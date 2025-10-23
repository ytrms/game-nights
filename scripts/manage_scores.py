#!/usr/bin/env python3
"""Utility helpers for updating the Gravina game night leaderboard data."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"

CONFIG_PATH = DATA_DIR / "config.json"
EVENTS_PATH = DATA_DIR / "events.json"
GUEST_TOKENS_PATH = DATA_DIR / "guest_tokens.json"
LEADERBOARD_PATH = PUBLIC_DIR / "leaderboard.json"
PUBLIC_GUEST_TOKENS_PATH = PUBLIC_DIR / "guest_tokens.json"

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def parse_timestamp(value: Optional[str], fallback: Optional[str] = None) -> Optional[datetime]:
    raw = value or fallback
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(raw)
    except ValueError:
        try:
            dt = datetime.strptime(raw, ISO_FORMAT)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_guest_tokens() -> Dict[str, Any]:
    payload = load_json(GUEST_TOKENS_PATH, {"tokens": {}})
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        tokens = {}
    cleaned = {}
    for key, value in tokens.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        token = key.strip()
        name = value.strip()
        if not token or not name:
            continue
        cleaned[token] = name
    payload["tokens"] = cleaned
    return payload


def save_guest_tokens(payload: Dict[str, Any]) -> None:
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        tokens = {}
    payload["tokens"] = tokens
    save_json(GUEST_TOKENS_PATH, payload)



def compute_leaderboard(config: Dict[str, Any], events_payload: Dict[str, Any]) -> Dict[str, Any]:
    players: Dict[str, Dict[str, Any]] = {}
    events = events_payload.get("events", [])
    recent_events: List[Dict[str, Any]] = []
    updated_candidates: List[datetime] = []

    for event in events:
        name = event.get("name") or "Game Night"
        date_str = event.get("date")
        awards = event.get("awards") or []
        event_entry = {"name": name, "date": date_str, "awards": []}

        for award in awards:
            player_name = award.get("player")
            if not player_name:
                continue
            try:
                points = int(award.get("points", 0))
            except (TypeError, ValueError):
                points = 0
            reason = award.get("reason") or "Awarded points"
            timestamp = parse_timestamp(award.get("timestamp"), date_str)
            if timestamp:
                updated_candidates.append(timestamp)

            player = players.setdefault(
                player_name,
                {"player": player_name, "points": 0, "breakdown": defaultdict(lambda: {"count": 0, "points": 0})},
            )

            player["points"] += points
            bucket = player["breakdown"][reason]
            bucket["count"] += 1
            bucket["points"] += points

            event_entry["awards"].append(
                {
                    "player": player_name,
                    "points": points,
                    "reason": reason,
                    "timestamp": timestamp.isoformat() if timestamp else None,
                }
            )

        if event_entry["awards"]:
            recent_events.append(event_entry)

    players_list = []
    for record in players.values():
        breakdown_list = [
            {
                "reason": reason,
                "count": details["count"],
                "points": details["points"],
            }
            for reason, details in record["breakdown"].items()
        ]
        breakdown_list.sort(key=lambda item: (-item["points"], item["reason"].lower()))
        players_list.append(
            {
                "player": record["player"],
                "points": record["points"],
                "breakdown": breakdown_list,
            }
        )

    players_list.sort(key=lambda item: (-item["points"], item["player"].lower()))

    current_rank = 0
    previous_points: Optional[int] = None
    for index, player in enumerate(players_list, start=1):
        if previous_points != player["points"]:
            current_rank = index
            previous_points = player["points"]
        player["rank"] = current_rank

    def latest_timestamp_for_event(event: Dict[str, Any]) -> datetime:
        candidate_times = []
        for award in event.get("awards", []):
            candidate = parse_timestamp(award.get("timestamp"))
            if candidate:
                candidate_times.append(candidate)
        event_time = parse_timestamp(event.get("date"))
        if event_time:
            candidate_times.append(event_time)
        if not candidate_times:
            return datetime.min.replace(tzinfo=timezone.utc)
        return max(candidate_times)

    recent_events.sort(key=latest_timestamp_for_event, reverse=True)

    limit = config.get("recentEventsLimit", 8)
    if isinstance(limit, int) and limit > 0:
        recent_events = recent_events[:limit]

    last_updated: Optional[datetime]
    if updated_candidates:
        last_updated = max(updated_candidates)
    else:
        last_updated = datetime.now(timezone.utc)

    result = {
        "title": config.get("title") or "Game Night Leaderboard",
        "tagline": config.get("tagline") or "Tracking every big play and bragging right.",
        "seasonLabel": config.get("seasonLabel"),
        "lastUpdated": last_updated.isoformat(),
        "leaderboard": players_list,
        "scoringRules": config.get("scoringRules", []),
        "recentEvents": recent_events,
    }
    return result


def rebuild_leaderboard(verbose: bool = False) -> Dict[str, Any]:
    config = load_json(CONFIG_PATH, {})
    events = load_json(EVENTS_PATH, {"events": []})
    payload = compute_leaderboard(config, events)
    save_json(LEADERBOARD_PATH, payload)
    guest_tokens = load_guest_tokens()
    save_json(PUBLIC_GUEST_TOKENS_PATH, guest_tokens)
    if verbose:
        print(f"Wrote leaderboard to {LEADERBOARD_PATH.relative_to(ROOT)}")
        print(f"Wrote guest tokens to {PUBLIC_GUEST_TOKENS_PATH.relative_to(ROOT)}")
    return payload


def ensure_event(events: Dict[str, Any], name: str, date: str) -> Dict[str, Any]:
    for event in events.get("events", []):
        if event.get("name") == name and event.get("date") == date:
            if "awards" not in event or event["awards"] is None:
                event["awards"] = []
            return event
    event = {"name": name, "date": date, "awards": []}
    events.setdefault("events", []).append(event)
    return event


def command_award(args: argparse.Namespace) -> int:
    events = load_json(EVENTS_PATH, {"events": []})
    player = args.player or input("Player name: ").strip()
    if not player:
        print("Player name is required.", file=sys.stderr)
        return 1

    reason = args.reason or input("Reason for points: ").strip() or "Awarded points"

    points: int
    if args.points is not None:
        points = args.points
    else:
        while True:
            raw = input("Points awarded: ").strip()
            if not raw:
                continue
            try:
                points = int(raw)
                break
            except ValueError:
                print("Please enter a whole number.", file=sys.stderr)

    date = args.date
    if not date:
        date = input("Event date (YYYY-MM-DD, blank for today): ").strip()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    event_name = args.event or input("Event name (e.g. Game Night #9): ").strip()
    if not event_name:
        event_name = f"Game Night {date}"

    timestamp = args.timestamp
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()

    event = ensure_event(events, event_name, date)
    event.setdefault("awards", []).append(
        {
            "player": player,
            "points": points,
            "reason": reason,
            "timestamp": timestamp,
        }
    )
    save_json(EVENTS_PATH, events)
    rebuild_leaderboard(verbose=args.verbose)
    print(f"Awarded {points} pts to {player} for '{reason}' on {date}.")
    return 0


def command_list(args: argparse.Namespace) -> int:
    payload = rebuild_leaderboard(verbose=False)
    rows = payload["leaderboard"]
    if not rows:
        print("No awards logged yet.")
        return 0

    name_width = max(len("Player"), max((len(row["player"]) for row in rows), default=6))
    points_width = max(len("Points"), max((len(str(row["points"])) for row in rows), default=6))

    print(f"{'Rank':<6}{'Player':<{name_width}}  {'Points':>{points_width}}  Top awards")
    print("-" * (name_width + points_width + 20))
    for row in rows:
        top_award = row["breakdown"][0]["reason"] if row["breakdown"] else ""
        print(f"#{row['rank']:<5}{row['player']:<{name_width}}  {row['points']:>{points_width}}  {top_award}")
    return 0


def command_events(args: argparse.Namespace) -> int:
    events = load_json(EVENTS_PATH, {"events": []}).get("events", [])
    if not events:
        print("No events recorded yet.")
        return 0

    events.sort(key=lambda ev: ev.get("date") or "", reverse=True)
    for event in events:
        print(f"{event.get('date', 'Unknown date')} — {event.get('name', 'Game Night')}")
        for award in event.get("awards", []):
            player = award.get("player", "Unknown")
            points = award.get("points", 0)
            reason = award.get("reason", "Awarded points")
            print(f"  +{points} pts to {player}: {reason}")
        print()
    return 0


def command_rebuild(args: argparse.Namespace) -> int:
    rebuild_leaderboard(verbose=True)
    return 0


def generate_unique_token(existing: Dict[str, str]) -> str:
    while True:
        token = secrets.token_urlsafe(5).rstrip("=")
        if token not in existing:
            return token


def command_tokens_add(args: argparse.Namespace) -> int:
    names: List[str] = args.names
    if not names:
        entered = input("Name to create a token for (blank to cancel): ").strip()
        if not entered:
            print("No tokens created.")
            return 1
        names = [entered]
    payload = load_guest_tokens()
    tokens = payload.setdefault("tokens", {})
    created: Dict[str, str] = {}
    for name in names:
        cleaned = name.strip()
        if not cleaned:
            continue
        if cleaned in tokens.values():
            # avoid duplicate entries with different tokens
            existing_token = next((key for key, value in tokens.items() if value == cleaned), None)
            if existing_token:
                print(f"Token already exists for {cleaned}: {existing_token}")
                continue
        token = generate_unique_token(tokens)
        tokens[token] = cleaned
        created[cleaned] = token
    if not created:
        print("No new tokens created.")
        return 1
    save_guest_tokens(payload)
    rebuild_leaderboard(verbose=args.verbose)
    for name, token in created.items():
        print(f"{name}: {token}")
    return 0


def command_tokens_list(args: argparse.Namespace) -> int:
    payload = load_guest_tokens()
    tokens = payload.get("tokens", {})
    if not tokens:
        print("No guest tokens yet. Generate one with 'tokens add'.")
        return 0
    print("Guest tokens:")
    for token, name in tokens.items():
        print(f"  {token} → {name}")
    return 0


def command_tokens_remove(args: argparse.Namespace) -> int:
    tokens_to_remove: List[str] = args.tokens
    if not tokens_to_remove:
        entered = input("Token to remove (blank to cancel): ").strip()
        if not entered:
            print("No tokens removed.")
            return 1
        tokens_to_remove = [entered]
    payload = load_guest_tokens()
    tokens = payload.get("tokens", {})
    removed_any = False
    for token in tokens_to_remove:
        if token in tokens:
            removed_any = True
            removed_name = tokens.pop(token)
            print(f"Removed token {token} (was {removed_name}).")
        else:
            print(f"Token {token} not found.", file=sys.stderr)
    if removed_any:
        save_guest_tokens(payload)
        rebuild_leaderboard(verbose=args.verbose)
        return 0
    return 1




def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.set_defaults(func=None)

    subparsers = parser.add_subparsers(dest="command")

    award_parser = subparsers.add_parser("award", help="Award points to a player")
    award_parser.add_argument("--player", "-p", help="Player receiving the points")
    award_parser.add_argument("--points", "-P", type=int, help="Points to award")
    award_parser.add_argument(
        "--reason", "-r", help="Short description (e.g. 'Won Catan final table')"
    )
    award_parser.add_argument("--event", "-e", help="Event name (default: Game Night <date>)")
    award_parser.add_argument("--date", "-d", help="Event date (YYYY-MM-DD)")
    award_parser.add_argument(
        "--timestamp",
        "-t",
        help="Exact timestamp for the award (ISO 8601). Defaults to current time.",
    )
    award_parser.add_argument("--verbose", "-v", action="store_true", help="Print file updates")
    award_parser.set_defaults(func=command_award)

    list_parser = subparsers.add_parser("list", help="Show the current leaderboard")
    list_parser.set_defaults(func=command_list)

    events_parser = subparsers.add_parser("events", help="Show the event log with awards")
    events_parser.set_defaults(func=command_events)

    rebuild_parser = subparsers.add_parser("rebuild", help="Rebuild leaderboard.json without changes")
    rebuild_parser.set_defaults(func=command_rebuild)

    tokens_parser = subparsers.add_parser("tokens", help="Manage greeting tokens")
    tokens_subparsers = tokens_parser.add_subparsers(dest="token_command")

    tokens_add = tokens_subparsers.add_parser("add", help="Generate unique token(s) for guests")
    tokens_add.add_argument("names", nargs="*", help="Guest names to create tokens for")
    tokens_add.add_argument("--verbose", "-v", action="store_true", help="Print file updates")
    tokens_add.set_defaults(func=command_tokens_add)

    tokens_list = tokens_subparsers.add_parser("list", help="List existing guest tokens")
    tokens_list.set_defaults(func=command_tokens_list)

    tokens_remove = tokens_subparsers.add_parser("remove", help="Delete token(s)")
    tokens_remove.add_argument("tokens", nargs="*", help="Token values to remove")
    tokens_remove.add_argument("--verbose", "-v", action="store_true", help="Print file updates")
    tokens_remove.set_defaults(func=command_tokens_remove)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.func is None:
        parser.print_help(sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
