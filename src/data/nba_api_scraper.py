"""
NBA API-based data scraper - replaces Selenium-based scraping.
Uses nba_api package to fetch game data, player stats, and video URLs.
"""

import os
import time
import requests
from datetime import datetime
from typing import Optional

from nba_api.stats.endpoints import (
    ScoreboardV2,
    BoxScoreTraditionalV2,
    PlayByPlayV2,
    VideoDetailsAsset,
)
from nba_api.stats.static import players, teams


class NBADataScraper:
    """Scrapes NBA data using the official stats API."""

    def __init__(self, game_date: str = None):
        """
        Initialize the scraper.

        Args:
            game_date: Date string in YYYY-MM-DD format. Defaults to today.
        """
        self.game_date = game_date or datetime.now().strftime("%Y-%m-%d")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com",
        }

    def get_games(self) -> list[dict]:
        """
        Get all games for the specified date.

        Returns:
            List of game dictionaries with game_id, home_team, away_team.
        """
        try:
            scoreboard = ScoreboardV2(game_date=self.game_date)
            games_data = scoreboard.get_normalized_dict()

            games = []
            for game in games_data.get("GameHeader", []):
                game_id = game.get("GAME_ID")
                home_team_id = game.get("HOME_TEAM_ID")
                away_team_id = game.get("VISITOR_TEAM_ID")

                # Get team names
                home_team = self._get_team_name(home_team_id)
                away_team = self._get_team_name(away_team_id)

                games.append({
                    "game_id": game_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                })

            return games
        except Exception as e:
            print(f"Error fetching games: {e}")
            return []

    def _get_team_name(self, team_id: int) -> str:
        """Get team name from team ID."""
        try:
            team_info = teams.find_team_name_by_id(team_id)
            return team_info.get("full_name", f"Team {team_id}") if team_info else f"Team {team_id}"
        except Exception:
            return f"Team {team_id}"

    def get_box_score(self, game_id: str) -> list[dict]:
        """
        Get box score for a specific game.

        Args:
            game_id: NBA game ID.

        Returns:
            List of player stat dictionaries.
        """
        try:
            box_score = BoxScoreTraditionalV2(game_id=game_id)
            data = box_score.get_normalized_dict()

            player_stats = []
            for player in data.get("PlayerStats", []):
                stats = {
                    "player_id": player.get("PLAYER_ID"),
                    "player_name": player.get("PLAYER_NAME"),
                    "team_id": player.get("TEAM_ID"),
                    "team_abbreviation": player.get("TEAM_ABBREVIATION"),
                    "min": player.get("MIN"),
                    "fgm": player.get("FGM", 0) or 0,
                    "fga": player.get("FGA", 0) or 0,
                    "pts": player.get("PTS", 0) or 0,
                    "reb": player.get("REB", 0) or 0,
                    "ast": player.get("AST", 0) or 0,
                    "stl": player.get("STL", 0) or 0,
                    "blk": player.get("BLK", 0) or 0,
                }
                player_stats.append(stats)

            return player_stats
        except Exception as e:
            print(f"Error fetching box score for game {game_id}: {e}")
            return []

    def get_play_by_play(self, game_id: str) -> list[dict]:
        """
        Get play-by-play data for a game.

        Args:
            game_id: NBA game ID.

        Returns:
            List of play dictionaries with event IDs.
        """
        try:
            pbp = PlayByPlayV2(game_id=game_id)
            data = pbp.get_normalized_dict()

            plays = []
            for play in data.get("PlayByPlay", []):
                plays.append({
                    "event_id": play.get("EVENTNUM"),
                    "event_type": play.get("EVENTMSGTYPE"),
                    "event_action": play.get("EVENTMSGACTIONTYPE"),
                    "period": play.get("PERIOD"),
                    "pctimestring": play.get("PCTIMESTRING"),
                    "description": play.get("HOMEDESCRIPTION") or play.get("VISITORDESCRIPTION") or play.get("NEUTRALDESCRIPTION", ""),
                    "player1_id": play.get("PLAYER1_ID"),
                    "player1_name": play.get("PLAYER1_NAME"),
                    "player2_id": play.get("PLAYER2_ID"),
                    "player2_name": play.get("PLAYER2_NAME"),
                })

            return plays
        except Exception as e:
            print(f"Error fetching play-by-play for game {game_id}: {e}")
            return []

    def get_video_url(self, game_id: str, event_id: int) -> Optional[str]:
        """
        Get video URL for a specific play event.

        Args:
            game_id: NBA game ID.
            event_id: Play event ID.

        Returns:
            Video URL string or None if not available.
        """
        try:
            video = VideoDetailsAsset(game_id=game_id, game_event_id=str(event_id))
            data = video.get_dict()

            # Try to get the video URL from the response
            result_sets = data.get("resultSets", {})
            if isinstance(result_sets, dict):
                meta = result_sets.get("Meta", {})
                video_urls = meta.get("videoUrls", [])
                if video_urls:
                    # Prefer large URL (lurl), fallback to medium (murl) or small (surl)
                    url = video_urls[0].get("lurl") or video_urls[0].get("murl") or video_urls[0].get("surl")
                    return url

            return None
        except Exception as e:
            print(f"Error fetching video for event {event_id}: {e}")
            return None

    def get_player_events(self, game_id: str, player_id: int, event_types: list[str] = None) -> list[dict]:
        """
        Get all events for a specific player in a game.

        Args:
            game_id: NBA game ID.
            player_id: NBA player ID.
            event_types: List of event types to filter ('fgm', 'ast', 'blk').

        Returns:
            List of event dictionaries with video URLs.
        """
        plays = self.get_play_by_play(game_id)
        player_events = []

        # Event type codes:
        # 1 = Made Shot (FGM)
        # 2 = Missed Shot
        # 3 = Free Throw
        # 4 = Rebound
        # 5 = Turnover
        # 6 = Foul
        # 7 = Violation
        # 8 = Substitution
        # 9 = Timeout
        # 10 = Jump Ball
        # 11 = Ejection
        # 12 = Start Period
        # 13 = End Period

        event_type_map = {
            "fgm": 1,  # Made shot
            "ast": 1,  # Assist is on made shot (player2)
            "blk": 2,  # Block is on missed shot
        }

        for play in plays:
            is_player_event = False
            event_category = None

            # Check if this player made a shot
            if play.get("event_type") == 1 and play.get("player1_id") == player_id:
                is_player_event = True
                event_category = "fgm"

            # Check if this player had an assist (player2 on made shot)
            if play.get("event_type") == 1 and play.get("player2_id") == player_id:
                is_player_event = True
                event_category = "ast"

            # Check if this player had a block
            if play.get("event_type") == 2:
                desc = (play.get("description") or "").upper()
                if "BLOCK" in desc and str(player_id) in str(play.get("player1_id", "")):
                    is_player_event = True
                    event_category = "blk"

            if is_player_event:
                if event_types is None or event_category in event_types:
                    player_events.append({
                        "event_id": play.get("event_id"),
                        "period": play.get("period"),
                        "time": play.get("pctimestring"),
                        "description": play.get("description"),
                        "category": event_category,
                    })

        return player_events

    def calculate_timestamp(self, period: int, time_str: str) -> int:
        """
        Calculate timestamp in seconds for sorting clips chronologically.

        Args:
            period: Game period (1-4 for regulation, 5+ for OT).
            time_str: Time string in "MM:SS" format.

        Returns:
            Timestamp in seconds from game start.
        """
        try:
            parts = time_str.split(":")
            minutes = int(parts[0])
            seconds = int(parts[1]) if len(parts) > 1 else 0

            if period <= 4:
                # Regular time: 12 minutes per quarter
                return 720 * period - 60 * minutes - seconds
            else:
                # Overtime: 5 minutes per OT period
                return 720 * 4 + 300 * (period - 4) - 60 * minutes - seconds
        except Exception:
            return 0

    def download_video(self, url: str, filepath: str) -> bool:
        """
        Download a video from URL to filepath.

        Args:
            url: Video URL.
            filepath: Local file path to save video.

        Returns:
            True if successful, False otherwise.
        """
        if not url:
            return False

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return True
            else:
                print(f"Failed to download video: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"Error downloading video: {e}")
            return False

    def download_player_highlights(
        self,
        game_id: str,
        player_id: int,
        player_name: str,
        game_date: str,
        build_path: str,
        fgm_count: int = 0,
        ast_count: int = 0,
        blk_count: int = 0,
    ) -> dict:
        """
        Download all highlight clips for a player.

        Args:
            game_id: NBA game ID.
            player_id: NBA player ID.
            player_name: Player's name for folder creation.
            game_date: Game date string for folder creation.
            build_path: Base build directory path.
            fgm_count: Expected number of FGM clips.
            ast_count: Expected number of AST clips.
            blk_count: Expected number of BLK clips.

        Returns:
            Dictionary with download statistics.
        """
        clips_path = f"{build_path}/{game_date}/{player_name}/clips"

        stats = {"fgm": 0, "ast": 0, "blk": 0, "failed": 0}

        # Get all player events
        events = self.get_player_events(game_id, player_id)

        for event in events:
            event_id = event.get("event_id")
            period = event.get("period", 1)
            time_str = event.get("time", "0:00")
            category = event.get("category")

            # Calculate timestamp for filename
            timestamp = self.calculate_timestamp(period, time_str)
            filepath = f"{clips_path}/{timestamp}.mp4"

            # Skip if file already exists
            if os.path.exists(filepath):
                stats[category] = stats.get(category, 0) + 1
                continue

            # Get video URL
            print(f"  Fetching video for {category.upper()}: {event.get('description', '')[:50]}...")
            video_url = self.get_video_url(game_id, event_id)

            if video_url:
                if self.download_video(video_url, filepath):
                    stats[category] = stats.get(category, 0) + 1
                    print(f"    Downloaded: {timestamp}.mp4")
                else:
                    stats["failed"] += 1
            else:
                stats["failed"] += 1
                print(f"    No video available for event {event_id}")

            # Rate limiting to avoid API throttling
            time.sleep(0.5)

        return stats

    def get_player_headshot_url(self, player_id: int) -> str:
        """
        Get player headshot image URL.

        Args:
            player_id: NBA player ID.

        Returns:
            URL string for player headshot.
        """
        return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"


def get_highlight_players(game_id: str, scraper: NBADataScraper, algorithm_func) -> list[dict]:
    """
    Get list of players who qualify for highlights based on the algorithm.

    Args:
        game_id: NBA game ID.
        scraper: NBADataScraper instance.
        algorithm_func: Function that takes (fgm, reb, ast, stl, blk, pts) and returns bool.

    Returns:
        List of player dictionaries who qualify for highlights.
    """
    box_score = scraper.get_box_score(game_id)
    highlight_players = []

    for player in box_score:
        # Skip players with no minutes
        if not player.get("min"):
            continue

        fgm = player.get("fgm", 0)
        reb = player.get("reb", 0)
        ast = player.get("ast", 0)
        stl = player.get("stl", 0)
        blk = player.get("blk", 0)
        pts = player.get("pts", 0)

        if algorithm_func(fgm, reb, ast, stl, blk, pts):
            highlight_players.append({
                "player_id": player.get("player_id"),
                "player_name": player.get("player_name"),
                "team_abbreviation": player.get("team_abbreviation"),
                "fgm": fgm,
                "reb": reb,
                "ast": ast,
                "stl": stl,
                "blk": blk,
                "pts": pts,
            })

    return highlight_players
