"""
inference.py
Flood extent inference using the trained ResNet34 U-Net.

Main frontend/backend function:
    predict_file(input_path, model_path, output_path)

Expected SAR input:
    2-band GeoTIFF: Band 1 = VV, Band 2 = VH
    OR NumPy array with shape (2, H, W)

Input types:
    uint8  = already converted using the project's preprocessing [0-255]
    db     = dB SAR values
    linear = linear SAR values
"""

import argparse
import json
import logging
import warnings
from pathlib import Path

import numpy as np
import torch
import segmentation_models_pytorch as smp

# Guard rasterio to prevent crash if Windows Application Control blocks C-DLLs
try:
    import rasterio
    import rasterio.errors
    from rasterio.features import shapes
    warnings.filterwarnings("ignore", category=getattr(rasterio.errors, "NotGeoreferencedWarning", UserWarning))
except (ImportError, Exception):
    rasterio = None

LOGGER = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.40
DEFAULT_WINDOW = 256
DEFAULT_STRIDE = 64
DEFAULT_BATCH_SIZE = 16


def _box_filter_2d(arr: np.ndarray, size: int) -> np.ndarray:
    """Pure-NumPy 2D box filter using integral images (no scipy dependency)."""
    h, w = arr.shape
    pad = size // 2
    padded = np.pad(arr, pad, mode="reflect")
    integral = np.pad(np.cumsum(np.cumsum(padded, axis=0), axis=1), ((1, 0), (1, 0)))
    y0, y1 = 0, h
    x0, x1 = 0, w
    res = (
        integral[y1 + size, x1 + size]
        - integral[y0, x1 + size]
        - integral[y1 + size, x0]
        + integral[y0, x0]
    )
    return res / (size * size)


def load_model(model_path, device=None):
    """Load the trained ResNet34 U-Net."""
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = smp.Unet(
        encoder_name="resnet34",
        encoder_weights=None,
        in_channels=2,
        classes=1,
    ).to(device)

    checkpoint = torch.load(model_path, map_location=device)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]

    model.load_state_dict(checkpoint)
    model.eval()
    return model, device


def lee_filter(img, size=5):
    """Lee speckle filter."""
    img = img.astype(np.float32)
    mean = _box_filter_2d(img, size)
    sq_mean = _box_filter_2d(img ** 2, size)
    var = np.maximum(sq_mean - mean ** 2, 0)
    w = var / (var + np.var(img) + 1e-12)
    return mean + w * (img - mean)


def db_to_uint8(db):
    """Clip dB to [-30, 5] and convert to 0-255."""
    db = np.clip(db, -30, 5)
    return ((db + 30) / 35 * 255).astype(np.uint8)


def linear_to_uint8_db(linear):
    """Linear SAR -> Lee filter -> dB -> uint8."""
    filt = lee_filter(linear)
    db = 10 * np.log10(np.maximum(filt, 1e-6))
    return db_to_uint8(db)


def prepare_sar(arr, input_type="uint8"):
    """
    Prepare a two-channel SAR array.
    Band 1 = VV, Band 2 = VH.
    """
    arr = np.asarray(arr)

    if arr.ndim != 3 or arr.shape[0] != 2:
        raise ValueError(
            f"Expected SAR array with shape (2,H,W), got {arr.shape}"
        )

    arr = arr.astype(np.float32)

    if input_type == "uint8":
        return np.clip(arr, 0, 255).astype(np.uint8)

    if input_type == "db":
        return np.stack(
            [db_to_uint8(lee_filter(arr[i])) for i in range(2)],
            axis=0,
        )

    if input_type == "linear":
        return np.stack(
            [linear_to_uint8_db(arr[i]) for i in range(2)],
            axis=0,
        )

    raise ValueError("input_type must be 'uint8', 'db', or 'linear'")


@torch.no_grad()
def predict_scene(
    model,
    img_u8,
    device,
    window=DEFAULT_WINDOW,
    stride=DEFAULT_STRIDE,
    batch_size=DEFAULT_BATCH_SIZE,
):
    """Run overlapping sliding-window segmentation on uint8 SAR input."""
    _, height, width = img_u8.shape

    def pad_amount(n):
        if n < window:
            return window - n
        return (-(n - window)) % stride

    pad_h = pad_amount(height)
    pad_w = pad_amount(width)

    x = np.pad(img_u8, ((0, 0), (0, pad_h), (0, pad_w)))
    padded_h, padded_w = x.shape[1:]

    prob = np.zeros((padded_h, padded_w), dtype=np.float32)
    count = np.zeros((padded_h, padded_w), dtype=np.float32)

    coords = [
        (r, c)
        for r in range(0, padded_h - window + 1, stride)
        for c in range(0, padded_w - window + 1, stride)
    ]

    use_amp = str(device).startswith("cuda")

    for start in range(0, len(coords), batch_size):
        batch_coords = coords[start : start + batch_size]

        batch = np.stack([
            x[:, r : r + window, c : c + window]
            for r, c in batch_coords
        ])

        xb = torch.from_numpy(batch).float().to(device)

        # Standard U-Net normalization: maps [0, 255] to [-1.0, 1.0]
        xb = (xb / 255.0 - 0.5) / 0.5

        if use_amp:
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(xb)
        else:
            logits = model(xb)

        predictions = torch.sigmoid(logits)
        predictions = predictions.float().squeeze(1).cpu().numpy()

        for (r, c), prediction in zip(batch_coords, predictions):
            prob[r : r + window, c : c + window] += prediction
            count[r : r + window, c : c + window] += 1

    return (prob / np.maximum(count, 1))[:height, :width]


@torch.no_grad()
def predict_scene_tta(
    model,
    img_u8,
    device,
    window=DEFAULT_WINDOW,
    stride=DEFAULT_STRIDE,
    batch_size=DEFAULT_BATCH_SIZE,
):
    """
    Horizontal-flip Test-Time Augmentation (TTA):
    1. Infer on original SAR image
    2. Infer on horizontally flipped SAR image
    3. Reverse the flipped probability map
    4. Average combined probabilities
    """
    # 1. Original pass
    prob_orig = predict_scene(
        model, img_u8, device, window=window, stride=stride, batch_size=batch_size
    )

    # 2. Horizontally flipped pass
    img_flipped = np.ascontiguousarray(img_u8[:, :, ::-1])
    prob_flip_raw = predict_scene(
        model, img_flipped, device, window=window, stride=stride, batch_size=batch_size
    )

    # 3. Reverse flipped probability map back
    prob_flip = np.ascontiguousarray(prob_flip_raw[:, ::-1])

    # 4. Average combined probabilities
    return (prob_orig + prob_flip) / 2.0


def _extract_pil_geotiff_profile(img, height, width):
    """Extract GeoTIFF metadata tags using PIL."""
    profile = {
        "count": 2,
        "height": height,
        "width": width,
        "dtype": "uint8",
        "crs": None,
        "transform": None,
        "tags": {},
        "bounds": None,
    }
    tags = getattr(img, "tag_v2", getattr(img, "tag", {}))

    # Tag 270: ImageDescription
    if 270 in tags:
        try:
            meta = json.loads(tags[270])
            if isinstance(meta, dict):
                profile["tags"].update(meta)
                if "crs" in meta:
                    profile["crs"] = meta["crs"]
                if "transform" in meta:
                    profile["transform"] = meta["transform"]
                if "bounds" in meta:
                    profile["bounds"] = meta["bounds"]
                if "ACQUISITION_DATE" in meta:
                    profile["tags"]["ACQUISITION_DATE"] = meta["ACQUISITION_DATE"]
        except Exception:
            pass

    # Tag 33550 (ModelPixelScaleTag) and Tag 33922 (ModelTiepointTag)
    if 33550 in tags and 33922 in tags:
        scale = tags[33550]
        tiepoint = tags[33922]
        if len(scale) >= 2 and len(tiepoint) >= 5:
            dx, dy = float(scale[0]), float(scale[1])
            x0, y0 = float(tiepoint[3]), float(tiepoint[4])
            profile["transform"] = [x0, dx, 0.0, y0, 0.0, -dy]
            profile["bounds"] = [x0, y0 - height * dy, x0 + width * dx, y0]

    # Tag 34735 (GeoKeyDirectoryTag)
    if 34735 in tags and not profile.get("crs"):
        profile["crs"] = "EPSG:4326"

    return profile


def load_input(input_path, input_type="uint8"):
    """
    Load a 2-band GeoTIFF (Band 1 = VV, Band 2 = VH) or (2,H,W) NumPy array.
    Returns:
        (arr_u8, profile_dict_or_None)
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if input_path.suffix.lower() == ".npy":
        arr = np.load(input_path)
        return prepare_sar(arr, input_type), None

    if input_path.suffix.lower() in [".tif", ".tiff"]:
        # Try rasterio first if available
        if rasterio is not None:
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=getattr(rasterio.errors, "NotGeoreferencedWarning", UserWarning))
                    with rasterio.open(input_path) as src:
                        if src.count < 2:
                            raise ValueError(
                                "GeoTIFF must contain at least 2 bands: VV and VH."
                            )
                        arr = src.read([1, 2])
                        profile = src.profile.copy()
                        profile["crs"] = str(src.crs) if src.crs else None
                        profile["transform"] = [
                            src.transform.c, src.transform.a, src.transform.b,
                            src.transform.f, src.transform.d, src.transform.e
                        ]
                        profile["tags"] = src.tags()
                return prepare_sar(arr, input_type), profile
            except Exception:
                pass

        # Robust PIL fallback for reading GeoTIFF
        from PIL import Image

        with Image.open(input_path) as img:
            bands = []
            n_frames = getattr(img, "n_frames", 1)
            if n_frames >= 2:
                for i in range(2):
                    img.seek(i)
                    bands.append(np.array(img))
            else:
                arr_raw = np.array(img)
                if arr_raw.ndim == 3 and arr_raw.shape[2] >= 2:
                    bands = [arr_raw[:, :, 0], arr_raw[:, :, 1]]
                elif arr_raw.ndim == 3 and arr_raw.shape[0] >= 2:
                    bands = [arr_raw[0], arr_raw[1]]
                else:
                    raise ValueError(
                        "GeoTIFF must contain at least 2 bands: VV and VH."
                    )
            arr = np.stack(bands[:2], axis=0)
            profile = _extract_pil_geotiff_profile(img, arr.shape[1], arr.shape[2])
            return prepare_sar(arr, input_type), profile

    raise ValueError("Supported input formats: .tif, .tiff, .npy")


def save_mask(mask, output_path, profile=None):
    """Save binary mask."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if profile is not None and rasterio is not None:
        try:
            out_profile = profile.copy()
            out_profile.update(count=1, dtype="uint8", nodata=0)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=getattr(rasterio.errors, "NotGeoreferencedWarning", UserWarning))
                with rasterio.open(output_path, "w", **out_profile) as dst:
                    dst.write(mask.astype(np.uint8), 1)
            return
        except Exception:
            pass

    if output_path.suffix.lower() in [".tif", ".tiff"]:
        from PIL import Image
        Image.fromarray(mask.astype(np.uint8) * 255).save(output_path)
    else:
        np.save(output_path, mask.astype(np.uint8))


def calculate_area_km2(mask, profile=None):
    """Calculate positive-pixel area in km²."""
    positive_pixels = int(np.count_nonzero(mask))
    if profile is not None and profile.get("transform") is not None:
        t = profile["transform"]
        dx = abs(t[1]) if len(t) > 1 else 0.0001
        dy = abs(t[5]) if len(t) > 5 else 0.0001
        # If in degrees (EPSG:4326), 1 deg ~ 111,320 m
        if dx < 1.0:
            pixel_area_m2 = (dx * 111320.0) * (dy * 110540.0)
        else:
            pixel_area_m2 = dx * dy
    else:
        pixel_area_m2 = 10.0 * 10.0

    return (positive_pixels * pixel_area_m2) / 1_000_000.0


def generate_prediction_panel(
    vv_img: np.ndarray,
    mask: np.ndarray,
    acquisition_date: str,
    coverage_pct: float,
    output_png_path: Path,
) -> Path:
    """
    Generate side-by-side SAR visualization:
    - Panel 1: Sentinel-1 SAR VV Channel Amplitude
    - Panel 2: ResNet-34 U-Net Flood Inundation Mask Overlay
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    output_png_path = Path(output_png_path)
    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(10, 5), dpi=150)
    fig.patch.set_facecolor("#0f172a")

    # Panel 1: Sentinel-1 SAR VV Channel
    im0 = axes[0].imshow(vv_img, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title(
        f"Sentinel-1 SAR VV Amplitude\nAcquisition: {acquisition_date}",
        color="#f8fafc",
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    axes[0].axis("off")
    cbar0 = plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    cbar0.ax.yaxis.set_tick_params(color="#94a3b8")
    plt.setp(plt.getp(cbar0.ax.axes, "yticklabels"), color="#94a3b8")

    # Panel 2: U-Net Flood Extent Mask Overlay
    base_rgb = np.stack([vv_img.astype(np.float32) / 255.0] * 3, axis=-1)
    tint = np.array([0.0, 0.78, 1.0])  # Cyan flood overlay
    alpha = 0.55
    composite = np.where(mask[:, :, None] == 1, base_rgb * (1 - alpha) + tint * alpha, base_rgb)

    axes[1].imshow(composite)
    axes[1].set_title(
        f"U-Net Flood Inundation Prediction\nThreshold: {DEFAULT_THRESHOLD:.2f} (Coverage: {coverage_pct:.1f}%)",
        color="#f8fafc",
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    axes[1].axis("off")

    legend_elements = [
        Patch(facecolor="#00e5ff", edgecolor="white", label="Flooded Water (p >= 0.40)"),
        Patch(facecolor="#64748b", edgecolor="white", label="Non-Water / Land"),
    ]
    axes[1].legend(
        handles=legend_elements,
        loc="lower right",
        facecolor="#1e293b",
        edgecolor="#334155",
        labelcolor="#f8fafc",
        fontsize=8,
    )

    plt.suptitle(
        "AquaWatch — SAR Flood Extent Segmentation (ResNet-34 U-Net)",
        color="#38bdf8",
        fontsize=12,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout()
    plt.savefig(output_png_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

    return output_png_path


def predict_file(
    input_path,
    model_path="models/unet_resnet34_best.pt",
    output_path="flood_mask.tif",
    input_type="uint8",
    threshold=DEFAULT_THRESHOLD,
    window=DEFAULT_WINDOW,
    stride=DEFAULT_STRIDE,
    batch_size=DEFAULT_BATCH_SIZE,
    output_png_path=None,
    acquisition_date="2026-07-28",
):
    """Complete inference pipeline with horizontal-flip TTA."""
    model, device = load_model(model_path)
    img_u8, profile = load_input(input_path, input_type)

    probability = predict_scene_tta(
        model,
        img_u8,
        device,
        window=window,
        stride=stride,
        batch_size=batch_size,
    )

    mask = (probability >= threshold).astype(np.uint8)
    save_mask(mask, output_path, profile)
    area_km2 = calculate_area_km2(mask, profile)
    coverage_pct = round(float(mask.mean() * 100), 2)

    png_result = None
    if output_png_path:
        vv = img_u8[0]
        png_result = str(generate_prediction_panel(
            vv, mask, acquisition_date, coverage_pct, Path(output_png_path)
        ))

    return {
        "model": "U-Net ResNet34",
        "threshold": float(threshold),
        "predicted_pixels": int(mask.sum()),
        "predicted_area_km2": round(float(area_km2), 4),
        "coverage_pct": coverage_pct,
        "input_shape": list(img_u8.shape),
        "output_mask": str(output_path),
        "prediction_image": png_result,
        "device": str(device),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Flood extent inference using ResNet34 U-Net with TTA."
    )
    parser.add_argument("--input", required=True, help="2-band VV/VH GeoTIFF or .npy file.")
    parser.add_argument("--model", default="models/unet_resnet34_best.pt", help="Path to U-Net checkpoint.")
    parser.add_argument("--output", default="flood_mask.tif", help="Output binary mask path.")
    parser.add_argument("--output-png", default=None, help="Optional output PNG panel path.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    parser.add_argument("--stride", type=int, default=DEFAULT_STRIDE)

    args = parser.parse_args()
    result = predict_file(
        input_path=args.input,
        model_path=args.model,
        output_path=args.output,
        output_png_path=args.output_png,
        threshold=args.threshold,
        window=args.window,
        stride=args.stride,
    )
    print("\nFlood Extent Prediction:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
