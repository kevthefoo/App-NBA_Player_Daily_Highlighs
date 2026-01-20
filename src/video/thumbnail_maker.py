"""
Thumbnail generator for NBA highlight videos.
Creates 1920x1080 thumbnails with player photo, stats, and game info.
"""

import os
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

from src.logger import get_logger, log_exception

# Initialize logger for this module
logger = get_logger("thumbnail")


def make_thumbnail(
    player_name: str,
    player_id: int,
    pts_data: int,
    reb_data: int,
    ast_data: int,
    away_team: str,
    home_team: str,
    game_date: str,
    game_date_readable: str,
    assets_path: str,
    build_path: str,
) -> bool:
    """
    Generate a thumbnail image for a player's highlight video.

    Args:
        player_name: Player's full name.
        player_id: NBA player ID for headshot URL.
        pts_data: Points scored.
        reb_data: Rebounds.
        ast_data: Assists.
        away_team: Away team name.
        home_team: Home team name.
        game_date: Date string for folder (MMDDYYYY format).
        game_date_readable: Date string for display (MM/DD/YYYY format).
        assets_path: Path to assets directory.
        build_path: Path to build directory.

    Returns:
        True if successful, False otherwise.
    """
    output_path = f"{build_path}/{game_date}/{player_name}/thumbnail.png"

    # Get player headshot directly from NBA CDN
    player_pfp_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

    try:
        logger.debug(f"Fetching player headshot for {player_name} (ID: {player_id})")
        response = requests.get(player_pfp_url, timeout=10)
        if response.status_code == 200:
            player_photo = Image.open(BytesIO(response.content))
            logger.debug("Player headshot loaded successfully")
        else:
            # Fallback: create a placeholder if headshot not available
            logger.warning(f"Could not fetch player headshot (HTTP {response.status_code}), using placeholder")
            player_photo = Image.new("RGBA", (1040, 760), (128, 128, 128, 255))
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching player headshot for {player_name}, using placeholder")
        player_photo = Image.new("RGBA", (1040, 760), (128, 128, 128, 255))
    except Exception as e:
        log_exception(logger, f"Error fetching player headshot for {player_name}", e)
        player_photo = Image.new("RGBA", (1040, 760), (128, 128, 128, 255))

    # Define asset paths
    mask_path = f"{assets_path}/thumbnail/mask/mask1.png"
    background_path = f"{assets_path}/thumbnail/background/background1.png"
    font_path = f"{assets_path}/thumbnail/font/Audiowide-Regular.ttf"

    # Validate required assets exist
    missing_assets = []
    if not os.path.exists(mask_path):
        missing_assets.append(f"mask: {mask_path}")
    if not os.path.exists(background_path):
        missing_assets.append(f"background: {background_path}")
    if not os.path.exists(font_path):
        missing_assets.append(f"font: {font_path}")

    if missing_assets:
        logger.error(f"Missing required assets for thumbnail: {missing_assets}")
        return False

    try:
        # Import mask and background
        mask = Image.open(mask_path)
        background = Image.open(background_path)
        logger.debug("Loaded mask and background images")

        # Resize the player photo to 1478x1080
        player_photo = player_photo.resize((1478, 1080))

        # Create a new canvas
        blank = Image.new("RGBA", (1920, 1080))

        # Paste the player's photos on the right part of the canvas
        blank.paste(player_photo, (700, 0))

        # Composite the background, player's photo and mask
        thumbnail = Image.alpha_composite(Image.alpha_composite(background, blank), mask)

        # Text part
        thumbnail_text = ImageDraw.Draw(thumbnail)

        # Load fonts
        try:
            data_font = ImageFont.truetype(font_path, size=150)
            title_font = ImageFont.truetype(font_path, size=85)
            game_info_font = ImageFont.truetype(font_path, size=60)
        except Exception as e:
            log_exception(logger, "Failed to load fonts", e)
            return False

        # Write the player's game data (PTS/REB/AST)
        line_height_data = 150 + 50  # font size + spacing
        thumbnail_text.text((30, 0), str(pts_data), fill=(0, 0, 0), font=data_font)
        thumbnail_text.text((30, line_height_data), str(reb_data), fill=(0, 0, 0), font=data_font)
        thumbnail_text.text((30, line_height_data * 2), str(ast_data), fill=(0, 0, 0), font=data_font)

        thumbnail_text.text((300, 0), "PTS", fill=(0, 0, 0), font=data_font)
        thumbnail_text.text((300, line_height_data), "REB", fill=(0, 0, 0), font=data_font)
        thumbnail_text.text((300, line_height_data * 2), "AST", fill=(0, 0, 0), font=data_font)

        # Write the player's name
        line_height_title = 85 + 20  # font size + spacing
        thumbnail_text.text((60, 610), player_name, fill=(0, 0, 0), font=title_font)
        thumbnail_text.text((60, 610 + line_height_title), "Highlights", fill=(0, 0, 0), font=title_font)

        # Write the game's info
        line_height_info = 60 + 10  # font size + small spacing
        thumbnail_text.text((100, 900), f"{away_team} @ {home_team}", fill=(0, 0, 0), font=game_info_font)
        thumbnail_text.text((100, 900 + line_height_info), game_date_readable, fill=(0, 0, 0), font=game_info_font)

        # Save the thumbnail
        thumbnail.save(output_path)
        logger.info(f"Thumbnail created successfully: {output_path}")
        return True

    except Exception as e:
        log_exception(logger, f"Failed to create thumbnail for {player_name}", e)
        return False
