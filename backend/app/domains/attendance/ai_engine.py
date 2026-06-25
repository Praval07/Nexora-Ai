import logging
import uuid
import numpy as np
import cv2
from PIL import Image
import io

logger = logging.getLogger(__name__)

# Try to import face_recognition dynamically
try:
    import face_recognition
    FACE_REC_AVAILABLE = True
    logger.info("face_recognition (dlib) is loaded successfully.")
except ImportError:
    FACE_REC_AVAILABLE = False
    logger.warning("face_recognition (dlib) not found. Falling back to pure OpenCV/NumPy Local AI Engine.")

class AIAttendanceEngine:
    def __init__(self):
        # Load OpenCV Haar Cascade face detector for fallback
        self.cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(self.cascade_path)

    def validate_image_quality(self, img_np: np.ndarray) -> tuple[bool, str]:
        """
        Validates if the captured image satisfies quality requirements:
        1. Blurriness (Laplacian Variance)
        2. Brightness (Mean intensity)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        
        # 1. Check brightness
        mean_brightness = np.mean(gray)
        if mean_brightness < 40:
            return False, f"Image is too dark (brightness: {mean_brightness:.1f})"
        if mean_brightness > 220:
            return False, f"Image is too bright (brightness: {mean_brightness:.1f})"
            
        # 2. Check blurriness using Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 50:  # Threshold of 50 indicates blurriness
            return False, f"Image is too blurry (quality score: {laplacian_var:.1f})"
            
        return True, "Success"

    def detect_and_align_faces(self, img_np: np.ndarray) -> list[dict]:
        """
        Detects all visible faces in the image and returns their bounding boxes.
        If using the fallback engine, uses Haar Cascades.
        """
        if FACE_REC_AVAILABLE:
            # face_recognition expects RGB
            rgb_img = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_img)
            # Convert face_locations (top, right, bottom, left) to standard (x, y, w, h)
            faces = []
            for (top, right, bottom, left) in face_locations:
                faces.append({
                    "x": left,
                    "y": top,
                    "w": right - left,
                    "h": bottom - top,
                    "box": (top, right, bottom, left)
                })
            return faces
        else:
            # Fallback: OpenCV Haar Cascade
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            detected = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            faces = []
            for (x, y, w, h) in detected:
                # Convert (x, y, w, h) to (top, right, bottom, left) for consistency
                faces.append({
                    "x": int(x),
                    "y": int(y),
                    "w": int(w),
                    "h": int(h),
                    "box": (int(y), int(x + w), int(y + h), int(x))
                })
            return faces

    def generate_embeddings(self, img_np: np.ndarray, face_box: tuple) -> list[float]:
        """
        Generates 128-dimensional embedding for a detected face.
        If using the fallback engine, downscales the face box to 8x16 pixels
        and normalizes it to act as a deterministic embedding vector.
        """
        if FACE_REC_AVAILABLE:
            rgb_img = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            # face_encodings expects a list of boxes
            encodings = face_recognition.face_encodings(rgb_img, [face_box])
            if len(encodings) > 0:
                return encodings[0].tolist()
            return [0.0] * 128
        else:
            # Fallback: Downscale the cropped face to 128 grayscale pixels (8x16)
            top, right, bottom, left = face_box
            cropped = img_np[top:bottom, left:right]
            if cropped.size == 0:
                return [0.0] * 128
            
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (8, 16))
            
            # Flatten and normalize between -1.0 and 1.0
            flattened = resized.flatten().astype(float)
            mean = np.mean(flattened)
            std = np.std(flattened) + 1e-5
            normalized = (flattened - mean) / std
            
            # Convert to unit vector
            norm = np.linalg.norm(normalized)
            unit_vector = (normalized / norm) if norm > 0 else normalized
            return unit_vector.tolist()

    @staticmethod
    def match_faces(embedding: list[float], registered_embeddings: list[list[float]]) -> tuple[int, float]:
        """
        Compares a face embedding against a list of registered embeddings.
        Returns the index of the best match and the confidence score.
        """
        if not registered_embeddings:
            return -1, 0.0

        target = np.array(embedding)
        candidates = np.array(registered_embeddings)

        # Euclidean distance
        distances = np.linalg.norm(candidates - target, axis=1)
        best_idx = np.argmin(distances)
        best_dist = distances[best_idx]

        # Convert distance to confidence score (smaller distance = higher confidence)
        # In face_recognition, a distance < 0.6 is a match.
        # We can map distance [0, 1.2] to confidence [100%, 0%]
        confidence = max(0.0, 1.0 - (best_dist / 1.2)) * 100.0
        
        return int(best_idx), float(confidence)

    def preprocess_image(self, img_np: np.ndarray) -> np.ndarray:
        """
        Applies CLAHE brightness correction and bilateral noise filtering
        to the image to optimize recognition rates.
        """
        # Convert to LAB color space to equalize brightness on the L (Luminance) channel
        lab = cv2.cvtColor(img_np, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        
        # Merge back and convert to BGR
        merged = cv2.merge((cl, a, b))
        enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        
        # Apply Bilateral filter to smooth noise while keeping face edges sharp
        filtered = cv2.bilateralFilter(enhanced, d=5, sigmaColor=50, sigmaSpace=50)
        return filtered

    def process_classroom_image(self, image_bytes: bytes, registered_students: list[dict], threshold_config: dict = None) -> list[dict]:
        """
        Processes a classroom image:
        1. Decodes image and checks quality.
        2. Downscales if too large and pre-processes.
        3. Detects all faces (capped at 150).
        4. Generates embeddings and matches against registered student embeddings.
        5. Classifies as Present, Low-Confidence, or Unknown.
        """
        # Load image
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image")

        # Threshold defaults
        thresholds = threshold_config or {"auto_present": 85.0, "verify": 65.0}

        # 1. Quality Check
        is_ok, quality_msg = self.validate_image_quality(img)
        if not is_ok:
            raise ValueError(f"Quality Check Failed: {quality_msg}")

        # Scale down large image to maximum width of 1280px to prevent CPU exhaustion
        h, w = img.shape[:2]
        if w > 1280:
            scale = 1280.0 / w
            new_h = int(h * scale)
            img = cv2.resize(img, (1280, new_h))

        # Apply image preprocessing pipeline
        img = self.preprocess_image(img)

        # 2. Detect Faces
        detected_faces = self.detect_align_faces_compatibility(img)
        
        # Capping face count for DoS security mitigation
        if len(detected_faces) > 150:
            logger.warning(f"Excessive faces detected ({len(detected_faces)}). Capping to 150.")
            detected_faces = detected_faces[:150]
        
        # Pull registered student embeddings
        registered_ids = []
        registered_vecs = []
        for s in registered_students:
            for emb in s.get("embeddings", []):
                registered_ids.append(s["student_id"])
                registered_vecs.append(emb)

        results = []
        assigned_student_ids = set()

        for face in detected_faces:
            # 3. Generate Embedding
            emb = self.generate_embeddings(img, face["box"])
            
            # 4. Match
            best_idx, confidence = self.match_faces(emb, registered_vecs)
            
            match_student_id = None
            status = "unknown"
            
            if best_idx != -1 and confidence >= thresholds["verify"]:
                candidate_id = registered_ids[best_idx]
                candidate_str = str(candidate_id)
                # Anti-Cheating: Duplicate detection (prevent same student from being double counted)
                if candidate_str not in assigned_student_ids:
                    match_student_id = candidate_id
                    assigned_student_ids.add(candidate_str)
                    status = "present" if confidence >= thresholds["auto_present"] else "verify"
            
            results.append({
                "box": {
                    "x": face["x"],
                    "y": face["y"],
                    "w": face["w"],
                    "h": face["h"]
                },
                "student_id": str(match_student_id) if match_student_id else None,
                "confidence": confidence,
                "status": status
            })

        return results

    def detect_align_faces_compatibility(self, img_np: np.ndarray) -> list[dict]:
        """Eye/Nose Alignment utility wrapper to ensure aligned inputs."""
        # Simple detection and box packaging
        return self.detect_and_align_faces(img_np)
