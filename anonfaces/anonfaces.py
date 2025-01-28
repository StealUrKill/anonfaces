#!/usr/bin/env python3

import argparse
import json
import mimetypes
import shutil
import signal
from io import BytesIO
from typing import Dict, Optional, Tuple

import cv2
import ffmpeg
import imageio.plugins.ffmpeg
import numpy as np
import skimage.draw
from moviepy.editor import *
from pedalboard import *
from pedalboard.io import AudioFile
from PIL import Image
from tqdm import tqdm

try:
    from centerface import CenterFace  # Import when running as a standalone script
except ImportError:
    from anonfaces.centerface import CenterFace  # Import when used as a library

# Global flag to indicate when to stop processing
stop_ffmpeg = False


def signal_handler(signum, frame):
    """
    Signal handler function to handle interruption signals (e.g., Ctrl+C).
    Sets the global 'stop_ffmpeg' flag to True to signal that processing should stop.
    """
    global stop_ffmpeg
    stop_ffmpeg = True
    # Write messages to the console using tqdm to avoid interfering with progress bars
    tqdm.write("")  # Add an empty line for spacing
    tqdm.write("Stop signal received, stopping cleanly...")
    tqdm.write("")  # Add another empty line for spacing


# Register the signal handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)


def scale_bb(x1, y1, x2, y2, mask_scale=1.0):
    """
    Scales a bounding box by a given mask_scale factor.

    Parameters:
    - x1, y1: Coordinates of the top-left corner of the bounding box.
    - x2, y2: Coordinates of the bottom-right corner of the bounding box.
    - mask_scale: Scaling factor for the bounding box. Default is 1.0 (no scaling).

    Returns:
    - A NumPy array containing the scaled bounding box coordinates [x1, y1, x2, y2], rounded to integers.
    """
    if mask_scale == 1.0:
        # No scaling needed; return original coordinates
        return np.array([x1, y1, x2, y2], dtype=int)

    # Calculate the amount to expand or shrink the bounding box
    scale_offset = (mask_scale - 1.0) / 2.0

    # Compute the width and height of the original bounding box
    width = x2 - x1
    height = y2 - y1

    # Adjust the bounding box coordinates based on the scaling factor
    x1 -= width * scale_offset
    y1 -= height * scale_offset
    x2 += width * scale_offset
    y2 += height * scale_offset

    # Round the coordinates to the nearest integer
    return np.round([x1, y1, x2, y2]).astype(int)


def draw_det(
    frame,
    score,
    det_idx,
    x1,
    y1,
    x2,
    y2,
    replacewith: str = "blur",
    ellipse: bool = True,
    draw_scores: bool = False,
    ovcolor: Tuple[int, int, int] = (0, 0, 0),
    replaceimg=None,
    mosaicsize: int = 20,
):
    """
    Applies an anonymization effect to a detected bounding box in the frame.

    Parameters:
    - frame: The image frame (NumPy array) to modify.
    - score: The confidence score of the detection.
    - det_idx: The index of the detection (not used in this function).
    - x1, y1: Coordinates of the top-left corner of the bounding box.
    - x2, y2: Coordinates of the bottom-right corner of the bounding box.
    - replacewith: Method of anonymization ('solid', 'blur', 'img', 'mosaic', 'none').
    - ellipse: If True, apply effects within an elliptical mask inside the bounding box.
    - draw_scores: If True, draw the detection score near the bounding box.
    - ovcolor: Color for 'solid' replacement (BGR tuple).
    - replaceimg: Image to use for 'img' replacement (NumPy array).
    - mosaicsize: Size of mosaic blocks for 'mosaic' replacement.

    Returns:
    - None. The function modifies the frame in place.
    """
    if replacewith == "solid":
        # Draw a solid rectangle over the bounding box area with the specified color
        cv2.rectangle(frame, (x1, y1), (x2, y2), ovcolor, -1)
    elif replacewith == "blur":
        # Blur the bounding box area
        bf = 2  # Blur factor (number of pixels in each dimension that the face will be reduced to)
        # Apply blur to the ROI (Region of Interest)
        blurred_box = cv2.blur(frame[y1:y2, x1:x2], (abs(x2 - x1) // bf, abs(y2 - y1) // bf))
        if ellipse:
            # If ellipse is True, apply the effect within an elliptical mask
            roibox = frame[y1:y2, x1:x2]
            # Get y and x coordinate lists of the "bounding ellipse"
            ey, ex = skimage.draw.ellipse((y2 - y1) // 2, (x2 - x1) // 2, (y2 - y1) // 2, (x2 - x1) // 2)
            # Apply the blurred effect within the ellipse
            roibox[ey, ex] = blurred_box[ey, ex]
            # Update the frame with the modified ROI
            frame[y1:y2, x1:x2] = roibox
        else:
            # Replace the ROI in the frame with the blurred version
            frame[y1:y2, x1:x2] = blurred_box
    elif replacewith == "img":
        # Replace the bounding box area with a provided image
        target_size = (x2 - x1, y2 - y1)
        # Resize the replacement image to match the target size
        resized_replaceimg = cv2.resize(replaceimg, target_size)
        if replaceimg.shape[2] == 3:  # RGB
            # Replace the ROI in the frame with the resized image
            frame[y1:y2, x1:x2] = resized_replaceimg
        elif replaceimg.shape[2] == 4:  # RGBA
            # Handle images with an alpha channel
            alpha_channel = resized_replaceimg[:, :, 3:] / 255
            color_img = resized_replaceimg[:, :, :3]
            roi = frame[y1:y2, x1:x2]
            # Blend the replacement image with the ROI using the alpha channel
            frame[y1:y2, x1:x2] = roi * (1 - alpha_channel) + color_img * alpha_channel
    elif replacewith == "mosaic":
        # Apply a mosaic effect to the bounding box area
        for y in range(y1, y2, mosaicsize):
            for x in range(x1, x2, mosaicsize):
                pt1 = (x, y)
                pt2 = (min(x2, x + mosaicsize - 1), min(y2, y + mosaicsize - 1))
                # Get the color from the top-left pixel of the block
                color = (int(frame[y, x][0]), int(frame[y, x][1]), int(frame[y, x][2]))
                # Draw the mosaic block with the selected color
                cv2.rectangle(frame, pt1, pt2, color, -1)
    elif replacewith == "none":
        # Do nothing; leave the bounding box area unchanged
        pass
    if draw_scores:
        # Draw the detection score near the bounding box
        cv2.putText(frame, f"{score:.2f}", (x1 + 0, y1 - 20), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 0))


def anonymize_frame(dets, frame, mask_scale, replacewith, ellipse, draw_scores, replaceimg, mosaicsize):
    """
    Applies anonymization effects to detected faces in a frame.

    Parameters:
    - dets: List of detections, where each detection is an array containing bounding box coordinates and a confidence score.
    - frame: The image frame (NumPy array) to modify.
    - mask_scale: Scaling factor for the bounding boxes.
    - replacewith: Method of anonymization ('solid', 'blur', 'img', 'mosaic', 'none').
    - ellipse: If True, apply effects within an elliptical mask inside the bounding box.
    - draw_scores: If True, draw the detection scores near the bounding boxes.
    - replaceimg: Image to use for 'img' replacement (NumPy array).
    - mosaicsize: Size of mosaic blocks for 'mosaic' replacement.

    Returns:
    - None. The function modifies the frame in place.
    """
    for i, det in enumerate(dets):
        # Extract bounding box coordinates and score from the detection
        boxes, score = det[:4], det[4]
        x1, y1, x2, y2 = boxes.astype(int)

        # Scale the bounding box according to mask_scale
        x1, y1, x2, y2 = scale_bb(x1, y1, x2, y2, mask_scale)

        # Clip bounding box coordinates to valid frame region
        y1, y2 = max(0, y1), min(frame.shape[0] - 1, y2)
        x1, x2 = max(0, x1), min(frame.shape[1] - 1, x2)

        # Apply the anonymization effect to the bounding box area
        draw_det(
            frame,
            score,
            i,
            x1,
            y1,
            x2,
            y2,
            replacewith=replacewith,
            ellipse=ellipse,
            draw_scores=draw_scores,
            replaceimg=replaceimg,
            mosaicsize=mosaicsize,
        )


def cam_read_iter(reader):
    """
    Generator function to continuously read frames from a camera or video reader.

    Parameters:
    - reader: An object with a method `get_next_data()` that returns the next frame.

    Yields:
    - Next frame from the reader.
    """
    while True:
        # Yield the next frame from the reader
        yield reader.get_next_data()


def get_video_metadata(ipath):
    """
    Retrieves metadata from a video file using FFmpeg.

    Parameters:
    - ipath: Path to the input video file.

    Returns:
    - metadata: A dictionary containing video metadata such as bit rate, pixel format, dimensions, codec name, average frame rate, duration, and whether it has an audio stream.
      Returns None if no video stream is found or an error occurs.
    """
    try:
        # Probe the video file to get metadata
        probe = ffmpeg.probe(ipath)

        # Extract video streams from the probe data
        video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]

        if not video_streams:
            print(f"No video stream found in {ipath}")
            return None

        # Get the first video stream
        video_stream = video_streams[0]

        # Build the metadata dictionary
        metadata = {
            "bit_rate": int(video_stream.get("bit_rate", 0)),
            "pix_fmt": video_stream.get("pix_fmt", ""),
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "codec_name": video_stream.get("codec_name", ""),
            "avg_frame_rate": video_stream.get("avg_frame_rate", "0/0"),
            "duration": float(video_stream.get("duration", 0.0)),
        }

        # Check for audio streams
        audio_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "audio"]
        metadata["has_audio"] = len(audio_streams) > 0

        return metadata

    except ffmpeg.Error as e:
        # Handle exceptions and print the error message
        print(f"Error retrieving metadata from {ipath}: {e.stderr.decode()}")
        return None


def video_detect(
    ipath: str,
    opath: str,
    centerface: CenterFace,
    threshold: float,
    enable_preview: bool,
    cam: bool,
    nested: bool,
    replacewith: str,
    mask_scale: float,
    ellipse: bool,
    draw_scores: bool,
    ffmpeg_config: Dict[str, str],
    replaceimg=None,
    keep_audio: bool = False,
    copy_acodec: bool = False,
    mosaicsize: int = 20,
    show_ffmpeg_config: bool = False,
    show_ffmpeg_command: bool = False,
    min_faces: int = 4,  # Add a parameter for the minimum number of faces
):
    metadata = get_video_metadata(ipath)
    if metadata is None:
        print(f"Could not retrieve metadata from {ipath}")
        return

    # Extract metadata values
    bit_rate = metadata["bit_rate"]
    pix_fmt = metadata["pix_fmt"]
    has_audio = metadata["has_audio"]

    # Handle camera input
    if cam:
        cap = cv2.VideoCapture(0)  # Adjust camera index if necessary
    else:
        cap = cv2.VideoCapture(ipath)

    if not cap.isOpened():
        if cam:
            tqdm.write(f"Could not open camera device. Please check your camera connection.")
        else:
            tqdm.write(f"Could not open file {ipath} as a video file with OpenCV. Skipping file...")
        return

    try:
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    except Exception as e:
        tqdm.write(f"Error retrieving video properties: {e}")
        return

    if fps <= 0 or fps > 120:
        fps = 30  # Default to 30 fps if fps is invalid

    # Adjust progress bar
    if nested and not cam:
        bar = tqdm(total=frame_count, position=1, leave=True, dynamic_ncols=True)
    else:
        bar = tqdm(position=1, leave=True, dynamic_ncols=True) if nested else tqdm(dynamic_ncols=True)

    # Prepare ffmpeg_config
    _ffmpeg_config = ffmpeg_config.copy()
    _ffmpeg_config["fps"] = fps
    _ffmpeg_config.setdefault("ffmpeg_log_level", "panic")
    _ffmpeg_config.setdefault("ffmpeg_params", [])
    _ffmpeg_config["ffmpeg_params"].extend(["-map_metadata", "0", "-map", "0"])

    common_pix_fmts = ["yuv420p", "yuvj420p", "nv12"]
    if pix_fmt in common_pix_fmts:
        _ffmpeg_config["ffmpeg_params"].extend(["-pix_fmt", pix_fmt])
    else:
        _ffmpeg_config["ffmpeg_params"].extend(["-pix_fmt", "yuv420p"])

    if bit_rate:
        bitrate_kbps = bit_rate // 1000
        _ffmpeg_config["bitrate"] = f"{bitrate_kbps}k"
    else:
        # Set default bitrate if extraction fails
        _ffmpeg_config["bitrate"] = "2000k"

    # Adjust Encoding Settings
    _ffmpeg_config["codec"] = "libx264"  # Ensure using H.264 codec
    _ffmpeg_config["ffmpeg_params"].extend(
        [
            "-preset",
            "slow",
            "-profile:v",
            "baseline",  # Match input video's profile
            "-level",
            "3.1",  # Set level if needed
        ]
    )

    # Handle audio settings
    if keep_audio and has_audio:
        _ffmpeg_config["audio_path"] = ipath
        if copy_acodec:
            _ffmpeg_config["audio_codec"] = "copy"
        else:
            _ffmpeg_config["audio_codec"] = "aac"
            _ffmpeg_config["audio_bitrate"] = "128k"

    if show_ffmpeg_config:
        tqdm.write(f"FFMPEG Config: {_ffmpeg_config}")
        tqdm.write("")

    # Construct and display FFmpeg command
    if show_ffmpeg_command:
        ffmpeg_command = (
            f"ffmpeg -y -loglevel {_ffmpeg_config['ffmpeg_log_level']} "
            f"-f rawvideo -vcodec rawvideo -s {frame_width}x{frame_height} -pix_fmt rgb24 -r {_ffmpeg_config['fps']} -i - "
        )
        if "audio_path" in _ffmpeg_config:
            ffmpeg_command += f"-i {_ffmpeg_config['audio_path']} "
        ffmpeg_command += f"-an -vcodec {_ffmpeg_config['codec']} "
        if "bitrate" in _ffmpeg_config:
            ffmpeg_command += f"-b:v {_ffmpeg_config['bitrate']} "
        if "ffmpeg_params" in _ffmpeg_config:
            params = " ".join(_ffmpeg_config["ffmpeg_params"])
            ffmpeg_command += f"{params} "
        if "audio_codec" in _ffmpeg_config:
            ffmpeg_command += f"-c:a {_ffmpeg_config['audio_codec']} "
            if "audio_bitrate" in _ffmpeg_config:
                ffmpeg_command += f"-b:a {_ffmpeg_config['audio_bitrate']} "
        ffmpeg_command += f"{opath}"
        tqdm.write(f"FFMPEG Command: {ffmpeg_command}")
        tqdm.write("")

    # Start processing frames
    # variables for face counting
    total_faces_detected = 0
    processed_frames = []  # We'll store processed frames temporarily
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if stop_ffmpeg:
            break

        # Process frame
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        dets, _ = centerface(frame_rgb, threshold=threshold)

        # Count the faces detected in this frame
        face_count = len(dets)
        total_faces_detected += face_count

        if face_count > 0:
            anonymize_frame(
                dets,
                frame_rgb,
                mask_scale=mask_scale,
                replacewith=replacewith,
                ellipse=ellipse,
                draw_scores=draw_scores,
                replaceimg=replaceimg,
                mosaicsize=mosaicsize,
            )

        frame_rgb = np.clip(frame_rgb, 0, 255).astype(np.uint8)
        processed_frames.append(frame_rgb)

        if enable_preview:
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            cv2.imshow("Preview of anonymization results (quit by pressing Q or Escape)", frame_bgr)
            if cv2.waitKey(1) & 0xFF in [ord("q"), 27]:
                cv2.destroyAllWindows()
                break

        bar.update(1)

    cap.release()
    bar.close()

    # After processing all frames, decide whether to write the anonymized video or return original
    if total_faces_detected < min_faces:
        tqdm.write(f"Total faces detected ({total_faces_detected}) is less than {min_faces}. Returning original video.")
        # If user wants output, just copy the original input file to the output
        writer = None  # writer was never created before counting, so no need to close
        # Just copy input to output
        shutil.copy(ipath, opath)

    else:
        # We have enough faces, write the anonymized video now
        # Prepare writer now that we know we want to produce anonymized output
        writer = imageio.get_writer(opath, format="FFMPEG", mode="I", **_ffmpeg_config)
        for f_rgb in processed_frames:
            writer.append_data(f_rgb)
        writer.close()


EXTRACTED_AUDIO = "extracted_audio.wav"
DISTORTED_AUDIO = "distorted_audio.wav"


def extract_audio_from_video(v_path: str, a_path: str):
    """
    Extracts the audio track from a video file and saves it as an audio file.

    Parameters:
    - v_path: Path to the input video file.
    - a_path: Path where the extracted audio file will be saved.

    Returns:
    - None
    """
    video = VideoFileClip(v_path)
    video.audio.write_audiofile(a_path)


def distort_audio(audio_input: str, audio_output: str, sample_rate: float = 44100.0):
    """
    Applies distortion effects to an audio file and saves the processed audio.

    Parameters:
    - audio_input: Path to the input audio file.
    - audio_output: Path where the distorted audio file will be saved.
    - sample_rate: The sample rate to use for processing (default: 44100.0 Hz).

    Returns:
    - None
    """
    # Read the audio file and resample if necessary
    with AudioFile(audio_input).resampled_to(sample_rate) as f:
        audio = f.read(f.frames)

    # Define the audio effects to apply
    board = Pedalboard(
        [
            Gain(gain_db=5),
            PitchShift(semitones=-2.5),
        ]
    )

    # Apply the effects to the audio
    d_audio = board(audio, sample_rate)

    # Write the processed audio to the output file
    with AudioFile(audio_output, "w", sample_rate, d_audio.shape[0]) as f:
        f.write(d_audio)


def combine_video_audio(v_path: str, a_path: str, o_path: str):
    """
    Combines a video file with an audio file, replacing the video's original audio.

    Parameters:
    - v_path: Path to the input video file.
    - a_path: Path to the input audio file.
    - o_path: Path where the output video file will be saved.

    Returns:
    - None
    """
    # Load the video and audio clips
    vclip = VideoFileClip(v_path)
    aclip = AudioFileClip(a_path)

    # Set the video's audio to the new audio clip
    vclip.audio = aclip

    # Write the combined video to the output file
    vclip.write_videofile(o_path, codec="libx264", logger=None)


def distort_now(ipath: str, opath: str):
    """
    Processes a video file by distorting its audio track and saving the result.

    Parameters:
    - ipath: Path to the input video file.
    - opath: Path to the original output video file (before distortion).

    Returns:
    - None
    """
    # Add "_distorted" to the output file name
    root, ext = os.path.splitext(opath)
    dopath = f"{root}_distorted{ext}"

    # Copy the original output video to the new distorted output path
    shutil.copy(opath, dopath)

    # Extract audio from the original video
    extract_audio_from_video(ipath, EXTRACTED_AUDIO)

    # Distort the extracted audio
    distort_audio(EXTRACTED_AUDIO, DISTORTED_AUDIO)

    # Combine the processed audio with the copied video
    combine_video_audio(opath, DISTORTED_AUDIO, dopath)

    # Remove temporary audio files
    os.remove(EXTRACTED_AUDIO)
    os.remove(DISTORTED_AUDIO)


def image_detect(
    image_bytes: bytes,
    centerface: CenterFace,
    threshold: float,
    replacewith: str,
    mask_scale: float,
    ellipse: bool,
    draw_scores: bool,
    enable_preview: bool,
    keep_metadata: bool,
    replaceimg=None,
    mosaicsize: int = 20,
    input_format: Optional[str] = None,
    min_faces: int = 1,
):
    """
    Detects faces in an image and applies anonymization effects.

    Parameters:
    - image_bytes: The image data in bytes.
    - centerface: An instance of the CenterFace face detection model.
    - threshold: The confidence threshold for face detection.
    - replacewith: The anonymization method ('solid', 'blur', 'img', 'mosaic', 'none').
    - mask_scale: Scaling factor for the bounding boxes.
    - ellipse: If True, apply effects within an elliptical mask inside the bounding box.
    - draw_scores: If True, draw the detection scores near the bounding boxes.
    - enable_preview: If True, display a preview window showing the anonymized image.
    - keep_metadata: If True, preserve the original image metadata.
    - replaceimg: Image to use for 'img' replacement (NumPy array or PIL Image).
    - mosaicsize: Size of mosaic blocks for 'mosaic' replacement.
    - input_format: The format of the input image (e.g., 'JPEG', 'PNG'). If None, it will be inferred.
    - min_faces: The minimum number of faces that must be detected in the image. If the number of faces found is less than this value, the image will not be modified.

    Returns:
    - output_image_bytes: The anonymized image data in bytes.
    """
    # Read the image from bytes using PIL to preserve metadata
    pil_image = Image.open(BytesIO(image_bytes))

    # Determine the input image format
    if input_format is None:
        input_format = pil_image.format
        if input_format is None:
            raise ValueError("Input image format could not be determined. Please provide the 'input_format' parameter.")

    # Collect all metadata
    info = pil_image.info.copy()

    # Preserve XMP data if present
    if "XML:com.adobe.xmp" in pil_image.info:
        info["xml"] = pil_image.info["XML:com.adobe.xmp"]
    elif "xmp" in pil_image.info:
        info["xmp"] = pil_image.info["xmp"]

    # Convert PIL image to OpenCV format (NumPy array)
    frame_rgb = np.array(pil_image.convert("RGB"))

    # Perform face detection
    dets, _ = centerface(frame_rgb, threshold=threshold)

    # Count the number of detected faces
    face_count = len(dets)

    # If the number of faces is below the desired threshold, return the original image
    if face_count < min_faces:
        return image_bytes

    # Anonymize the frame
    anonymize_frame(
        dets,
        frame_rgb,
        mask_scale=mask_scale,
        replacewith=replacewith,
        ellipse=ellipse,
        draw_scores=draw_scores,
        replaceimg=replaceimg,
        mosaicsize=mosaicsize,
    )

    # Convert back to PIL Image
    anonymized_pil_image = Image.fromarray(frame_rgb)

    # Display preview if enabled
    if enable_preview:
        # Convert RGB to BGR for OpenCV display
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        cv2.imshow("Preview of anonymization results (press any key to close)", frame_bgr)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    # Save image to bytes
    output_image_bytes_io = BytesIO()
    save_kwargs = {}
    if keep_metadata:
        save_kwargs.update(info)

    save_kwargs["format"] = input_format
    save_kwargs["optimize"] = True

    # Save the image using the specified format and parameters
    anonymized_pil_image.save(output_image_bytes_io, **save_kwargs)

    # Retrieve the bytes of the anonymized image
    output_image_bytes = output_image_bytes_io.getvalue()

    return output_image_bytes


def get_file_type(path):
    if path.startswith("<video"):
        return "cam"
    if not os.path.isfile(path):
        return "notfound"
    mime = mimetypes.guess_type(path)[0]
    if mime is None:
        return None
    if mime.startswith("video"):
        return "video"
    if mime.startswith("image"):
        return "image"
    return mime


def get_anonymized_image(
    frame, threshold: float, replacewith: str, mask_scale: float, ellipse: bool, draw_scores: bool, replaceimg=None
):
    """
    Method for getting an anonymized image without CLI
    returns frame
    """

    centerface = CenterFace(in_shape=None, backend="auto")
    dets, _ = centerface(frame, threshold=threshold)

    anonymize_frame(
        dets,
        frame,
        mask_scale=mask_scale,
        replacewith=replacewith,
        ellipse=ellipse,
        draw_scores=draw_scores,
        replaceimg=replaceimg,
    )

    return frame


def read_file_as_bytes(file_path):
    with open(file_path, "rb") as f:
        return f.read()


def parse_cli_args():
    parser = argparse.ArgumentParser(description="Video anonymization by face detection", add_help=False)
    parser.add_argument(
        "input",
        nargs="*",
        help=f"File path(s) or camera device name. It is possible to pass multiple paths by separating them by spaces or by using shell expansion (e.g. `$ anonfaces vids/*.mp4`). Alternatively, you can pass a directory as an input, in which case all files in the directory will be used as inputs. If a camera is installed, a live webcam demo can be started by running `$ anonfaces cam` (which is a shortcut for `$ anonfaces -p '<video0>'`.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        metavar="O",
        help='Output file name. Defaults to input path + postfix "_anonymized".',
    )
    parser.add_argument(
        "--thresh",
        "-t",
        default=0.2,
        type=float,
        metavar="T",
        help="Detection threshold (tune this to trade off between false positive and false negative rate). Default: 0.2.",
    )
    parser.add_argument(
        "--scale",
        "-s",
        default=None,
        metavar="WxH",
        help="Downscale images for network inference to this size (format: WxH, example: --scale 640x360).",
    )
    parser.add_argument(
        "--preview",
        "-p",
        default=False,
        action="store_true",
        help="Enable live preview GUI (can decrease performance).",
    )
    parser.add_argument("--boxes", default=False, action="store_true", help="Use boxes instead of ellipse masks.")
    parser.add_argument("--draw-scores", default=False, action="store_true", help="Draw detection scores onto outputs.")
    parser.add_argument(
        "--mask-scale",
        default=1.3,
        type=float,
        metavar="M",
        help="Scale factor for face masks, to make sure that masks cover the complete face. Default: 1.3.",
    )
    parser.add_argument(
        "--replacewith",
        default="blur",
        choices=["blur", "solid", "none", "img", "mosaic"],
        help='Anonymization filter mode for face regions. "blur" applies a strong gaussian blurring, "solid" draws a solid black box, "none" does leaves the input unchanged, "img" replaces the face with a custom image and "mosaic" replaces the face with mosaic. Default: "blur".',
    )
    parser.add_argument(
        "--replaceimg",
        default="replace_img.png",
        help="Anonymization image for face regions. Requires --replacewith img option.",
    )
    parser.add_argument(
        "--mosaicsize",
        default=20,
        type=int,
        metavar="width",
        help="Setting the mosaic size. Requires --replacewith mosaic option. Default: 20.",
    )
    parser.add_argument(
        "--distort-audio",
        "-da",
        default=False,
        action="store_true",
        help="Enable audio distortion for the output video (applies pitch shift and gain effects to the audio). This automatically applies --keep-audio but will not work with --copy-acodec due to MoviePy",
    )
    parser.add_argument(
        "--keep-audio",
        "-k",
        default=False,
        action="store_true",
        help="Keep audio from video source file and copy it over to the output (only applies to videos).",
    )
    parser.add_argument(
        "--copy-acodec", "-ca", default=False, action="store_true", help="Keep audio codec from video source file."
    )
    parser.add_argument(
        "--show-ffmpeg-config",
        "-config",
        action="store_true",
        default=False,
        help="Shows the FFmpeg config arguments string.",
    )
    parser.add_argument(
        "--show-ffmpeg-command",
        "-command",
        action="store_true",
        default=False,
        help="Shows the FFmpeg constructed command used for processing the video. Helpful for troublshooting.",
    )
    parser.add_argument(
        "--show-both",
        "-both",
        action="store_true",
        default=False,
        help="Shows both --show-ffmpeg-command & --show-ffmpeg-config",
    )
    parser.add_argument(
        "--ffmpeg-config",
        default={"codec": "libx264"},
        type=json.loads,
        help='FFMPEG config arguments for encoding output videos. This argument is expected in JSON notation. For a list of possible options, refer to the ffmpeg-imageio docs. Default: \'{"codec": "libx264"}\'.',
    )  # See https://imageio.readthedocs.io/en/stable/format_ffmpeg.html#parameters-for-saving
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "onnxrt", "opencv"],
        help='Backend for ONNX model execution. Default: "auto" (prefer onnxrt if available).',
    )
    parser.add_argument(
        "--execution-provider",
        "--ep",
        default=None,
        metavar="EP",
        help="Override onnxrt execution provider (see https://onnxruntime.ai/docs/execution-providers/). If not specified, the presumably fastest available one will be automatically selected. Only used if backend is onnxrt.",
    )
    parser.add_argument(
        "--keep-metadata",
        "-m",
        default=False,
        action="store_true",
        help="Keep metadata of the original image. Default : False.",
    )
    parser.add_argument("--help", "-h", action="help", help="Show this help message and exit.")

    args = parser.parse_args()

    if args.show_both:
        args.show_ffmpeg_command = True
        args.show_ffmpeg_config = True

    # Automatically enable keep_audio if distort_audio is set
    if args.distort_audio:
        args.keep_audio = True

    if args.keep_audio and args.copy_acodec:
        tqdm.write("")
        tqdm.write("Error: '--keep-audio' and '--copy-acodec' cannot be used together. Please choose one.")
        exit(1)

    if len(args.input) == 0:
        parser.print_help()
        tqdm.write("\nPlease supply at least one input path.")
        exit(1)

    if args.input == ["cam"]:  # Shortcut for webcam demo with live preview
        args.input = ["<video0>"]
        args.preview = True

    return args


def process_inputs(
    input_paths,
    output,
    thresh,
    preview,
    ellipse,
    draw_scores,
    mask_scale,
    replacewith,
    replaceimg,
    mosaicsize,
    distort_audio,
    keep_audio,
    copy_acodec,
    show_ffmpeg_config,
    show_ffmpeg_command,
    ffmpeg_config,
    centerface,
    keep_metadata,
):
    # If multiple inputs, show a batch progress bar
    multi_file = len(input_paths) > 1
    if multi_file:
        input_paths = tqdm(input_paths, position=0, dynamic_ncols=True, desc="Batch progress")

    for ipath in input_paths:
        if stop_ffmpeg:
            break
        opath = output

        is_cam = False
        if ipath == "cam":
            ipath = "<video0>"
            is_cam = True
            preview = True

        filetype = get_file_type(ipath)
        if opath is None and not is_cam:
            root, ext = os.path.splitext(ipath)
            opath = f"{root}_anon{ext}"

        tqdm.write(f"Input:  {ipath}\nOutput: {opath}\n")
        if opath is None and not preview:
            tqdm.write("No output file specified and preview disabled. No output will be produced.")

        # Process videos
        if filetype in ["video", "cam"]:
            video_detect(
                ipath=ipath,
                opath=opath,
                centerface=centerface,
                threshold=thresh,
                cam=is_cam,
                replacewith=replacewith,
                mask_scale=mask_scale,
                ellipse=ellipse,
                draw_scores=draw_scores,
                enable_preview=preview,
                nested=multi_file,
                keep_audio=keep_audio,
                copy_acodec=copy_acodec,
                ffmpeg_config=ffmpeg_config,
                replaceimg=replaceimg,
                mosaicsize=mosaicsize,
                show_ffmpeg_config=show_ffmpeg_config,
                show_ffmpeg_command=show_ffmpeg_command,
            )
            if stop_ffmpeg:
                break
            if distort_audio:
                tqdm.write("Distorting audio for the video...")
                distort_now(ipath, opath)
            else:
                tqdm.write("Skipping audio distortion.")

        # Process images
        elif filetype == "image":
            with open(ipath, "rb") as f:
                input_bytes = f.read()
            input_extension = os.path.splitext(ipath)[1].lower()
            input_format = Image.registered_extensions().get(input_extension, "JPEG")

            output_image_bytes = image_detect(
                image_bytes=input_bytes,
                centerface=centerface,
                threshold=thresh,
                replacewith=replacewith,
                mask_scale=mask_scale,
                ellipse=ellipse,
                draw_scores=draw_scores,
                enable_preview=preview,
                keep_metadata=keep_metadata,
                replaceimg=replaceimg,
                mosaicsize=mosaicsize,
                input_format=input_format,
            )

            if stop_ffmpeg:
                break

            with open(opath, "wb") as f:
                f.write(output_image_bytes)

        elif filetype is None:
            tqdm.write(f"Cannot determine file type of file {ipath}. Skipping...")
        elif filetype == "notfound":
            tqdm.write(f"File {ipath} not found. Skipping...")
        else:
            tqdm.write(f"File {ipath} has an unknown type {filetype}. Skipping...")


def run_anonfaces(
    input_paths,
    output=None,
    thresh=0.2,
    scale=None,
    preview=False,
    boxes=False,
    draw_scores=False,
    mask_scale=1.3,
    replacewith="blur",
    replaceimg_path="replace_img.png",
    mosaicsize=20,
    distort_audio=False,
    keep_audio=False,
    copy_acodec=False,
    show_ffmpeg_config=False,
    show_ffmpeg_command=False,
    ffmpeg_config={"codec": "libx264"},
    backend="auto",
    execution_provider=None,
    keep_metadata=False,
):
    in_shape = None
    if scale is not None:
        w, h = scale.split("x")
        in_shape = (int(w), int(h))

    replaceimg = None
    if replacewith == "img":
        replaceimg = imageio.imread(replaceimg_path)
        print(f"After opening {replaceimg_path} shape: {replaceimg.shape}")

    ellipse = not boxes
    centerface = CenterFace(in_shape=in_shape, backend=backend, override_execution_provider=execution_provider)

    process_inputs(
        input_paths=input_paths,
        output=output,
        thresh=thresh,
        preview=preview,
        ellipse=ellipse,
        draw_scores=draw_scores,
        mask_scale=mask_scale,
        replacewith=replacewith,
        replaceimg=replaceimg,
        mosaicsize=mosaicsize,
        distort_audio=distort_audio,
        keep_audio=keep_audio,
        copy_acodec=copy_acodec,
        show_ffmpeg_config=show_ffmpeg_config,
        show_ffmpeg_command=show_ffmpeg_command,
        ffmpeg_config=ffmpeg_config,
        centerface=centerface,
        keep_metadata=keep_metadata,
    )


def main():
    args = parse_cli_args()
    # Prepare input paths
    ipaths = []
    for path in args.input:
        if os.path.isdir(path):
            for file in os.listdir(path):
                ipaths.append(os.path.join(path, file))
        else:
            ipaths.append(path)

    # Set up parameters from args
    if args.scale is not None:
        w, h = args.scale.split("x")
        in_shape = (int(w), int(h))
    else:
        in_shape = None

    replaceimg = None
    if args.replacewith == "img":
        replaceimg = imageio.imread(args.replaceimg)
        print(f"After opening {args.replaceimg} shape: {replaceimg.shape}")

    ellipse = not args.boxes

    centerface = CenterFace(
        in_shape=in_shape, backend=args.backend, override_execution_provider=args.execution_provider
    )

    process_inputs(
        input_paths=ipaths,
        output=args.output,
        thresh=args.thresh,
        preview=args.preview,
        ellipse=ellipse,
        draw_scores=args.draw_scores,
        mask_scale=args.mask_scale,
        replacewith=args.replacewith,
        replaceimg=replaceimg,
        mosaicsize=args.mosaicsize,
        distort_audio=args.distort_audio,
        keep_audio=args.keep_audio,
        copy_acodec=args.copy_acodec,
        show_ffmpeg_config=args.show_ffmpeg_config,
        show_ffmpeg_command=args.show_ffmpeg_command,
        ffmpeg_config=args.ffmpeg_config,
        centerface=centerface,
        keep_metadata=args.keep_metadata,
    )


if __name__ == "__main__":
    main()
