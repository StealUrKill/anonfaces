import os
import sys
import numpy as np
import cv2
from skimage import transform as trans
from tqdm import tqdm


# ArcFace standard alignment template for 112x112 input
# Points: left eye, right eye, nose tip, left mouth corner, right mouth corner
ARCFACE_DST = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041],
], dtype=np.float32)

MODEL_NAME = "w600k_r50.onnx"
MODEL_URL = "https://huggingface.co/public-data/insightface/resolve/main/models/buffalo_l/w600k_r50.onnx"


def get_default_model_path():
    model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database')
    return os.path.join(model_dir, MODEL_NAME)


def download_model(dest_path):
    import urllib.request
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tqdm.write(f"Downloading ArcFace model ({MODEL_NAME})...")
    tqdm.write("This is a one-time download (~166 MB).")

    def _progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 // total_size)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  {mb_done:.1f}/{mb_total:.1f} MB ({pct}%)")
            sys.stdout.flush()

    urllib.request.urlretrieve(MODEL_URL, dest_path, reporthook=_progress)
    sys.stdout.write("\n")
    tqdm.write("Download complete.")


def align_face(img, landmarks):
    """Align face using 5-point landmarks to ArcFace 112x112 template.

    Args:
        img: Full frame image (RGB, any size)
        landmarks: 5x2 array of facial landmark coordinates in frame space

    Returns:
        Aligned 112x112 face image (RGB)
    """
    tform = trans.SimilarityTransform()
    tform.estimate(landmarks, ARCFACE_DST)
    M = tform.params[0:2, :]
    aligned = cv2.warpAffine(img, M, (112, 112), borderValue=0.0)
    return aligned


class ArcFaceONNX:
    """ArcFace face recognition using ONNX Runtime (w600k_r50)."""

    def __init__(self, model_path=None, backend='auto', override_execution_provider=None):
        if model_path is None:
            model_path = get_default_model_path()

        if not os.path.exists(model_path):
            download_model(model_path)

        import onnxruntime
        import platform as _platform

        if override_execution_provider:
            providers = [override_execution_provider]
        elif backend in ('onnxrt', 'auto'):
            available = onnxruntime.get_available_providers()
            if "CUDAExecutionProvider" in available:
                providers = ["CUDAExecutionProvider"]
            else:
                providers = available
        else:
            providers = ['CPUExecutionProvider']

        # Handle OpenVINO DLL loading on Windows
        if _platform.system() == "Windows" and any('openvino' in p.lower() for p in providers):
            try:
                import onnxruntime.tools.add_openvino_win_libs as utils
                utils.add_openvino_libs_to_path()
            except Exception:
                pass

        self.session = onnxruntime.InferenceSession(model_path, providers=providers)
        input_cfg = self.session.get_inputs()[0]
        self.input_name = input_cfg.name
        self.output_name = self.session.get_outputs()[0].name

    def get_embedding(self, aligned_face):
        """Compute 512-D face embedding from aligned 112x112 face.

        Args:
            aligned_face: 112x112 RGB image (uint8)

        Returns:
            L2-normalized 512-D embedding vector
        """
        img = aligned_face.astype(np.float32)
        img = (img - 127.5) / 127.5
        # HWC -> CHW, add batch dim: (1, 3, 112, 112)
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)

        embedding = self.session.run([self.output_name], {self.input_name: img})[0]
        embedding = embedding.flatten()
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    def get_embeddings_batch(self, aligned_faces):
        """Compute 512-D face embeddings for a batch of aligned faces in one inference call.

        Args:
            aligned_faces: list of 112x112 RGB images (uint8)

        Returns:
            (N, 512) array of L2-normalized embedding vectors
        """
        if len(aligned_faces) == 0:
            return np.empty((0, 512), dtype=np.float32)
        batch = np.stack([
            np.transpose((face.astype(np.float32) - 127.5) / 127.5, (2, 0, 1))
            for face in aligned_faces
        ])  # (N, 3, 112, 112)
        embeddings = self.session.run([self.output_name], {self.input_name: batch})[0]
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        return embeddings / norms

    def compute_similarity(self, emb1, emb2):
        """Cosine similarity between two L2-normalized embeddings."""
        return float(np.dot(emb1, emb2))
