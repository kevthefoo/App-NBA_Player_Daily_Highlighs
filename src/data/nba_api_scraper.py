"""
NBA API-based data scraper - uses direct HTTP requests to NBA stats endpoints.
Replaces nba_api library with direct requests for more control and reliability.
"""

import json
import os
import time
import requests
from datetime import datetime
from typing import Optional

from src.logger import get_logger, log_exception

# Initialize logger for this module
logger = get_logger("nba_api")


# Team ID to name/abbreviation mapping
TEAM_ID_MAP = {
    1610612737: {"abbreviation": "ATL", "full_name": "Atlanta Hawks"},
    1610612738: {"abbreviation": "BOS", "full_name": "Boston Celtics"},
    1610612751: {"abbreviation": "BKN", "full_name": "Brooklyn Nets"},
    1610612766: {"abbreviation": "CHA", "full_name": "Charlotte Hornets"},
    1610612741: {"abbreviation": "CHI", "full_name": "Chicago Bulls"},
    1610612739: {"abbreviation": "CLE", "full_name": "Cleveland Cavaliers"},
    1610612742: {"abbreviation": "DAL", "full_name": "Dallas Mavericks"},
    1610612743: {"abbreviation": "DEN", "full_name": "Denver Nuggets"},
    1610612765: {"abbreviation": "DET", "full_name": "Detroit Pistons"},
    1610612744: {"abbreviation": "GSW", "full_name": "Golden State Warriors"},
    1610612745: {"abbreviation": "HOU", "full_name": "Houston Rockets"},
    1610612754: {"abbreviation": "IND", "full_name": "Indiana Pacers"},
    1610612746: {"abbreviation": "LAC", "full_name": "Los Angeles Clippers"},
    1610612747: {"abbreviation": "LAL", "full_name": "Los Angeles Lakers"},
    1610612763: {"abbreviation": "MEM", "full_name": "Memphis Grizzlies"},
    1610612748: {"abbreviation": "MIA", "full_name": "Miami Heat"},
    1610612749: {"abbreviation": "MIL", "full_name": "Milwaukee Bucks"},
    1610612750: {"abbreviation": "MIN", "full_name": "Minnesota Timberwolves"},
    1610612740: {"abbreviation": "NOP", "full_name": "New Orleans Pelicans"},
    1610612752: {"abbreviation": "NYK", "full_name": "New York Knicks"},
    1610612760: {"abbreviation": "OKC", "full_name": "Oklahoma City Thunder"},
    1610612753: {"abbreviation": "ORL", "full_name": "Orlando Magic"},
    1610612755: {"abbreviation": "PHI", "full_name": "Philadelphia 76ers"},
    1610612756: {"abbreviation": "PHX", "full_name": "Phoenix Suns"},
    1610612757: {"abbreviation": "POR", "full_name": "Portland Trail Blazers"},
    1610612758: {"abbreviation": "SAC", "full_name": "Sacramento Kings"},
    1610612759: {"abbreviation": "SAS", "full_name": "San Antonio Spurs"},
    1610612761: {"abbreviation": "TOR", "full_name": "Toronto Raptors"},
    1610612762: {"abbreviation": "UTA", "full_name": "Utah Jazz"},
    1610612764: {"abbreviation": "WAS", "full_name": "Washington Wizards"},
}


def parse_nba_response(result_set: dict) -> list[dict]:
    """
    Convert NBA API rowSet to list of dictionaries.

    Args:
        result_set: A result set from NBA API response containing 'headers' and 'rowSet'.

    Returns:
        List of dictionaries with header names as keys.
    """
    headers = result_set.get('headers', [])
    rows = result_set.get('rowSet', [])
    return [dict(zip(headers, row)) for row in rows]


class NBADataScraper:
    """Scrapes NBA data using direct HTTP requests to stats.nba.com."""

    BASE_URL = "https://stats.nba.com/stats"

    def __init__(self, game_date: str = None):
        """
        Initialize the scraper.

        Args:
            game_date: Date string in YYYY-MM-DD format. Defaults to today.
        """
        self.game_date = game_date or datetime.now().strftime("%Y-%m-%d")
        self.headers = {
            'Host': 'stats.nba.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.nba.com/',
            'Origin': 'https://www.nba.com',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _make_request(self, endpoint: str, params: dict, max_retries: int = 3) -> Optional[dict]:
        """
        Make a request to the NBA stats API with retry logic.

        Args:
            endpoint: API endpoint name (e.g., 'scoreboardv2').
            params: Query parameters for the request.
            max_retries: Maximum number of retry attempts.

        Returns:
            JSON response as dictionary, or None if request failed.
        """
        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(max_retries):
            try:
                # Longer timeout and add delay between retries
                if attempt > 0:
                    wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                    logger.debug(f"Retry {attempt}/{max_retries} for {endpoint} in {wait_time}s...")
                    time.sleep(wait_time)

                response = self.session.get(url, params=params, timeout=60)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout for {endpoint} (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    logger.error(f"Request error for {endpoint}: {e}")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {endpoint}: {e}")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for {endpoint}: {e}")
                return None

        return None

    def _get_result_set(self, data: dict, name: str) -> Optional[dict]:
        """
        Find a result set by name in the API response.

        Args:
            data: Full API response.
            name: Name of the result set to find.

        Returns:
            The result set dictionary, or None if not found.
        """
        if not data:
            return None
        result_sets = data.get('resultSets', [])
        for rs in result_sets:
            if rs.get('name') == name:
                return rs
        return None

    def get_games(self) -> list[dict]:
        """
        Get all games for the specified date.

        Returns:
            List of game dictionaries with game_id, home_team, away_team.
        """
        params = {
            'DayOffset': 0,
            'GameDate': self.game_date,
            'LeagueID': '00',
        }

        data = self._make_request('scoreboardv2', params)
        if not data:
            logger.error("No data returned from scoreboardv2")
            return []

        try:
            game_header = self._get_result_set(data, 'GameHeader')
            if not game_header:
                logger.error("No GameHeader in response")
                return []

            games_data = parse_nba_response(game_header)
            games = []

            for game in games_data:
                game_id = game.get("GAME_ID")
                home_team_id = game.get("HOME_TEAM_ID")
                away_team_id = game.get("VISITOR_TEAM_ID")
                game_status = game.get("GAME_STATUS_ID", "Unknown")

                # Get team names
                home_team = self._get_team_name(home_team_id)
                away_team = self._get_team_name(away_team_id)

                games.append({
                    "game_id": game_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "status": game_status,
                })

            return games
        except Exception as e:
            log_exception(logger, "Error parsing games", e)
            return []

    def _get_team_name(self, team_id: int) -> str:
        """Get team name from team ID using local mapping."""
        team_info = TEAM_ID_MAP.get(team_id)
        if team_info:
            return team_info.get("full_name", f"Team {team_id}")
        return f"Team {team_id}"

    def get_box_score(self, game_id: str) -> list[dict]:
        """
        Get box score for a specific game using CDN endpoint.

        Args:
            game_id: NBA game ID.

        Returns:
            List of player stat dictionaries.
        """
        cdn_url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"

        try:
            cdn_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Referer': 'https://www.nba.com/',
            }
            response = requests.get(cdn_url, headers=cdn_headers, timeout=60)
            response.raise_for_status()
            data = response.json()

            game = data.get('game', {})
            home_team = game.get('homeTeam', {})
            away_team = game.get('awayTeam', {})

            player_stats = []

            # Process home team players
            for player in home_team.get('players', []):
                stats = player.get('statistics', {})
                if not stats:
                    continue
                player_stats.append({
                    "player_id": player.get("personId"),
                    "player_name": player.get("name"),
                    "team_id": home_team.get("teamId"),
                    "team_abbreviation": home_team.get("teamTricode"),
                    "min": stats.get("minutes", ""),
                    "fgm": stats.get("fieldGoalsMade", 0) or 0,
                    "fga": stats.get("fieldGoalsAttempted", 0) or 0,
                    "pts": stats.get("points", 0) or 0,
                    "reb": stats.get("reboundsTotal", 0) or 0,
                    "ast": stats.get("assists", 0) or 0,
                    "stl": stats.get("steals", 0) or 0,
                    "blk": stats.get("blocks", 0) or 0,
                })

            # Process away team players
            for player in away_team.get('players', []):
                stats = player.get('statistics', {})
                if not stats:
                    continue
                player_stats.append({
                    "player_id": player.get("personId"),
                    "player_name": player.get("name"),
                    "team_id": away_team.get("teamId"),
                    "team_abbreviation": away_team.get("teamTricode"),
                    "min": stats.get("minutes", ""),
                    "fgm": stats.get("fieldGoalsMade", 0) or 0,
                    "fga": stats.get("fieldGoalsAttempted", 0) or 0,
                    "pts": stats.get("points", 0) or 0,
                    "reb": stats.get("reboundsTotal", 0) or 0,
                    "ast": stats.get("assists", 0) or 0,
                    "stl": stats.get("steals", 0) or 0,
                    "blk": stats.get("blocks", 0) or 0,
                })

            logger.debug(f"Box score: {len(player_stats)} players from CDN")
            return player_stats

        except Exception as e:
            log_exception(logger, f"Error fetching box score from CDN for game {game_id}", e)
            return []

    def get_play_by_play(self, game_id: str) -> list[dict]:
        """
        Get play-by-play data for a game using CDN endpoint.

        Args:
            game_id: NBA game ID.

        Returns:
            List of play dictionaries with event IDs.
        """
        # Use CDN endpoint which is more reliable
        cdn_url = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"

        try:
            cdn_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Referer': 'https://www.nba.com/',
            }
            response = requests.get(cdn_url, headers=cdn_headers, timeout=60)
            response.raise_for_status()
            data = response.json()

            actions = data.get('game', {}).get('actions', [])
            if not actions:
                logger.warning(f"No actions in CDN response for game {game_id}")
                return []

            plays = []
            for action in actions:
                # Parse clock time from ISO format (PT12M00.00S -> 12:00)
                clock = action.get('clock', 'PT0M0.00S')
                time_str = self._parse_clock_time(clock)

                # Map CDN action types to our event types
                # 2pt, 3pt = made shot (type 1)
                # block = block (type 2 with BLOCK)
                action_type = action.get('actionType', '')
                shot_result = action.get('shotResult', '')

                event_type = 0
                if action_type in ('2pt', '3pt') and shot_result == 'Made':
                    event_type = 1  # Made shot
                elif action_type == 'block':
                    event_type = 2  # Block (treated as missed shot with block)

                plays.append({
                    "event_id": action.get("actionNumber"),
                    "event_type": event_type,
                    "event_action": action.get("subType", ""),
                    "period": action.get("period"),
                    "pctimestring": time_str,
                    "description": action.get("description", ""),
                    "player1_id": action.get("personId"),
                    "player1_name": action.get("playerNameI", ""),
                    "player2_id": action.get("assistPersonId"),
                    "player2_name": action.get("assistPlayerNameInitial", ""),
                })

            return plays
        except Exception as e:
            log_exception(logger, f"Error fetching play-by-play from CDN for game {game_id}", e)
            return []

    def _parse_clock_time(self, clock: str) -> str:
        """
        Parse ISO clock format to MM:SS.

        Args:
            clock: Time string in format PT12M30.00S

        Returns:
            Time string in format 12:30
        """
        try:
            # Remove PT prefix and S suffix
            clock = clock.replace('PT', '').replace('S', '')
            # Split by M
            parts = clock.split('M')
            minutes = int(parts[0]) if parts[0] else 0
            seconds = int(float(parts[1])) if len(parts) > 1 and parts[1] else 0
            return f"{minutes}:{seconds:02d}"
        except Exception:
            return "0:00"

    def get_video_url(self, game_id: str, event_id: int, max_retries: int = 3) -> Optional[str]:
        """
        Get video URL for a specific play event.

        Args:
            game_id: NBA game ID.
            event_id: Play event ID.
            max_retries: Maximum retry attempts.

        Returns:
            Video URL string or None if not available.
        """
        url = f"{self.BASE_URL}/videoeventsasset"
        params = {
            'GameID': game_id,
            'GameEventID': str(event_id),
        }

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 3 * (attempt + 1)  # 6, 9 seconds for retries
                    logger.debug(f"Retry {attempt}/{max_retries} for video in {wait_time}s...")
                    time.sleep(wait_time)

                response = self.session.get(url, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()

                # The video URL is nested in resultSets.Meta.videoUrls
                result_sets = data.get("resultSets", {})
                if isinstance(result_sets, dict):
                    meta = result_sets.get("Meta", {})
                    video_urls = meta.get("videoUrls", [])
                    if video_urls:
                        # Prefer large URL (lurl), fallback to medium (murl) or small (surl)
                        video_url = video_urls[0].get("lurl") or video_urls[0].get("murl") or video_urls[0].get("surl")
                        return video_url

                return None

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout fetching video (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return None
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return None
                # Wait longer on connection errors (likely rate limiting)
                time.sleep(5 * (attempt + 1))
            except Exception as e:
                logger.error(f"Error fetching video for event {event_id}: {e}")
                return None

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
            # Use different headers for video download (videos come from CDN)
            download_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                'Referer': 'https://www.nba.com/',
            }
            response = requests.get(url, headers=download_headers, timeout=30)
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return True
            else:
                logger.error(f"Failed to download video: HTTP {response.status_code}")
                return False
        except Exception as e:
            log_exception(logger, "Error downloading video", e)
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
            logger.debug(f"Fetching video for {category.upper()}: {event.get('description', '')[:50]}...")
            video_url = self.get_video_url(game_id, event_id)

            if video_url:
                if self.download_video(video_url, filepath):
                    stats[category] = stats.get(category, 0) + 1
                    logger.debug(f"Downloaded: {timestamp}.mp4")
                else:
                    stats["failed"] += 1
            else:
                stats["failed"] += 1
                logger.warning(f"No video available for event {event_id}")

            # Rate limiting to avoid API throttling (2 seconds between requests)
            time.sleep(2)

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
