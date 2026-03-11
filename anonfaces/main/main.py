#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
from typing import Dict, Tuple
import tempfile
import numpy as np
import ffmpeg
import cv2
import sys
import math
import signal
import platform
from pedalboard import Gain, PitchShift, Pedalboard
from pedalboard.io import AudioFile
from tqdm import tqdm
import tkinter as tk
import sqlite3
import re
from tkinter import Tk
from tkinter.filedialog import askdirectory


try:
    from anonfaces import __version__
    from anonfaces.main.centerface import CenterFace
    from anonfaces.main.arcface import ArcFaceONNX, align_face
    from anonfaces.gui.dbfacegui import FaceDatabaseApp
except (ModuleNotFoundError, ImportError):
    # Standalone mode - running directly from the package directory
    _pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from __init__ import __version__
    from main.centerface import CenterFace
    from main.arcface import ArcFaceONNX, align_face
    from gui.dbfacegui import FaceDatabaseApp




# Sends a signal to stop ffmpeg
stop_ffmpeg = False


def signal_handler(signum, frame):
    global stop_ffmpeg
    stop_ffmpeg = True
    #tqdm.write(f"")
    #tqdm.write("Stop signal received, stopping cleanly...")
    #tqdm.write(f"")


signal.signal(signal.SIGINT, signal_handler)



def scale_bb(x1, y1, x2, y2, mask_scale=1.0):
    s = mask_scale - 1.0
    h, w = y2 - y1, x2 - x1
    y1 -= h * s
    y2 += h * s
    x1 -= w * s
    x2 += w * s
    return np.round([x1, y1, x2, y2]).astype(int)


def draw_det(
        frame, score, det_idx, x1, y1, x2, y2,
        replacewith: str = 'blur',
        ellipse: bool = True,
        draw_scores: bool = False,
        ovcolor: Tuple[int] = (0, 0, 0),
        replaceimg = None,
        mosaicsize: int = 20
):
    if replacewith == 'solid':
        cv2.rectangle(frame, (x1, y1), (x2, y2), ovcolor, -1)
    elif replacewith == 'blur':
        bf = 2  # blur factor (number of pixels in each dimension that the face will be reduced to)
        blurred_box =  cv2.blur(
            frame[y1:y2, x1:x2],
            (abs(x2 - x1) // bf, abs(y2 - y1) // bf)
        )
        if ellipse:
            # Build ellipse mask using cv2 (C++ native, faster than skimage coordinate generation)
            h_roi, w_roi = y2 - y1, x2 - x1
            mask = np.zeros((h_roi, w_roi), dtype=np.uint8)
            cv2.ellipse(mask, (w_roi // 2, h_roi // 2), (w_roi // 2, h_roi // 2), 0, 0, 360, 255, -1)
            mask_bool = mask > 0
            roibox = frame[y1:y2, x1:x2]
            roibox[mask_bool] = blurred_box[mask_bool]
            frame[y1:y2, x1:x2] = roibox
        else:
            frame[y1:y2, x1:x2] = blurred_box
    elif replacewith == 'img':
        target_size = (x2 - x1, y2 - y1)
        resized_replaceimg = cv2.resize(replaceimg, target_size)
        if replaceimg.shape[2] == 3:  # RGB
            frame[y1:y2, x1:x2] = resized_replaceimg
        elif replaceimg.shape[2] == 4:  # RGBA
            frame[y1:y2, x1:x2] = frame[y1:y2, x1:x2] * (1 - resized_replaceimg[:, :, 3:] / 255) + resized_replaceimg[:, :, :3] * (resized_replaceimg[:, :, 3:] / 255)
    elif replacewith == 'mosaic':
        for y in range(y1, y2, mosaicsize):
            for x in range(x1, x2, mosaicsize):
                pt1 = (x, y)
                pt2 = (min(x2, x + mosaicsize - 1), min(y2, y + mosaicsize - 1))
                color = (int(frame[y, x][0]), int(frame[y, x][1]), int(frame[y, x][2]))
                cv2.rectangle(frame, pt1, pt2, color, -1)
    elif replacewith == 'none':
        pass
    if draw_scores:
        cv2.putText(
            frame, f'{score:.2f}', (x1 + 0, y1 - 20),
            cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 0)
        )


#leaving here to fallback to directory loading faces
def load_reference_faces(reference_directory, centerface, arcface):
    reference_descriptors = []
    reference_names = []
    for file_name in os.listdir(reference_directory):
        if file_name.endswith(('.jpg', '.jpeg', '.png')):
            img_path = os.path.join(reference_directory, file_name)
            img = cv2.imread(img_path)
            if img is None:
                tqdm.write(f"Could not open {img_path}")
                continue
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            dets, lms = centerface(img_rgb, threshold=0.2)

            if len(dets) > 0:
                landmarks = lms[0].reshape(5, 2)
                aligned = align_face(img_rgb, landmarks)
                embedding = arcface.get_embedding(aligned)
                reference_descriptors.append(embedding)
                # Clean up the name by removing numbers and file extensions so we can have multiple images John_Doe1.jpg
                cleaned_name = re.sub(r'\d+', '', os.path.splitext(file_name)[0])
                cleaned_name = cleaned_name.replace('_', ' ').title()
                reference_names.append(cleaned_name)
            else:
                tqdm.write(f"No face detected in {img_path}")

    return reference_descriptors, reference_names


# check if a detected face matches any reference face (cosine similarity, higher = more similar)
def is_known_face(face_embedding, reference_face_descriptors, reference_names, reference_image_ids, threshold):
    for ref_descriptor, ref_name, ref_id in zip(reference_face_descriptors, reference_names, reference_image_ids):
        similarity = float(np.dot(face_embedding, ref_descriptor))
        if similarity > threshold:
            return ref_name
    return None


def load_reference_faces_from_db(database_path, centerface, arcface):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # get all persons and their associated images
    cursor.execute('''
        SELECT images.id, persons.name, images.image
        FROM persons
        JOIN images ON persons.id = images.person_id
    ''')

    reference_descriptors = []
    reference_names = []
    reference_image_ids = []

    for image_id, name, image_blob in cursor.fetchall():
        # convert sql BLOB back to an image
        img = np.frombuffer(image_blob, dtype=np.uint8)
        img = cv2.imdecode(img, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # detect face with CenterFace and compute ArcFace embedding
        dets, lms = centerface(img_rgb, threshold=0.2)
        if len(dets) > 0:
            landmarks = lms[0].reshape(5, 2)
            aligned = align_face(img_rgb, landmarks)
            embedding = arcface.get_embedding(aligned)
            reference_descriptors.append(embedding)
            # first letter of first and last capitalized, remove all numbers
            cleaned_name = ' '.join([part.capitalize() for part in ''.join([i for i in name if not i.isdigit()]).split()])
            reference_names.append(cleaned_name)
            reference_image_ids.append(image_id)
        else:
            tqdm.write(f"No face detected in {name}")

    conn.close()
    return reference_descriptors, reference_names, reference_image_ids


def anonymize_frame(
        dets, frame, mask_scale,
        replacewith, ellipse, draw_scores, replaceimg, mosaicsize,
        face_recog, fr_name, arcface=None, landmarks=None,
        reference_face_descriptors=None, reference_names=None, reference_image_ids=None, fr_thresh=0.45,
):
    # Batch ArcFace: align all faces and compute embeddings in one inference call
    use_recog = face_recog and reference_face_descriptors and arcface is not None and landmarks is not None
    known_flags = {}  # index -> matched_name or None
    if use_recog and len(dets) > 0:
        aligned_faces = []
        for i in range(len(dets)):
            face_lms = landmarks[i].reshape(5, 2)
            aligned_faces.append(align_face(frame, face_lms))
        embeddings = arcface.get_embeddings_batch(aligned_faces)
        # Vectorized matching: ref_matrix (R, 512) @ embedding (512,) -> (R,) similarities
        ref_matrix = np.stack(reference_face_descriptors)  # (R, 512)
        for i in range(len(dets)):
            similarities = ref_matrix @ embeddings[i]
            best_idx = np.argmax(similarities)
            if similarities[best_idx] > fr_thresh:
                known_flags[i] = reference_names[best_idx]
            else:
                known_flags[i] = None

    for i, det in enumerate(dets):
        boxes, score = det[:4], det[4]
        x1, y1, x2, y2 = boxes.astype(int)
        x1, y1, x2, y2 = scale_bb(x1, y1, x2, y2, mask_scale)
        y1, y2 = max(0, y1), min(frame.shape[0] - 1, y2)
        x1, x2 = max(0, x1), min(frame.shape[1] - 1, x2)

        if use_recog:
            matched_name = known_flags.get(i)
            if matched_name:
                if fr_name:
                    text_size = cv2.getTextSize(matched_name, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
                    text_x = x1 + (x2 - x1 - text_size[0]) // 2
                    text_y = y1 + text_size[1]
                    cv2.putText(frame, matched_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (36, 255, 12), 2)
                continue  # Skip blurring for known faces

        draw_det(
            frame, score, i, x1, y1, x2, y2,
            replacewith=replacewith,
            ellipse=ellipse,
            draw_scores=draw_scores,
            replaceimg=replaceimg,
            mosaicsize=mosaicsize
        )



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
        replaceimg = None,
        keep_audio: bool = False,
        mosaicsize: int = 20,
        #new below
        copy_acodec: bool = False,
        info: bool = False,
        face_recog: bool = False,  # Add face recog parameter from below
        reference_face_descriptors=None,
        reference_names=None,
        reference_image_ids=None,
        fr_thresh=0.60,
        fr_name: bool = False,
        arcface=None
):
    try:
        # Handle camera device identifiers for OpenCV
        if isinstance(ipath, str) and ipath.startswith('<video') and ipath.endswith('>'):
            device_id = int(ipath[6:-1])
            # Use DirectShow on Windows for better camera compatibility
            if platform.system() == 'Windows':
                cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(device_id)
        else:
            cap = cv2.VideoCapture(ipath)

        if not cap.isOpened():
            raise IOError("Cannot open video source")

        original_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Check for audio stream via ffmpeg probe (only for files, not cameras)
        has_audio = False
        if not cam:
            try:
                probe_data = ffmpeg.probe(ipath)
                audio_stream = next((s for s in probe_data['streams'] if s['codec_type'] == 'audio'), None)
                has_audio = audio_stream is not None
            except:
                has_audio = False
    except Exception as e:
        if cam:
            tqdm.write(f'Could not find video device {ipath}. Please set a valid input. Error: {e}')
        else:
            tqdm.write(f'Could not open file {ipath} as a video file. Skipping file...')
        return

    if cam:
        nframes = None
    else:
        try:
            if platform.system() != "Darwin":
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                specified_fps = ffmpeg_config.get('fps', original_fps)

                # Calculate adjusted total frames based on specified FPS
                nframes = math.ceil(total_frames * (specified_fps / original_fps)) if total_frames > 0 else None
            else:
                nframes = None  # Frame counting fails on macOS - do not have a mac to test - someone? anyone?
        except:
            nframes = None # Fallback if counting frames fail
    # Now intialize the progress bars with the adjusted nframes
    if nested:
        bar = tqdm(dynamic_ncols=True, total=nframes, position=1, leave=True)
    else:
        bar = tqdm(dynamic_ncols=True, total=nframes)

    process = None
    if opath is not None:
        _ffmpeg_config = ffmpeg_config.copy()
        #  If fps is not explicitly set in ffmpeg_config, use source video fps value
        _ffmpeg_config.setdefault('fps', original_fps)
        codec = _ffmpeg_config.get('codec', 'mpeg4')
        fps = _ffmpeg_config.get('fps', original_fps)
        bitrate = _ffmpeg_config.get('bitrate', None)
        pix_fmt = _ffmpeg_config.get('pix_fmt', None)
        audio_codec = _ffmpeg_config.get('acodec', 'aac')
        audio_bitrate = _ffmpeg_config.get('audio_bitrate', None)
        sample_rate = _ffmpeg_config.get('sample_rate', None)

        # Build ffmpeg-python output pipeline
        video_in = ffmpeg.input('pipe:', format='rawvideo', pix_fmt='rgb24', s=f'{width}x{height}', r=fps)
        output_kwargs = {'vcodec': codec}
        if bitrate:
            output_kwargs['video_bitrate'] = bitrate
        # Default to yuv420p for broad player compatibility (rgb24 input causes 4:4:4 profile)
        output_kwargs['pix_fmt'] = pix_fmt if pix_fmt else 'yuv420p'

        # Handle audio muxing
        if keep_audio and has_audio:
            audio_in = ffmpeg.input(ipath).audio
            output_kwargs['acodec'] = audio_codec
            output_kwargs['shortest'] = None  # Trim audio to match video length (e.g. if stopped early)
            if audio_bitrate:
                output_kwargs['audio_bitrate'] = audio_bitrate
            if sample_rate:
                output_kwargs['ar'] = sample_rate
            process = (
                ffmpeg
                .output(video_in, audio_in, opath, **output_kwargs)
                .overwrite_output()
                .run_async(pipe_stdin=True, pipe_stderr=True)
            )
        elif copy_acodec and has_audio:
            audio_in = ffmpeg.input(ipath).audio
            audio_codec = 'copy'
            output_kwargs['acodec'] = audio_codec
            output_kwargs['shortest'] = None  # Trim audio to match video length (e.g. if stopped early)
            process = (
                ffmpeg
                .output(video_in, audio_in, opath, **output_kwargs)
                .overwrite_output()
                .run_async(pipe_stdin=True, pipe_stderr=True)
            )
        else:
            process = (
                ffmpeg
                .output(video_in, opath, **output_kwargs)
                .overwrite_output()
                .run_async(pipe_stdin=True, pipe_stderr=True)
            )

        if info:
            ffmpeg_command = f"ffmpeg -y -f rawvideo -pix_fmt rgb24 -s {width}x{height} -r {fps} -i pipe: "
            if bitrate:
                ffmpeg_command += f"-b:v {bitrate} "
            if pix_fmt:
                ffmpeg_command += f"-pix_fmt {pix_fmt} "
            ffmpeg_command += f"-c:v {codec} "
            if audio_codec:
                ffmpeg_command += f"-c:a {audio_codec} "
                if audio_bitrate:
                    ffmpeg_command += f"-b:a {audio_bitrate} "
                if sample_rate:
                    ffmpeg_command += f"-ar {sample_rate} "
            ffmpeg_command += f"{opath}"
            tqdm.write(f"FFMPEG Command: {ffmpeg_command}")
            tqdm.write("")

    # Drain ffmpeg stderr in a background thread to prevent pipe deadlock
    ffmpeg_stderr_output = []
    if process is not None and process.stderr:
        import threading as _threading
        def _drain_stderr():
            for line in iter(process.stderr.readline, b''):
                ffmpeg_stderr_output.append(line.decode(errors='replace').strip())
        _stderr_thread = _threading.Thread(target=_drain_stderr, daemon=True)
        _stderr_thread.start()

    # Handle fps resampling - skip frames if target fps differs from source
    target_fps = ffmpeg_config.get('fps', original_fps)
    frame_interval = original_fps / target_fps if target_fps < original_fps else 1
    frame_idx = 0

    while True:
        #signal flag during ffmpeg video_detect
        if stop_ffmpeg:
            bar.close()
            cap.release()
            if opath is not None and process is not None:
                process.stdin.close()
                process.wait()
            tqdm.write(f"")
            tqdm.write("Stop signal received, stopping cleanly...")
            tqdm.write(f"")
            return

        ret, frame = cap.read()
        if not ret:
            break

        # Frame skipping for fps resampling
        if frame_interval > 1:
            frame_idx += 1
            if int(frame_idx % frame_interval) != 0:
                continue

        # Convert BGR to RGB (OpenCV reads BGR, CenterFace expects RGB)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Perform network inference, get bb dets and landmark predictions
        dets, lms = centerface(frame, threshold=threshold)

        anonymize_frame(
            dets, frame, mask_scale=mask_scale,
            replacewith=replacewith, ellipse=ellipse, draw_scores=draw_scores,
            replaceimg=replaceimg, mosaicsize=mosaicsize,
            face_recog=face_recog, fr_name=fr_name,
            arcface=arcface, landmarks=lms,
            reference_face_descriptors=reference_face_descriptors,
            reference_names=reference_names, fr_thresh=fr_thresh,
            reference_image_ids=reference_image_ids,
        )

        if opath is not None and process is not None:
            try:
                process.stdin.write(frame.tobytes())
            except OSError as e:
                tqdm.write(f"FFmpeg pipe error: {e}")
                if ffmpeg_stderr_output:
                    tqdm.write(f"FFmpeg stderr: {chr(10).join(ffmpeg_stderr_output[-20:])}")
                break

        if enable_preview:
            cv2.imshow('Preview of anonymization results (quit by pressing Q or Escape)', frame[:, :, ::-1])  # RGB -> BGR for display
            if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:  # 27 is the escape key code
                cv2.destroyAllWindows()
                break
        bar.update()
    cap.release()
    if opath is not None and process is not None:
        try:
            process.stdin.close()
        except OSError:
            pass
        process.wait()
        if process.returncode != 0 and ffmpeg_stderr_output:
            tqdm.write(f"FFmpeg error output: {chr(10).join(ffmpeg_stderr_output[-20:])}")
    bar.close()


def distort_now(ipath, opath, sample_rate=44100.0):
    """Extract audio from original, distort it, mux onto anonymized video."""
    root, ext = os.path.splitext(opath)
    dopath = f"{root}_distorted{ext}"

    with tempfile.TemporaryDirectory() as tmpdir:
        extracted = os.path.join(tmpdir, "audio.wav")
        distorted = os.path.join(tmpdir, "distorted.wav")

        # Extract audio from original video via ffmpeg
        ffmpeg.input(ipath).output(extracted, ac=1, ar=sample_rate).overwrite_output().run(quiet=True)

        # Distort with pedalboard
        with AudioFile(extracted).resampled_to(sample_rate) as f:
            audio = f.read(f.frames)
        board = Pedalboard([Gain(gain_db=5), PitchShift(semitones=-2.5)])
        d_audio = board(audio, sample_rate)
        with AudioFile(distorted, 'w', sample_rate, d_audio.shape[0]) as f:
            f.write(d_audio)

        # Mux: copy video stream from anonymized output + distorted audio (no re-encode)
        video_in = ffmpeg.input(opath).video
        audio_in = ffmpeg.input(distorted).audio
        ffmpeg.output(video_in, audio_in, dopath, vcodec='copy', acodec='aac').overwrite_output().run(quiet=True)
    

def image_detect(
        ipath: str,
        opath: str,
        centerface: CenterFace,
        threshold: float,
        replacewith: str,
        mask_scale: float,
        ellipse: bool,
        draw_scores: bool,
        enable_preview: bool,
        keep_metadata: bool,
        replaceimg = None,
        mosaicsize: int = 20,
        #new below
        face_recog: bool = False,  # Add face_recog parameter
        reference_face_descriptors=None,
        reference_names=None,
        reference_image_ids=None,
        fr_thresh=0.60,
        fr_name: bool = False,
        arcface=None
):
    frame_bgr = cv2.imread(ipath)
    if frame_bgr is None:
        tqdm.write(f'Could not open image {ipath}. Skipping...')
        return
    # Convert BGR to RGB (OpenCV reads BGR, CenterFace expects RGB)
    frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    if keep_metadata:
        # Source image EXIF metadata retrieval via PIL
        from PIL import Image as PILImage
        pil_img = PILImage.open(ipath)
        exif_data = pil_img.info.get('exif', None)

    # Perform network inference, get bb dets and landmark predictions
    dets, lms = centerface(frame, threshold=threshold)

    anonymize_frame(
        dets, frame, mask_scale=mask_scale,
        replacewith=replacewith, ellipse=ellipse, draw_scores=draw_scores,
        replaceimg=replaceimg, mosaicsize=mosaicsize,
        face_recog=face_recog, fr_name=fr_name,
        arcface=arcface, landmarks=lms,
        reference_face_descriptors=reference_face_descriptors,
        reference_names=reference_names, fr_thresh=fr_thresh,
        reference_image_ids=reference_image_ids,
    )

    if enable_preview:
        cv2.imshow('Preview of anonymization results (quit by pressing Q or Escape)', frame[:, :, ::-1])  # RGB -> BGR for display
        if cv2.waitKey(0) & 0xFF in [ord('q'), 27]:  # 27 is the escape key code
            cv2.destroyAllWindows()

    # Save with or without EXIF metadata
    if keep_metadata and exif_data:
        from PIL import Image as PILImage
        pil_out = PILImage.fromarray(frame)  # frame is RGB, PIL expects RGB
        pil_out.save(opath, exif=exif_data)
    else:
        frame_out = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite(opath, frame_out)


def get_file_type(path):
    if path.startswith('<video'):
        return 'cam'
    if not os.path.isfile(path):
        return 'notfound'
    mime = mimetypes.guess_type(path)[0]
    if mime is None:
        return None
    if mime.startswith('video'):
        return 'video'
    if mime.startswith('image'):
        return 'image'
    return mime


def get_anonymized_image(frame,
                         threshold: float,
                         replacewith: str,
                         mask_scale: float,
                         ellipse: bool,
                         draw_scores: bool,
                         replaceimg = None,
                         mosaicsize: int = 20
                         ):
    """
    Method for getting an anonymized image without CLI
    returns frame
    """

    centerface = CenterFace(in_shape=None, backend='auto')
    dets, lms = centerface(frame, threshold=threshold)

    anonymize_frame(
        dets, frame, mask_scale=mask_scale,
        replacewith=replacewith, ellipse=ellipse, draw_scores=draw_scores,
        replaceimg=replaceimg, mosaicsize=mosaicsize,
        face_recog=False, fr_name=False,
        arcface=None, landmarks=lms
    )

    return frame


def parse_cli_args():
    parser = argparse.ArgumentParser(description='Video/Image anonymization by face detection with beta stage face recognition', add_help=False)
    parser.add_argument(
        'input', nargs='*',
        help=f'File path(s) or camera device name. It is possible to pass multiple paths by separating them by spaces or by using shell expansion (e.g. `$ anonfaces vids/*.mp4`). Alternatively, you can pass a directory as an input, in which case all files in the directory will be used as inputs. If a camera is installed, a live webcam demo can be started by running `$ anonfaces cam` (which is a shortcut for `$ anonfaces -p \'<video0>\'`.')
    parser.add_argument(
        '--output', '-o', default=None, metavar='O',
        help='Output file name. Defaults to input path + postfix "_anonymized".')
    parser.add_argument(
        '--thresh', '-t', default=0.2, type=float, metavar='T',
        help='Detection threshold (tune this to trade off between false positive and false negative rate). Default: 0.2.')
    parser.add_argument(
        '--scale', '-s', default=None, metavar='WxH',
        help='Downscale images for network inference to this size (format: WxH, example: --scale 640x360).')
    parser.add_argument(
        '--preview', '-p', default=False, action='store_true',
        help='Enable live preview GUI (can decrease performance).')
    parser.add_argument(
        '--boxes', default=False, action='store_true',
        help='Use boxes instead of ellipse masks.')
    parser.add_argument(
        '--draw-scores', '-ds', default=False, action='store_true',
        help='Draw detection scores onto outputs.')
    parser.add_argument(
        '--mask-scale', default=1.3, type=float, metavar='M',
        help='Scale factor for face masks, to make sure that masks cover the complete face. Default: 1.3.')
    parser.add_argument(
        '--replacewith', default='blur', choices=['blur', 'solid', 'none', 'img', 'mosaic'],
        help='Anonymization filter mode for face regions. "blur" applies a strong gaussian blurring, "solid" draws a solid black box, "none" does leaves the input unchanged, "img" replaces the face with a custom image and "mosaic" replaces the face with mosaic. Default: "blur".')
    parser.add_argument(
        '--replaceimg', default='replace_img.png',
        help='Anonymization image for face regions. Requires --replacewith img option.')
    parser.add_argument(
        '--mosaicsize', default=20, type=int, metavar='width',
        help='Setting the mosaic size. Requires --replacewith mosaic option. Default: 20.')
    parser.add_argument(
        '--face-recog', '-fr', default=False, action='store_true',
        help="Enable face recognition to not blur faces in Face GUI Database.")
    parser.add_argument(
        '--fr-name', '-name', default=False, action='store_true',
        help="Enable face recognition names from image name in Face GUI Database.")    
    parser.add_argument(
        '--face-gui', '-fg', default=False, action='store_true',
        help="Launch the face database GUI without running face recognition.")
    parser.add_argument(
        '--frn', '-frn', action='store_true', default=False,
        help="Enable both face recognition and name labeling from image names.")
    parser.add_argument(
        '--fr-thresh', '-ft', type=float, default=0.45,
        help="Set the face recognition cosine similarity threshold (higher = stricter). Default: 0.45")
    parser.add_argument(
        '--distort-audio', '-da', default=False, action='store_true',
        help='Enable audio distortion for the output video (applies pitch shift and gain effects to the audio). This automatically applies --keep-audio but will not work with --copy-acodec.')
    parser.add_argument(
        '--keep-audio', '-k', default=False, action='store_true',
        help='Keep audio from video source file and copy it over to the output (only applies to videos).')
    parser.add_argument(
        '--copy-acodec', '-ca', default=False, action='store_true',
        help='Keep audio codec from video source file.')
    parser.add_argument(
        '--ffmpeg-config', default={"codec": "mpeg4"}, type=json.loads,
        help='FFMPEG config arguments for encoding output videos. This argument is expected in JSON notation. For a list of possible options, refer to the ffmpeg docs. Default: \'{"codec": "mpeg4"}\'.  Windows example --ffmpeg-config "{\\"fps\\": 10, \\"bitrate\\": \\"1000k\\"}"')
    parser.add_argument(
        '--backend', default='auto', choices=['auto', 'onnxrt', 'opencv'],
        help='Backend for ONNX model execution. Default: "auto" (prefer onnxrt if available).')
    parser.add_argument(
        '--execution-provider', '-ep', default=None, metavar='EP',
        help='Override onnxrt execution provider (see https://onnxruntime.ai/docs/execution-providers/). If not specified, the presumably fastest available one will be automatically selected. Only used if backend is onnxrt.')
    parser.add_argument(
        '--info', default=False, action="store_true",
        help='Shows file input/output location and ffmpeg command. Default is off the clear clutter.')
    parser.add_argument(
        '--version', action='version', version=__version__,
        help='Print version number and exit.')
    parser.add_argument(
        '--keep-metadata', '-m', default=False, action='store_true',
        help='Keep metadata of the original image. Default : False.')
    parser.add_argument('--help', '-h', action='help', help='Show this help message and exit.')
    parser.add_argument(
        '--all', '-all', nargs=0, action=MyFavorite,
        help="Enables face recognition, names from image names, preview, draw scores, and keep audio.")
    
    args = parser.parse_args()
    
    if args.frn:
        args.face_recog = True
        args.fr_name = True
    
    if args.face_recog:
        root = tk.Tk()
        app = FaceDatabaseApp(root)
        try:
            root.protocol("WM_DELETE_WINDOW", app.close_app)
            root.mainloop()
        finally:
            app.close_app()
        
    if args.face_gui:     
        root = tk.Tk()
        app = FaceDatabaseApp(root)
        try:
            root.protocol("WM_DELETE_WINDOW", app.close_app)
            root.mainloop()
        finally:
            app.close_app()
        exit(1)
        
    # Automatically enable keep_audio if distort_audio is set
    if args.distort_audio:
        args.keep_audio = True
    
    if args.keep_audio and args.copy_acodec:
        tqdm.write("")
        tqdm.write("Error: '--keep-audio' and '--copy-acodec' cannot be used together. Please choose one.")
        exit(1)
    
    if len(args.input) == 0:
        parser.print_help()
        tqdm.write('\nPlease supply at least one input path.')
        exit(1)

    if args.input == ['cam']:  # Shortcut for webcam demo with live preview
        args.input = ['<video0>']
        args.preview = True

    return args

class MyFavorite(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, 'face_recog', True)
        setattr(namespace, 'fr_name', True)
        setattr(namespace, 'draw_scores', True)
        setattr(namespace, 'preview', True)
        setattr(namespace, 'keep_audio', True)

def main():
    args = parse_cli_args()
    ipaths = []
    
    # add files in folders
    for path in args.input:
        if os.path.isdir(path):
            for file in os.listdir(path):
                ipaths.append(os.path.join(path,file))
        else:
            # Either a path to a regular file, the special 'cam' shortcut
            # or an invalid path. The latter two cases are handled below.
            ipaths.append(path)

    base_opath = args.output
    replacewith = args.replacewith
    enable_preview = args.preview
    draw_scores = args.draw_scores
    threshold = args.thresh
    ellipse = not args.boxes
    mask_scale = args.mask_scale
    keep_audio = args.keep_audio
    ffmpeg_config = args.ffmpeg_config
    backend = args.backend
    in_shape = args.scale
    execution_provider = args.execution_provider
    threshold = args.thresh
    mosaicsize = args.mosaicsize
    keep_metadata = args.keep_metadata
    replaceimg = None
    #new below
    copy_acodec = args.copy_acodec
    info = args.info
    fr_name = args.fr_name
    if in_shape is not None:
        w, h = in_shape.split('x')
        in_shape = int(w), int(h)
    if replacewith == "img":
        replaceimg = cv2.imread(args.replaceimg, cv2.IMREAD_UNCHANGED)
        if replaceimg is not None:
            # Convert BGR/BGRA to RGB/RGBA for consistency
            if replaceimg.shape[2] == 4:
                replaceimg = cv2.cvtColor(replaceimg, cv2.COLOR_BGRA2RGBA)
            else:
                replaceimg = cv2.cvtColor(replaceimg, cv2.COLOR_BGR2RGB)
            tqdm.write(f'After opening {args.replaceimg} shape: {replaceimg.shape}')
        else:
            tqdm.write(f'Could not open replacement image {args.replaceimg}. Exiting.')
            sys.exit(1)


    # TODO: scalar downscaling setting (-> in_shape), preserving aspect ratio
    centerface = CenterFace(in_shape=in_shape, backend=backend, override_execution_provider=execution_provider)

    # Load ArcFace and reference faces if face recognition is enabled
    arcface_model = None
    if args.face_recog:
        arcface_model = ArcFaceONNX(backend=backend, override_execution_provider=execution_provider)
        database_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'database',
            'face_db.sqlite'
        )
        reference_face_descriptors, reference_names, reference_image_ids = load_reference_faces_from_db(database_path, centerface, arcface_model)
    else:
        reference_face_descriptors, reference_names, reference_image_ids = [], [], []

    multi_file = len(ipaths) > 1
    if multi_file:
        ipaths = tqdm(ipaths, position=0, dynamic_ncols=True, desc='Batch progress', leave=True)

    for ipath in ipaths:
        if stop_ffmpeg:
            break  # exit the loop immediately if signal is received
        opath = base_opath
        if ipath == 'cam':
            ipath = '<video0>'
            enable_preview = True
        filetype = get_file_type(ipath)
        is_cam = filetype == 'cam'
        if opath is None and not is_cam:
            root, ext = os.path.splitext(ipath)
            opath = f'{root}_anon{ext}'
        if info:
            tqdm.write(f"Input:  {ipath}\nOutput: {opath}")
            tqdm.write("")
        if opath is None and not enable_preview:
            tqdm.write('No output file is specified and the preview GUI is disabled. No output will be produced.')
        if filetype == 'video' or is_cam:
            video_detect(
                ipath=ipath,
                opath=opath,
                centerface=centerface,
                threshold=threshold,
                cam=is_cam,
                replacewith=replacewith,
                mask_scale=mask_scale,
                ellipse=ellipse,
                draw_scores=draw_scores,
                enable_preview=enable_preview,
                nested=multi_file,
                keep_audio=keep_audio,
                ffmpeg_config=ffmpeg_config,
                replaceimg=replaceimg,
                mosaicsize=mosaicsize,
                copy_acodec=copy_acodec,
                info=info,
                fr_thresh=args.fr_thresh,
                face_recog=args.face_recog,
                reference_face_descriptors=reference_face_descriptors if args.face_recog else None,
                reference_names=reference_names if args.face_recog else None,
                reference_image_ids=reference_image_ids if args.face_recog else None,
                fr_name=args.fr_name,
                arcface=arcface_model if args.face_recog else None
            )
            if stop_ffmpeg:
                break  # exit the loop immediately if signal is received - second loop
            # Check if args.distort_audio is allowed
            if args.keep_audio or args.copy_acodec:
                if args.distort_audio:
                    tqdm.write("")
                    tqdm.write("Distorting audio for the video...")
                    distort_now(ipath, opath)
        elif filetype == 'image':
            valid_image_ext = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
            _, ext = os.path.splitext(ipath)
            ext = ext.lower()
            # check if the file extension is valid for images due to heic images causing issue. may add a converter in as an arg.
            if ext in valid_image_ext:
                image_detect(
                    ipath=ipath,
                    opath=opath,
                    centerface=centerface,
                    threshold=threshold,
                    replacewith=replacewith,
                    mask_scale=mask_scale,
                    ellipse=ellipse,
                    draw_scores=draw_scores,
                    enable_preview=enable_preview,
                    keep_metadata=keep_metadata,
                    replaceimg=replaceimg,
                    mosaicsize=mosaicsize,
                    fr_thresh=args.fr_thresh,
                    face_recog=args.face_recog,
                    reference_face_descriptors=reference_face_descriptors if args.face_recog else None,
                    reference_names=reference_names if args.face_recog else None,
                    reference_image_ids=reference_image_ids if args.face_recog else None,
                    fr_name=args.fr_name,
                    arcface=arcface_model if args.face_recog else None
                )
            else:
                tqdm.write(f'File {ipath} has an unsupported image format {ext}. Skipping...')
            if stop_ffmpeg:
                break  # exit the loop immediately if signal is received - third loop
        elif filetype is None:
            tqdm.write(f'Can\'t determine file type of file {ipath}. Skipping...')
        elif filetype == 'notfound':
            tqdm.write(f'File {ipath} not found. Skipping...')
        else:
            tqdm.write(f'File {ipath} has an unknown type {filetype}. Skipping...')


#leaving this in here for a fallback
def select_reference_directory():
    # Initialize directory window aka Tkinter and hide the root/console window
    root = Tk()
    root.withdraw()

    # Choose your directory
    reference_directory = askdirectory(title="Select the directory containing reference images")

    if not reference_directory:
        tqdm.write("No directory selected. Exiting.")
        root.destroy()
        sys.exit(0)

    root.destroy()
    return reference_directory

if __name__ == '__main__':
    main()