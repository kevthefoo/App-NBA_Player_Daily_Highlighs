"""
NBA Player Daily Highlights Automation System

Fetches NBA game data via API, downloads player highlight clips,
assembles highlight reels, generates thumbnails, and uploads to YouTube.
"""

import argparse
import json
import time
import os
import sys
from datetime import datetime, timedelta
from pytz import timezone
from dotenv import load_dotenv

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def safe_print(text: str) -> None:
    """Print text with safe Unicode handling for Windows console."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))

from src.data.nba_api_scraper import NBADataScraper, get_highlight_players
from src import config

from src.video.highlights_maker import Highlight_Make
from src.video.thumbnail_maker import make_thumbnail
from src.video.upload_video import YouTubeUploader


def setup_directories(build_path: str, game_date: str) -> None:
    """Create necessary directories for the build."""
    os.makedirs(f"{build_path}/{game_date}", exist_ok=True)

    # Create completed players tracking file
    completed_file = f"{build_path}/{game_date}/completed_player.txt"
    if not os.path.exists(completed_file):
        with open(completed_file, "w") as f:
            pass


def get_completed_players(build_path: str, game_date: str) -> set:
    """Get set of already processed player names."""
    try:
        with open(f"{build_path}/{game_date}/completed_player.txt", "r") as f:
            return set(line.strip() for line in f.readlines() if line.strip())
    except FileNotFoundError:
        return set()


def mark_player_completed(build_path: str, game_date: str, player_name: str) -> None:
    """Mark a player as completed."""
    with open(f"{build_path}/{game_date}/completed_player.txt", "a") as f:
        f.write(f"{player_name}\n")


def process_player(
    scraper: NBADataScraper,
    game_info: dict,
    player: dict,
    game_date: str,
    game_date_readable: str,
    assets_path: str,
    build_path: str,
    hm: Highlight_Make,
    uploader: YouTubeUploader,
) -> None:
    """Process a single player: download clips, make highlight video, upload to YouTube."""

    player_name = player["player_name"]
    player_id = player["player_id"]

    print(f"\n{'='*60}")
    print(f"Processing: {player_name}")
    print(f"Stats: {player['pts']} PTS / {player['reb']} REB / {player['ast']} AST")
    print(f"{'='*60}")

    # Create player directories
    player_path = f"{build_path}/{game_date}/{player_name}"
    os.makedirs(f"{player_path}/clips", exist_ok=True)

    start_time = time.time()

    # Download highlight clips
    print("\nDownloading highlight clips...")
    download_stats = scraper.download_player_highlights(
        game_id=game_info["game_id"],
        player_id=player_id,
        player_name=player_name,
        game_date=game_date,
        build_path=build_path,
        fgm_count=player["fgm"],
        ast_count=player["ast"],
        blk_count=player["blk"],
    )

    print(f"\nDownload complete: FGM={download_stats['fgm']}, AST={download_stats['ast']}, BLK={download_stats['blk']}, Failed={download_stats['failed']}")

    # Check if we have any clips
    clips_path = f"{player_path}/clips"
    clip_files = [f for f in os.listdir(clips_path) if f.endswith(".mp4")]

    if not clip_files:
        print(f"No clips downloaded for {player_name}, skipping...")
        return

    # Create highlight video
    print("\nCreating highlight video...")
    hm.highlight_maker(player_name, game_date, assets_path, build_path)

    # Create thumbnail
    print("\nCreating thumbnail...")
    make_thumbnail(
        player_name=player_name,
        player_id=player_id,
        pts_data=player["pts"],
        reb_data=player["reb"],
        ast_data=player["ast"],
        away_team=game_info["away_team"],
        home_team=game_info["home_team"],
        game_date=game_date,
        game_date_readable=game_date_readable,
        assets_path=assets_path,
        build_path=build_path,
    )

    # Upload to YouTube
    print("\nUploading to YouTube...")
    yt_title = f"NBA - {player_name} Highlights - {game_info['away_team']} vs {game_info['home_team']} - {game_date_readable}"

    uploader.upload_video(
        player_name=player_name,
        away_team=game_info["away_team"],
        home_team=game_info["home_team"],
        title=yt_title,
        game_date=game_date,
        build_path=build_path,
    )

    end_time = time.time()

    # Write log
    with open(f"{player_path}/log.txt", "a", encoding="utf-8") as f:
        f.write("The title for Youtube:\n")
        f.write(f"{yt_title}\n\n")
        f.write(f"Stats: {player['pts']} PTS / {player['reb']} REB / {player['ast']} AST\n\n")
        f.write(f"{game_info['away_team']} @ {game_info['home_team']}\n")
        f.write(f"{game_date_readable}\n\n")
        f.write(f"Processing time: {int(end_time - start_time)} seconds\n")
        f.write(f"Clips downloaded: FGM={download_stats['fgm']}, AST={download_stats['ast']}, BLK={download_stats['blk']}\n")

    print(f"\nCompleted {player_name} in {int(end_time - start_time)} seconds")


def main():
    """Main entry point."""
    load_dotenv()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="NBA Player Daily Highlights Automation")
    parser.add_argument(
        "--date",
        type=str,
        help="Game date in YYYY-MM-DD format (default: yesterday)",
    )
    args = parser.parse_args()

    # Initialize paths
    basepath = os.path.dirname(__file__)
    assets_path = os.path.abspath(os.path.join(basepath, "assets"))
    build_path = os.path.abspath(os.path.join(basepath, "build"))

    # Get game date (default to yesterday in EST)
    tz = timezone("EST")
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=tz)
    else:
        target_date = datetime.now(tz) - timedelta(days=1)

    today_date = target_date.strftime("%Y-%m-%d")
    game_date = target_date.strftime("%m%d%Y")
    game_date_readable = target_date.strftime("%m/%d/%Y")

    print(f"NBA Player Daily Highlights")
    print(f"Date: {game_date_readable}")
    print(f"{'='*60}\n")

    # Setup directories
    setup_directories(build_path, game_date)

    # Initialize components
    scraper = NBADataScraper(game_date=today_date)
    hm = Highlight_Make()
    uploader = YouTubeUploader()
    print("Authenticating with YouTube API...")
    uploader.authenticate()

    # Get today's games
    print("\nFetching today's games...")
    games = scraper.get_games()

    if not games:
        print("No games found for today.")
        return

    print(f"Found {len(games)} games\n")

    # Get completed players
    completed_players = get_completed_players(build_path, game_date)

    # Process each game
    for game in games:
        print(f"\n{'='*60}")
        print(f"Game: {game['away_team']} @ {game['home_team']}")
        print(f"Game ID: {game['game_id']} | Status ID: {game.get('status', 'Unknown')}")
        print(f"{'='*60}")

        # Skip games that haven't finished yet
        game_status = game.get('status', '')
        if game_status !=3:
            print(f"Skipping - game not finished yet (status: {game.get('status', 'Unknown')})")
            continue

        # Get players who qualify for highlights
        print("\nFetching box score...")
        highlight_players = get_highlight_players(
            game_id=game["game_id"],
            scraper=scraper,
            algorithm_func=config.algorithm,
        )

        if not highlight_players:
            print("No players qualify for highlights in this game.")
            continue

        print(f"\nFound {len(highlight_players)} players qualifying for highlights:")
        for p in highlight_players:
            status = "(already done)" if p["player_name"] in completed_players else ""
            print(f"  - {p['player_name']}: {p['pts']} PTS / {p['reb']} REB / {p['ast']} AST {status}")

        # Process each qualifying player
        for player in highlight_players:
            if player["player_name"] in completed_players:
                print(f"\nSkipping {player['player_name']} (already processed)")
                continue

            try:
                process_player(
                    scraper=scraper,
                    game_info=game,
                    player=player,
                    game_date=game_date,
                    game_date_readable=game_date_readable,
                    assets_path=assets_path,
                    build_path=build_path,
                    hm=hm,
                    uploader=uploader,
                )
                mark_player_completed(build_path, game_date, player["player_name"])
            except Exception as e:
                print(f"\nError processing {player['player_name']}: {e}")
                continue

    print(f"\n{'='*60}")
    print("All tasks completed!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
