"""
Highlight video maker for NBA player clips.
Concatenates individual play clips with transitions into a final highlight reel.
"""

import os

from src.logger import get_logger, log_exception

# Initialize logger for this module
logger = get_logger("highlights")

try:
    # MoviePy 2.x
    from moviepy import VideoFileClip, concatenate_videoclips
    from moviepy.video.fx import FadeIn, FadeOut
    MOVIEPY_V2 = True
except ImportError:
    # MoviePy 1.x (legacy)
    from moviepy.editor import VideoFileClip, concatenate_videoclips, vfx
    MOVIEPY_V2 = False


class Highlight_Make:
    """Creates highlight videos from individual clip files."""

    def highlight_maker(self, player_name: str, game_date: str, assets_path: str, build_path: str) -> bool:
        """
        Create a highlight video from clips in the player's clips folder.

        Args:
            player_name: Player's name (used for folder path).
            game_date: Game date string (MMDDYYYY format).
            assets_path: Path to assets directory.
            build_path: Path to build directory.

        Returns:
            True if successful, False otherwise.
        """
        clips_folder = f"{build_path}/{game_date}/{player_name}/clips"
        output_path = f"{build_path}/{game_date}/{player_name}/{player_name}.mp4"
        promotion_path = f"{assets_path}/promotion/promotion_ending.mp4"

        # Validate clips folder exists
        if not os.path.exists(clips_folder):
            logger.error(f"Clips folder not found: {clips_folder}")
            return False

        # Read and sort clip files
        try:
            clip_files = os.listdir(clips_folder)
            clip_files = [f for f in clip_files if f.endswith(".mp4")]
        except OSError as e:
            log_exception(logger, f"Failed to read clips folder: {clips_folder}", e)
            return False

        if not clip_files:
            logger.error(f"No clip files found in {clips_folder}")
            return False

        # Sort clips by timestamp (filename is timestamp.mp4)
        try:
            timestamps = []
            for clip_file in clip_files:
                timestamp = int(clip_file.replace(".mp4", ""))
                timestamps.append(timestamp)
            timestamps.sort()
            ordered_clips = [f"{ts}.mp4" for ts in timestamps]
        except ValueError as e:
            log_exception(logger, "Failed to parse clip filenames for sorting", e)
            # Fallback: use original order
            ordered_clips = clip_files
            logger.warning("Using unsorted clip order due to filename parsing error")

        logger.info(f"Processing {len(ordered_clips)} clips for {player_name}")

        # Load and process clips
        loaded_clips = []
        failed_clips = []

        for clip_file in ordered_clips:
            clip_path = f"{clips_folder}/{clip_file}"
            try:
                clip = VideoFileClip(clip_path)

                # Add fade transitions
                if MOVIEPY_V2:
                    clip = clip.with_effects([FadeIn(0.5), FadeOut(0.5)])
                else:
                    clip = clip.fx(vfx.fadein, 0.5).fx(vfx.fadeout, 0.5)

                loaded_clips.append(clip)
                logger.debug(f"Loaded clip: {clip_file}")

            except Exception as e:
                log_exception(logger, f"Failed to load clip: {clip_file}", e)
                failed_clips.append(clip_file)
                continue

        if not loaded_clips:
            logger.error(f"No clips could be loaded for {player_name}")
            return False

        if failed_clips:
            logger.warning(f"{len(failed_clips)} clips failed to load: {failed_clips}")

        # Load promotion ending video
        try:
            if os.path.exists(promotion_path):
                promotion_clip = VideoFileClip(promotion_path)
                loaded_clips.append(promotion_clip)
                logger.debug("Added promotion ending clip")
            else:
                logger.warning(f"Promotion video not found: {promotion_path}")
        except Exception as e:
            log_exception(logger, "Failed to load promotion video", e)
            # Continue without promotion video

        # Concatenate all clips
        try:
            logger.info("Concatenating clips...")
            final_video = concatenate_videoclips(loaded_clips)
        except Exception as e:
            log_exception(logger, "Failed to concatenate clips", e)
            # Clean up loaded clips
            for clip in loaded_clips:
                try:
                    clip.close()
                except Exception:
                    pass
            return False

        # Export final video
        try:
            logger.info(f"Exporting highlight video to {output_path}")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                logger=None,  # Suppress moviepy's own logging
            )
            logger.info(f"Highlight video created successfully: {output_path}")

        except Exception as e:
            log_exception(logger, f"Failed to export highlight video to {output_path}", e)
            return False

        finally:
            # Clean up resources
            try:
                final_video.close()
            except Exception:
                pass
            for clip in loaded_clips:
                try:
                    clip.close()
                except Exception:
                    pass

        return True
