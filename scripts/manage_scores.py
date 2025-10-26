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
PLAYS_PATH = DATA_DIR / "plays.json"
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


def load_plays_payload() -> Dict[str, Any]:
    payload = load_json(PLAYS_PATH, {"plays": []})
    plays = payload.get("plays")
    if not isinstance(plays, list):
        plays = []
    cleaned: List[Dict[str, Any]] = []
    for entry in plays:
        if not isinstance(entry, dict):
            continue
        game = str(entry.get("game", "")).strip()
        results = entry.get("results")
        date = entry.get("date")
        event = entry.get("event")
        scored = bool(entry.get("scored"))
        notes = str(entry.get("notes", "") or "").strip()
        play_id = entry.get("id")
        normalized_results: List[Dict[str, Any]] = []
        if isinstance(results, list):
            for res in results:
                if not isinstance(res, dict):
                    continue
                player = str(res.get("player", "")).strip()
                if not player:
                    continue
                placement = res.get("placement")
                try:
                    placement_val = int(placement) if placement is not None else None
                except (TypeError, ValueError):
                    placement_val = None
                try:
                    points_val = int(res.get("points", 0))
                except (TypeError, ValueError):
                    points_val = 0
                normalized_results.append(
                    {
                        "player": player,
                        "placement": placement_val,
                        "points": points_val,
                    }
                )
        cleaned.append(
            {
                "id": play_id,
                "game": game,
                "date": date,
                "event": event,
                "scored": scored,
                "notes": notes,
                "timestamp": entry.get("timestamp"),
                "results": normalized_results,
            }
        )
    payload["plays"] = cleaned
    return payload


def save_plays_payload(payload: Dict[str, Any]) -> None:
    plays = payload.get("plays")
    if not isinstance(plays, list):
        plays = []
    payload["plays"] = plays
    save_json(PLAYS_PATH, payload)


def parse_name_arguments(values: Optional[List[str]]) -> List[str]:
    names: List[str] = []
    if not values:
        return names
    for value in values:
        if value is None:
            continue
        for piece in str(value).split(","):
            cleaned = piece.strip()
            if cleaned:
                names.append(cleaned)
    return names


def dedupe_preserve_case(names: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for name in names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def compute_leaderboard(
    config: Dict[str, Any], events_payload: Dict[str, Any], plays_payload: Dict[str, Any]
) -> Dict[str, Any]:
    players: Dict[str, Dict[str, Any]] = {}
    events = events_payload.get("events", [])
    plays = plays_payload.get("plays", [])
    recent_events: List[Dict[str, Any]] = []
    recent_plays: List[Dict[str, Any]] = []
    updated_candidates: List[datetime] = []
    player_activity: Dict[str, Dict[str, Any]] = {}

    def ensure_activity(player_name: str) -> Dict[str, Any]:
        entry = player_activity.get(player_name)
        if entry:
            return entry
        entry = {
            "player": player_name,
            "totalPlays": 0,
            "scoredPlays": 0,
            "unscoredPlays": 0,
            "games": defaultdict(int),
            "podiums": defaultdict(int),
        }
        player_activity[player_name] = entry
        return entry

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

    for play in plays:
        game = play.get("game") or "Untitled Game"
        date_str = play.get("date")
        event_name = play.get("event")
        scored = bool(play.get("scored"))
        notes = play.get("notes")
        results = play.get("results") or []
        timestamp = parse_timestamp(play.get("timestamp"), date_str)
        if timestamp:
            updated_candidates.append(timestamp)

        play_entry = {
            "game": game,
            "date": date_str,
            "event": event_name,
            "scored": scored,
            "notes": notes,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "results": [],
        }

        for result in results:
            player_name = result.get("player")
            if not player_name:
                continue
            placement = result.get("placement")
            try:
                points_value = int(result.get("points", 0))
            except (TypeError, ValueError):
                points_value = 0

            stats = ensure_activity(player_name)
            stats["totalPlays"] += 1
            if scored:
                stats["scoredPlays"] += 1
            else:
                stats["unscoredPlays"] += 1
            stats["games"][game] += 1
            if placement in (1, 2, 3):
                stats["podiums"][placement] += 1

            play_entry["results"].append(
                {
                    "player": player_name,
                    "placement": placement,
                    "points": points_value,
                }
            )

        if play_entry["results"]:
            recent_plays.append(play_entry)

    for player_record in players.keys():
        ensure_activity(player_record)

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

    def latest_timestamp_for_play(play_entry: Dict[str, Any]) -> datetime:
        candidate = parse_timestamp(play_entry.get("timestamp"), play_entry.get("date"))
        if candidate:
            return candidate
        return datetime.min.replace(tzinfo=timezone.utc)

    recent_plays.sort(key=latest_timestamp_for_play, reverse=True)
    if isinstance(limit, int) and limit > 0:
        recent_plays = recent_plays[:limit]

    activity_list: List[Dict[str, Any]] = []
    for stats in player_activity.values():
        games_counts = sorted(
            stats["games"].items(), key=lambda item: (-item[1], item[0].lower())
        )
        activity_list.append(
            {
                "player": stats["player"],
                "totalPlays": stats["totalPlays"],
                "scoredPlays": stats["scoredPlays"],
                "unscoredPlays": stats["unscoredPlays"],
                "games": [
                    {"game": game_name, "count": count}
                    for game_name, count in games_counts
                ],
                "podiums": {
                    "1": int(stats["podiums"].get(1, 0)),
                    "2": int(stats["podiums"].get(2, 0)),
                    "3": int(stats["podiums"].get(3, 0)),
                },
            }
        )

    activity_list.sort(key=lambda entry: (-entry["totalPlays"], entry["player"].lower()))

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
        "recentPlays": recent_plays,
        "playerActivity": activity_list,
    }
    return result


def rebuild_leaderboard(verbose: bool = False) -> Dict[str, Any]:
    config = load_json(CONFIG_PATH, {})
    events = load_json(EVENTS_PATH, {"events": []})
    plays = load_plays_payload()
    payload = compute_leaderboard(config, events, plays)
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


def command_plays_add(args: argparse.Namespace) -> int:
    plays_payload = load_plays_payload()
    events_payload = load_json(EVENTS_PATH, {"events": []})

    game = args.game or input("Game name: ").strip()
    if not game:
        print("Game name is required.", file=sys.stderr)
        return 1

    date = args.date or input("Play date (YYYY-MM-DD, blank for today): ").strip()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    event_name = args.event
    if event_name is None:
        event_name = input("Event name (blank if not part of an event): ").strip()
    if not event_name:
        event_name = None

    if args.ranked and args.unranked:
        print("Cannot set both ranked and unranked options.", file=sys.stderr)
        return 1

    if args.ranked:
        scored = True
    elif args.unranked:
        scored = False
    else:
        default_prompt = input("Count this play for points? [Y/n]: ").strip().lower()
        scored = default_prompt != "n"

    participants = parse_name_arguments(args.players)
    if not participants:
        participants = parse_name_arguments([input("Players (comma separated): ")])
    participants = dedupe_preserve_case(participants)
    if not participants:
        print("At least one player is required.", file=sys.stderr)
        return 1

    def prompt_placement(label: str, provided: Optional[List[str]]) -> List[str]:
        if provided:
            return dedupe_preserve_case(provided)
        response = input(f"{label} place (comma separated, blank for none): ").strip()
        return dedupe_preserve_case(parse_name_arguments([response]))

    first = prompt_placement("First", parse_name_arguments(args.first)) if scored else []
    second = prompt_placement("Second", parse_name_arguments(args.second)) if scored else []
    third = prompt_placement("Third", parse_name_arguments(args.third)) if scored else []

    note = args.note
    if note is None:
        note_input = input("Notes (optional): ").strip()
        note = note_input or None

    auto_award: Optional[bool]
    if args.award and args.no_award:
        print("Cannot use --award and --no-award together.", file=sys.stderr)
        return 1
    if args.award:
        auto_award = True
    elif args.no_award:
        auto_award = False
    else:
        auto_award = scored

    points_first = args.points_first if args.points_first is not None else 5
    points_second = args.points_second if args.points_second is not None else 3
    points_third = args.points_third if args.points_third is not None else 2
    points_map = {1: points_first, 2: points_second, 3: points_third}

    timestamp = datetime.now(timezone.utc)
    play_id = args.play_id or secrets.token_hex(6)

    placement_map = {1: first, 2: second, 3: third}
    results: List[Dict[str, Any]] = []
    added = set()

    def add_result(player_name: str, placement: Optional[int]) -> None:
        key = player_name.casefold()
        if key in added and placement is None:
            return
        if placement in (1, 2, 3):
            points_value = points_map.get(placement, 0) if auto_award else 0
        else:
            points_value = 0
        results.append(
            {
                "player": player_name,
                "placement": placement,
                "points": points_value,
            }
        )
        added.add(key)

    for placement, names in placement_map.items():
        for name in names:
            add_result(name, placement)

    for participant in participants:
        if participant.casefold() not in added:
            add_result(participant, None)

    plays_list = plays_payload.setdefault("plays", [])
    plays_list.append(
        {
            "id": play_id,
            "game": game,
            "date": date,
            "event": event_name,
            "scored": bool(scored),
            "notes": note,
            "timestamp": timestamp.isoformat(),
            "results": results,
        }
    )
    save_plays_payload(plays_payload)

    if auto_award and scored:
        if not event_name:
            print("Skipping auto-award because no event name was provided.", file=sys.stderr)
        else:
            event = ensure_event(events_payload, event_name, date)
            for placement, names in placement_map.items():
                if placement not in points_map:
                    continue
                points_value = points_map[placement]
                if points_value <= 0:
                    continue
                for name in names:
                    reason = f"{placement}{'st' if placement == 1 else 'nd' if placement == 2 else 'rd'} place in {game}"
                    event.setdefault("awards", []).append(
                        {
                            "player": name,
                            "points": points_value,
                            "reason": reason,
                            "timestamp": timestamp.isoformat(),
                        }
                    )
            save_json(EVENTS_PATH, events_payload)

    rebuild_leaderboard(verbose=args.verbose)

    print(f"Logged play of {game} on {date} with {len(participants)} participant(s).")
    if auto_award and scored and event_name:
        print("Points were awarded based on placements.")
    return 0


def command_plays_list(args: argparse.Namespace) -> int:
    plays_payload = load_plays_payload()
    plays = plays_payload.get("plays", [])
    if not plays:
        print("No plays recorded yet.")
        return 0

    def play_timestamp(play: Dict[str, Any]) -> datetime:
        return parse_timestamp(play.get("timestamp"), play.get("date")) or datetime.min.replace(
            tzinfo=timezone.utc
        )

    plays_sorted = sorted(plays, key=play_timestamp, reverse=True)
    limit = args.limit
    if limit is not None:
        plays_sorted = plays_sorted[:limit]

    for play in plays_sorted:
        date = play.get("date", "Unknown date")
        game = play.get("game", "Game")
        event = play.get("event")
        scored = "ranked" if play.get("scored") else "unranked"
        header = f"{date} — {game} ({scored})"
        if event:
            header += f" @ {event}"
        print(header)
        for result in play.get("results", []):
            player = result.get("player", "Unknown")
            placement = result.get("placement")
            points = result.get("points", 0)
            placement_label = (
                f"{placement}{'st' if placement == 1 else 'nd' if placement == 2 else 'rd'}"
                if placement in (1, 2, 3)
                else "Participated"
            )
            suffix = f" (+{points} pts)" if points else ""
            print(f"  {placement_label}: {player}{suffix}")
        if play.get("notes"):
            print(f"  Notes: {play.get('notes')}")
        print()
    return 0




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

    plays_parser = subparsers.add_parser("plays", help="Log and review game plays")
    plays_subparsers = plays_parser.add_subparsers(dest="plays_command")

    plays_add = plays_subparsers.add_parser("add", help="Add a play entry")
    plays_add.add_argument("--game", "-g", help="Name of the game played")
    plays_add.add_argument("--date", "-d", help="Date of the play (YYYY-MM-DD)")
    plays_add.add_argument("--event", "-e", help="Event name (e.g. Game Night #1)")
    plays_add.add_argument("--ranked", dest="ranked", action="store_true", help="Mark play as ranked")
    plays_add.add_argument(
        "--unranked", dest="unranked", action="store_true", help="Mark play as unranked"
    )
    plays_add.add_argument(
        "--players",
        "-p",
        action="append",
        help="Comma-separated list of players who participated",
    )
    plays_add.add_argument("--first", action="append", help="Comma-separated first place players")
    plays_add.add_argument("--second", action="append", help="Comma-separated second place players")
    plays_add.add_argument("--third", action="append", help="Comma-separated third place players")
    plays_add.add_argument("--points-first", type=int, help="Points awarded for first place")
    plays_add.add_argument("--points-second", type=int, help="Points awarded for second place")
    plays_add.add_argument("--points-third", type=int, help="Points awarded for third place")
    plays_add.add_argument("--award", action="store_true", help="Force auto-awarding points")
    plays_add.add_argument("--no-award", action="store_true", help="Skip awarding points")
    plays_add.add_argument("--note", "-n", help="Notes about the play")
    plays_add.add_argument("--play-id", help="Custom identifier for the play entry")
    plays_add.add_argument("--verbose", "-v", action="store_true", help="Print file updates")
    plays_add.set_defaults(func=command_plays_add)

    plays_list = plays_subparsers.add_parser("list", help="List recorded plays")
    plays_list.add_argument("--limit", type=int, help="Limit the number of plays shown")
    plays_list.set_defaults(func=command_plays_list)

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
