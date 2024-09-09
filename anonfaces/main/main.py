#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
from typing import Dict, Tuple
import shutil
import skimage.draw
import numpy as np
import imageio
import imageio_ffmpeg as ffmpeg
import imageio.plugins.ffmpeg
import cv2
import sys
import signal
import platform
from moviepy.editor import *
from pedalboard import *
from pedalboard.io import AudioFile
from tqdm import tqdm
import tkinter as tk
import sqlite3
import re
from scipy.spatial import distance
from tkinter import Tk
from tkinter.filedialog import askdirectory


from anonfaces import __version__
from anonfaces.main.centerface import CenterFace
from anonfaces.gui.dbfacegui import FaceDatabaseApp
#from main import __version__               #to run as standalone uncomment these three
#from main.centerface import CenterFace     #then comment the three above
#from gui.dbfacegui import FaceDatabaseApp




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
            roibox = frame[y1:y2, x1:x2]
            # Get y and x coordinate lists of the "bounding ellipse"
            ey, ex = skimage.draw.ellipse((y2 - y1) // 2, (x2 - x1) // 2, (y2 - y1) // 2, (x2 - x1) // 2)
            roibox[ey, ex] = blurred_box[ey, ex]
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


def load_dlib_params():
    #dlib face detector and face recognition models

    shape_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'database',
        'shape_predictor_5_face_landmarks.dat'
        )

    face_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'database',
        'dlib_face_recognition_resnet_model_v1.dat'
        )
    import dlib
    detector = dlib.get_frontal_face_detector()
    sp = dlib.shape_predictor(shape_path)
    facerec = dlib.face_recognition_model_v1(face_path)
    return detector, sp, facerec


#leaving here to fallback to directory loading faces
def load_reference_faces(reference_directory, detector, sp, facerec):
    reference_descriptors = []
    reference_names = []
    for file_name in os.listdir(reference_directory):
        if file_name.endswith(('.jpg', '.jpeg', '.png')): #only tested with these formats. others might work
            img_path = os.path.join(reference_directory, file_name)
            img = dlib.load_rgb_image(img_path)
            dets = detector(img, 1)#reduce the number of scales to speed up detection? 1 default here

            if len(dets) > 0:
                shape = sp(img, dets[0])
                face_descriptor = facerec.compute_face_descriptor(img, shape)
                reference_descriptors.append(np.array(face_descriptor))
                # Clean up the name by removing numbers and file extensions so we can have multiple images John_Doe1.jpg
                cleaned_name = re.sub(r'\d+', '', os.path.splitext(file_name)[0])
                cleaned_name = cleaned_name.replace('_', ' ').title()
                reference_names.append(cleaned_name)
            else:
                tqdm.write(f"No face detected in {img_path}")

    return reference_descriptors, reference_names


# check if a detected face matches any reference face
def is_known_face(face_descriptor, reference_face_descriptors, reference_names, reference_image_ids, threshold):
    for ref_descriptor, ref_name, ref_id in zip(reference_face_descriptors, reference_names, reference_image_ids):
    #for ref_descriptor in reference_face_descriptors:
        
        #uncomment to verify multiple image checks per person via image id in sql.
        #print(f"Checking against: {ref_name} - {ref_id}")
        dist = distance.euclidean(face_descriptor, ref_descriptor)
        if dist < threshold:
            return ref_name
    return None


def load_reference_faces_from_db(database_path, detector, sp, facerec):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    #print(f"Database path: {database_path}")

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
        
        # process the image using dlib
        dets = detector(img, 1)
        if len(dets) > 0:
            shape = sp(img, dets[0])
            face_descriptor = facerec.compute_face_descriptor(img, shape)
            reference_descriptors.append(np.array(face_descriptor))
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
        face_recog, fr_name, detector, sp, facerec,
        reference_face_descriptors=None, reference_names=None, reference_image_ids=None, fr_thresh=0.60,
):
    for i, det in enumerate(dets):
        boxes, score = det[:4], det[4]
        x1, y1, x2, y2 = boxes.astype(int)
        x1, y1, x2, y2 = scale_bb(x1, y1, x2, y2, mask_scale)
        y1, y2 = max(0, y1), min(frame.shape[0] - 1, y2)
        x1, x2 = max(0, x1), min(frame.shape[1] - 1, x2)

        if face_recog and reference_face_descriptors:
            # Extract face and create an embedding - Now only done if face recog is on
            face = frame[y1:y2, x1:x2]
            face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
            #face_rgb = cv2.resize(face_rgb, (128, 128))  # option to resize for faster times and still match - testing on an off locally
            dets = detector(face_rgb, 1)#reduce the number of scales to speed up detection? 1 default here
            
            if len(dets) > 0:
                shape = sp(face_rgb, dets[0])
                face_descriptor = facerec.compute_face_descriptor(face_rgb, shape)
                face_descriptor = np.array(face_descriptor)

                if face_descriptor.ndim != 1:
                    face_descriptor = face_descriptor.flatten()#seems slower with no benefit yet - info below
                    # uncomment to see what dimension the array is in.
                    #tqdm.write(f'face_descriptor.ndim: {face_descriptor.ndim}')
                
                # Check if the detected face is a known reference face
                matched_name = is_known_face(face_descriptor, reference_face_descriptors, reference_names, reference_image_ids, threshold=fr_thresh)
                if matched_name:
                    if fr_name:
                        text_size = cv2.getTextSize(matched_name, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
                        text_x = x1 + (x2 - x1 - text_size[0]) // 2
                        text_y = y1 + text_size[1]
                        cv2.putText(frame, matched_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (36, 255, 12), 2)

                    continue  # Hopefully skip blurring for known faces

        draw_det(
            frame, score, i, x1, y1, x2, y2,
            replacewith=replacewith,
            ellipse=ellipse,
            draw_scores=draw_scores,
            replaceimg=replaceimg,
            mosaicsize=mosaicsize
        )



def cam_read_iter(reader):
    while True:
        yield reader.get_next_data()


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
        detector=None, sp=None, facerec=None
):
    try:
        if 'fps' in ffmpeg_config:
            reader: imageio.plugins.ffmpeg.FfmpegFormat.Reader = imageio.get_reader(ipath, fps=ffmpeg_config['fps'])
        else:
            reader: imageio.plugins.ffmpeg.FfmpegFormat.Reader = imageio.get_reader(ipath)

        meta = reader.get_meta_data()
        _ = meta['size']
    except:
        if cam:
            tqdm.write(f'Could not find video device {ipath}. Please set a valid input.')
        else:
            tqdm.write(f'Could not open file {ipath} as a video file with imageio. Skipping file...')
        return

    if cam:
        nframes = None
        read_iter = cam_read_iter(reader)
    else:
        read_iter = reader.iter_data()
        if platform.system() == "Darwin":
            nframes = None  # Frame counting fails on macOS - do not have a mac to test - someone? anyone?
        else:
            nframes = reader.count_frames()
    if nested:
        bar = tqdm(dynamic_ncols=True, total=nframes, position=1, leave=True)
    else:
        bar = tqdm(dynamic_ncols=True, total=nframes)

    if opath is not None:
        _ffmpeg_config = ffmpeg_config.copy()
        #  If fps is not explicitly set in ffmpeg_config, use source video fps value
        _ffmpeg_config.setdefault('fps', meta['fps'])
        _ffmpeg_config.setdefault('ffmpeg_log_level', 'panic')
        if keep_audio and meta.get('audio_codec'):  # Carry over audio from input path but change audio to libmp3lame
            _ffmpeg_config.setdefault('audio_path', ipath)
            _ffmpeg_config.setdefault('audio_codec', 'libmp3lame')
        # Carry over audio from input path, use "copy" codec (no transcoding)
        if copy_acodec and meta.get('audio_codec'): #use "copy" codec off by default but copies direct audio codec
            _ffmpeg_config.setdefault('audio_path', ipath)
            _ffmpeg_config.setdefault('audio_codec', 'copy')
        codec = _ffmpeg_config.get('codec', 'libx264')
        fps = _ffmpeg_config.get('fps', None)
        bitrate = _ffmpeg_config.get('bitrate', None)
        audio_codec = _ffmpeg_config.get('audio_codec', None)
        audio_bitrate = _ffmpeg_config.get('audio_bitrate', None)
        pix_fmt = _ffmpeg_config.get('pix_fmt', None)
        sample_rate = _ffmpeg_config.get('sample_rate', None)
        writer: imageio.plugins.ffmpeg.FfmpegFormat.Writer = imageio.get_writer(
            opath, format='FFMPEG', mode='I', **_ffmpeg_config
        )
        #work in progess due to possible missing params
        if info:
            ffmpeg_command = f"ffmpeg -y -loglevel {_ffmpeg_config['ffmpeg_log_level']} -i {ipath} "
    
            if fps:
                ffmpeg_command += f"-r {fps} "
            if bitrate:
                ffmpeg_command += f"-b:v {bitrate} "
            if pix_fmt:
                ffmpeg_command += f"-pix_fmt {pix_fmt} "
    
            # Add video codec
            ffmpeg_command += f"-c:v {codec} "
    
            # If audio is specified
            if audio_codec:
                ffmpeg_command += f"-c:a {audio_codec} "
                if audio_bitrate:
                    ffmpeg_command += f"-b:a {audio_bitrate} "
                if sample_rate:
                    ffmpeg_command += f"-ar {sample_rate} "
    
            ffmpeg_command += f"{opath}"
            
            tqdm.write(f"FFMPEG Command: {ffmpeg_command}")
            tqdm.write("")

    for frame in read_iter:
        #signal flag during ffmpeg video_detect
        if stop_ffmpeg:
            bar.close()
            reader.close()
            if opath is not None:
                writer.close()
            tqdm.write(f"")
            tqdm.write("Stop signal received, stopping cleanly...")
            tqdm.write(f"")
            return
        
        # Perform network inference, get bb dets but discard landmark predictions
        dets, _ = centerface(frame, threshold=threshold)

        anonymize_frame(
            dets, frame, mask_scale=mask_scale,
            replacewith=replacewith, ellipse=ellipse, draw_scores=draw_scores,
            replaceimg=replaceimg, mosaicsize=mosaicsize,
            #new below
            face_recog=face_recog,
            reference_face_descriptors=reference_face_descriptors,
            reference_names=reference_names, fr_thresh=fr_thresh,
            fr_name=fr_name, reference_image_ids=reference_image_ids,
            detector=detector, sp=sp, facerec=facerec
        )

        if opath is not None:
            writer.append_data(frame)

        if enable_preview:
            cv2.imshow('Preview of anonymization results (quit by pressing Q or Escape)', frame[:, :, ::-1])  # RGB -> RGB
            if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:  # 27 is the escape key code
                cv2.destroyAllWindows()
                break
        bar.update()
    reader.close()
    if opath is not None:
        writer.close()
    bar.close()


EXTRACTED_AUDIO = "extracted_audio.wav"
DISTORTED_AUDIO = "distorted_audio.wav"


def extract_audio_from_video(v_path: str, a_path: str):
    video = VideoFileClip(v_path)
    video.audio.write_audiofile(a_path)

def distort_audio(audio_input: str, audio_output: str, sample_rate: float = 44100.0):
    with AudioFile(audio_input).resampled_to(sample_rate) as f:
        audio = f.read(f.frames)

    board = Pedalboard([
        Gain(gain_db=5),
        PitchShift(semitones=-2.5),
    ])
    d_audio = board(audio, sample_rate)

    with AudioFile(audio_output, 'w', sample_rate, d_audio.shape[0]) as f:
        f.write(d_audio)

def combine_video_audio(v_path: str, a_path: str, o_path: str):
    vclip = VideoFileClip(v_path)
    aclip = AudioFileClip(a_path)

    vclip.audio = aclip
    vclip.write_videofile(o_path, codec="libx264", logger=None)
    
def distort_now(ipath, opath):

    # Add "_distorted" to the output file name
    root, ext = os.path.splitext(opath)
    dopath = f"{root}_distorted{ext}"

    # Copy opath to dopath
    shutil.copy(opath, dopath)

    # Extract audio from the original video
    extract_audio_from_video(ipath, EXTRACTED_AUDIO)

    # Distort the extracted audio
    distort_audio(EXTRACTED_AUDIO, DISTORTED_AUDIO)

    # Combine the processed audio with the original video
    combine_video_audio(opath, DISTORTED_AUDIO, dopath)
    
    # Remove temporary audio files
    os.remove(EXTRACTED_AUDIO)
    os.remove(DISTORTED_AUDIO)
    

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
        detector=None, sp=None, facerec=None
):
    frame = imageio.v3.imread(ipath)
    
    if keep_metadata:
        # Source image EXIF metadata retrieval via imageio V3 lib
        metadata = imageio.v3.immeta(ipath)
        exif_dict = metadata.get("exif", None)

    # Perform network inference, get bb dets but discard landmark predictions
    dets, _ = centerface(frame, threshold=threshold)

    anonymize_frame(
        dets, frame, mask_scale=mask_scale,
        replacewith=replacewith, ellipse=ellipse, draw_scores=draw_scores,
        replaceimg=replaceimg, mosaicsize=mosaicsize,
        #new below
        face_recog=face_recog,
        reference_face_descriptors=reference_face_descriptors,
        reference_names=reference_names, fr_thresh=fr_thresh,
        fr_name=fr_name, reference_image_ids=reference_image_ids,
        detector=detector, sp=sp, facerec=facerec
    )

    if enable_preview:
        cv2.imshow('Preview of anonymization results (quit by pressing Q or Escape)', frame[:, :, ::-1])  # RGB -> RGB
        if cv2.waitKey(0) & 0xFF in [ord('q'), 27]:  # 27 is the escape key code
            cv2.destroyAllWindows()

    imageio.imsave(opath, frame)
    
    # save the image/s with or without EXIF metadata based on its availability due to error with exif=None
    # this is due to PIL (used by imageio for saving JPEG images) trying to access the len() of exif, but exif is None
    if keep_metadata and exif_dict:
        imageio.imsave(opath, frame, exif=exif_dict)
    else:
        imageio.imsave(opath, frame)

    #tqdm.write(f'Output saved to {opath}')


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
                         replaceimg = None
                         ):
    """
    Method for getting an anonymized image without CLI
    returns frame
    """

    centerface = CenterFace(in_shape=None, backend='auto')
    dets, _ = centerface(frame, threshold=threshold)

    anonymize_frame(
        dets, frame, mask_scale=mask_scale,
        replacewith=replacewith, ellipse=ellipse, draw_scores=draw_scores,
        replaceimg=replaceimg
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
        '--fr-thresh', '-ft', type=float, default=0.60,
        help="Set the face recognition threshold. Default is 0.60 here and seems standard. More testing needed")
    parser.add_argument(
        '--distort-audio', '-da', default=False, action='store_true',
        help='Enable audio distortion for the output video (applies pitch shift and gain effects to the audio). This automatically applies --keep-audio but will not work with --copy-acodec due to MoviePy')
    parser.add_argument(
        '--keep-audio', '-k', default=False, action='store_true',
        help='Keep audio from video source file and copy it over to the output (only applies to videos).')
    parser.add_argument(
        '--copy-acodec', '-ca', default=False, action='store_true',
        help='Keep audio codec from video source file.')
    parser.add_argument(
        '--ffmpeg-config', default={"codec": "libx264"}, type=json.loads,
        help='FFMPEG config arguments for encoding output videos. This argument is expected in JSON notation. For a list of possible options, refer to the ffmpeg-imageio docs. Default: \'{"codec": "libx264"}\'.  Windows example --ffmpeg-config "{\\"fps\\": 10, \\"bitrate\\": \\"1000k\\"}"')  # See https://imageio.readthedocs.io/en/stable/format_ffmpeg.html#parameters-for-saving
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
    
    # Directory only shows if face recog arg = on
    if args.face_recog:
        detector, sp, facerec = load_dlib_params()
        database_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'database',
            'face_db.sqlite'
        )
        reference_face_descriptors, reference_names, reference_image_ids = load_reference_faces_from_db(database_path, detector, sp, facerec)
        #uncomment for local directory reference faces-leaving in here for a fallback later
        #will keep both but figure out the best way to handle the option.....
        #reference_directory = select_reference_directory()
        #reference_face_descriptors, reference_names = load_reference_faces(reference_directory)
    else:
        reference_face_descriptors, reference_names, reference_image_ids = [], [], []
    
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
        replaceimg = imageio.imread(args.replaceimg)
        tqdm.write(f'After opening {args.replaceimg} shape: {replaceimg.shape}')


    # TODO: scalar downscaling setting (-> in_shape), preserving aspect ratio
    centerface = CenterFace(in_shape=in_shape, backend=backend, override_execution_provider=execution_provider)

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
                #new below
                copy_acodec=copy_acodec,
                info=info,
                fr_thresh=args.fr_thresh,
                face_recog=args.face_recog,  # Pass the face recog argument
                reference_face_descriptors=reference_face_descriptors if args.face_recog else None,  # Pass reference descriptors if face recog = on
                reference_names=reference_names if args.face_recog else None,  # Pass reference names
                reference_image_ids=reference_image_ids if args.face_recog else None, #Pass the ids for testing - should not slow anything down.
                fr_name=args.fr_name,
                detector=detector if args.face_recog else None,
                sp=sp if args.face_recog else None,
                facerec=facerec if args.face_recog else None
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
                    #new below
                    fr_thresh=args.fr_thresh,
                    face_recog=args.face_recog,  # Pass the face recog argument
                    reference_face_descriptors=reference_face_descriptors if args.face_recog else None,  # Pass reference descriptors if face recog = on
                    reference_names=reference_names if args.face_recog else None,  # Pass reference names
                    reference_image_ids=reference_image_ids if args.face_recog else None, #Pass the ids for testing - should not slow anything down.
                    fr_name= args.fr_name,
                    detector=detector if args.face_recog else None,
                    sp=sp if args.face_recog else None,
                    facerec=facerec if args.face_recog else None
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