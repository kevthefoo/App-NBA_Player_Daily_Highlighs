# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NBA Player Daily Highlights Automation System - fetches NBA game data via the official NBA Stats API, downloads player highlight clips based on performance metrics (PTS+REB+AST > 35), assembles highlight reels with transitions, generates thumbnails, and uploads to YouTube automatically.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run main automation (processes all games from current date)
python main.py

# Run manual/interactive mode (for testing single players)
python src/manual.py
```

## Required Environment Variables (.env file)

```
YOUTUBE_CHANNEL_ID=your_channel_id_here
```

## Architecture

### Entry Point
- `main.py` - Orchestrates entire workflow: fetches data via API → downloads clips → assembles videos → creates thumbnails → uploads to YouTube

### Data Fetching (`src/data/`)
- `nba_api_scraper.py` (NBADataScraper class) - Uses `nba_api` package to:
  - Get today's games from ScoreboardV2
  - Get box scores from BoxScoreTraditionalV2
  - Get play-by-play data from PlayByPlayV2
  - Get video URLs from VideoEventsAsset
  - Download video clips via HTTP requests

### Video Processing (`src/video/`)
- `highlights_maker.py` (Highlight_Make class) - Concatenates clips with fade transitions, appends promotion video
- `thumbnail_maker.py` (make_thumbnail function) - Generates 1920x1080 thumbnails with player photo from NBA CDN, stats, game info
- `upload_video.py` (Upload_Video class) - Automates YouTube Studio upload via Selenium (only part using browser automation)

### Supporting Files
- `src/config.py` - Performance threshold algorithm (pts + reb + ast > 35)
- `assets/information/team_info.json` - NBA team abbreviation mappings

## Key Implementation Details

### Data Sources
- **Game Data**: `nba_api.stats.endpoints.ScoreboardV2`
- **Box Scores**: `nba_api.stats.endpoints.BoxScoreTraditionalV2`
- **Play-by-Play**: `nba_api.stats.endpoints.PlayByPlayV2`
- **Video URLs**: `nba_api.stats.endpoints.VideoEventsAsset`
- **Player Headshots**: `https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png`

### Timestamp Calculation (for sorting clips)
- Regular time: `720 * quarter - 60 * minute - second`
- Overtime: `720 * 4 + 300 * (quarter-4) - 60 * minute - second`

### Build Output Structure
```
build/{MMDDYYYY}/{player_name}/
├── clips/           # Individual play clips named by timestamp
├── {player}.mp4     # Final highlight reel
├── thumbnail.png    # YouTube thumbnail
└── log.txt          # Processing log
```

### Scheduling
- Windows: Task Scheduler
- Linux: Crontab (e.g., `30 8 * * * export DISPLAY=:1; python /path/to/main.py`)

## Dependencies

- `nba_api` - Official NBA Stats API wrapper
- `moviepy` - Video editing and concatenation
- `Pillow` - Thumbnail image generation
- `selenium` - YouTube upload automation only
- `requests` - HTTP requests for video downloads
- `pytz` - Timezone handling
- `python-dotenv` - Environment variable management
