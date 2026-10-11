# GenD commit 387a42266dd385fbe8f7626c5d3aa03eea3bfaab; MIT, see licenses/GenD-MIT.txt.
import cv2
import numpy as np

def align_face(
    img: np.ndarray,
    landmarks: np.ndarray,
    target_size: None | tuple = None,
    scale: float = 1.3,
    mask: np.ndarray = None,
):
    """
    Aligns a face based on 5-point facial landmarks (eyes, nose, mouth corners).

    Args:
        img: Input image containing the face
        landmarks: 5-point facial landmarks array with shape (5, 2)
        target_size: Desired output size as (width, height) tuple
        scale: Scaling factor to control how much context around the face to include
        stabilize_features: Whether to use standard reference points for consistent alignment
        return_transform: Whether to return the transformation matrix
        mask: Resize mask the same way as img

    Returns:
        Aligned face image with specified target_size
        Optionally returns the transformation matrix if return_transform=True
    """
    dst = np.array(
        [
            [0.34, 0.46],
            [0.66, 0.46],
            [0.5, 0.64],
            [0.37, 0.82],
            [0.63, 0.82],
        ],
        dtype=np.float32,
    )

    if target_size is None:
        # Compute desired distances between all pairs
        desired_dists = np.linalg.norm(landmarks[:, None, :] - landmarks[None, :, :], axis=-1)

        # Destination distances between all pairs
        dst_dists = np.linalg.norm(dst[:, None, :] - dst[None, :, :], axis=-1)

        # Take upper triangle of the distance matrix
        upper_triangle_indices = np.triu_indices(len(dst), k=1)
        dst_dists = dst_dists[upper_triangle_indices]
        desired_dists = desired_dists[upper_triangle_indices]

        # Approximate target size
        approx_size = np.round(np.mean(desired_dists / dst_dists) * scale).astype(int)
        target_size = (approx_size, approx_size)

    dst[:, 0] = dst[:, 0] * target_size[0]
    dst[:, 1] = dst[:, 1] * target_size[1]

    margin_rate = scale - 1
    x_margin = target_size[0] * margin_rate / 2.0
    y_margin = target_size[1] * margin_rate / 2.0

    # move
    dst[:, 0] += x_margin
    dst[:, 1] += y_margin

    # resize
    dst[:, 0] *= target_size[0] / (target_size[0] + 2 * x_margin)
    dst[:, 1] *= target_size[1] / (target_size[1] + 2 * y_margin)

    src = landmarks.astype(np.float32)

    M = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)[0]

    img = cv2.warpAffine(img, M, target_size, flags=cv2.INTER_LINEAR)

    # Warp landmarks, show
    # landmarks = cv2.transform(np.expand_dims(landmarks, axis=0), M)[0]
    # for point in landmarks:
    #     cv2.circle(img, tuple(point.astype(int)), 2, (0, 255, 0), -1)

    if mask is not None:
        mask = cv2.warpAffine(mask, M, target_size, flags=cv2.INTER_NEAREST)

    return img, mask
