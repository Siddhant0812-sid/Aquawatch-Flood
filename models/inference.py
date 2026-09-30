"""
inference.py
Flood extent inference using the trained ResNet34 U-Net.

Main frontend/backend function:
    predict_file(input_path, model_path, output_path)

Expected SAR input:
    2-band GeoTIFF: Band 1 = VV, Band 2 = VH
    OR NumPy array with shape (2, H, W)

Input types:
    uint8  = already converted using the project's preprocessing
    db     = dB SAR values
    linear = linear SAR values

Example:
    python inference.py --input assam_sar.tif --output flood_mask.tif
"""

import argparse
from pathlib import Path

import numpy as np
import torch
import segmentation_models_pytorch as smp
import rasterio
from scipy.ndimage import uniform_filter


DEFAULT_THRESHOLD = 0.50
DEFAULT_WINDOW = 256
DEFAULT_STRIDE = 64
DEFAULT_BATCH_SIZE = 16


def load_model(model_path, device=None):
    """Load the trained ResNet34 U-Net."""
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = smp.Unet(
        encoder_name="resnet34",
        encoder_weights=None,
        in_channels=2,
        classes=1
    ).to(device)

    checkpoint = torch.load(model_path, map_location=device)

    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]

    model.load_state_dict(checkpoint)
    model.eval()
    return model, device


def lee_filter(img, size=5):
    """Same Lee filter used in the project."""
    img = img.astype(np.float32)
    mean = uniform_filter(img, size)
    sq_mean = uniform_filter(img ** 2, size)
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

    input_type:
        uint8  : already processed
        db     : dB values
        linear : linear SAR values
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
            axis=0
        )

    if input_type == "linear":
        return np.stack(
            [linear_to_uint8_db(arr[i]) for i in range(2)],
            axis=0
        )

    raise ValueError("input_type must be 'uint8', 'db', or 'linear'")


@torch.no_grad()
def predict_scene(
    model,
    img_u8,
    device,
    window=DEFAULT_WINDOW,
    stride=DEFAULT_STRIDE,
    batch_size=DEFAULT_BATCH_SIZE
):
    """Run overlapping sliding-window segmentation."""
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

    use_amp = device.startswith("cuda")

    for start in range(0, len(coords), batch_size):
        batch_coords = coords[start:start + batch_size]

        batch = np.stack([
            x[:, r:r + window, c:c + window]
            for r, c in batch_coords
        ])

        xb = torch.from_numpy(batch).float().to(device)

        # Same normalization used during training.
        xb = (xb / 255.0 - 0.5) / 0.5

        if use_amp:
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(xb)
        else:
            logits = model(xb)

        predictions = torch.sigmoid(logits)
        predictions = predictions.float().squeeze(1).cpu().numpy()

        for (r, c), prediction in zip(batch_coords, predictions):
            prob[r:r + window, c:c + window] += prediction
            count[r:r + window, c:c + window] += 1

    return (prob / np.maximum(count, 1))[:height, :width]


def load_input(input_path, input_type="uint8"):
    """Load a 2-band GeoTIFF or (2,H,W) NumPy file."""
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if input_path.suffix.lower() == ".npy":
        arr = np.load(input_path)
        return prepare_sar(arr, input_type), None

    if input_path.suffix.lower() in [".tif", ".tiff"]:
        with rasterio.open(input_path) as src:
            if src.count < 2:
                raise ValueError(
                    "GeoTIFF must contain at least 2 bands: VV and VH."
                )
            arr = src.read([1, 2])
            profile = src.profile.copy()

        return prepare_sar(arr, input_type), profile

    raise ValueError("Supported input formats: .tif, .tiff, .npy")


def save_mask(mask, output_path, profile=None):
    """Save a binary mask, preserving GeoTIFF georeferencing when available."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if profile is not None:
        out_profile = profile.copy()
        out_profile.update(count=1, dtype="uint8", nodata=0)

        with rasterio.open(output_path, "w", **out_profile) as dst:
            dst.write(mask.astype(np.uint8), 1)
    else:
        np.save(output_path, mask.astype(np.uint8))


def calculate_area_km2(mask, profile=None):
    """Calculate positive-pixel area in km²."""
    positive_pixels = int(np.count_nonzero(mask))

    if profile is not None and profile.get("transform") is not None:
        transform = profile["transform"]
        pixel_area_m2 = abs(transform.a * transform.e)
    else:
        # Sentinel-1 processing in this project uses 10 m pixels.
        pixel_area_m2 = 10.0 * 10.0

    return (positive_pixels * pixel_area_m2) / 1_000_000.0


def predict_file(
    input_path,
    model_path="unet_resnet34_best.pt",
    output_path="flood_mask.tif",
    input_type="uint8",
    threshold=DEFAULT_THRESHOLD,
    window=DEFAULT_WINDOW,
    stride=DEFAULT_STRIDE,
    batch_size=DEFAULT_BATCH_SIZE
):
    """
    Complete inference pipeline.

    Returns a dictionary that can be returned by a Flask/FastAPI backend.
    """
    model, device = load_model(model_path)

    img_u8, profile = load_input(input_path, input_type)

    probability = predict_scene(
        model,
        img_u8,
        device,
        window=window,
        stride=stride,
        batch_size=batch_size
    )

    mask = (probability >= threshold).astype(np.uint8)

    save_mask(mask, output_path, profile)

    area_km2 = calculate_area_km2(mask, profile)

    return {
        "model": "U-Net ResNet34",
        "threshold": float(threshold),
        "predicted_pixels": int(mask.sum()),
        "predicted_area_km2": round(float(area_km2), 4),
        "input_shape": list(img_u8.shape),
        "output_mask": str(output_path),
        "device": device
    }


def main():
    parser = argparse.ArgumentParser(
        description="Flood extent inference using ResNet34 U-Net."
    )

    parser.add_argument(
        "--input", required=True,
        help="2-band VV/VH GeoTIFF or (2,H,W) NumPy .npy file."
    )
    parser.add_argument(
        "--model", default="unet_resnet34_best.pt",
        help="Path to trained U-Net .pt file."
    )
    parser.add_argument(
        "--output", default="flood_mask.tif",
        help="Output binary mask path."
    )
    parser.add_argument(
        "--input-type",
        choices=["uint8", "db", "linear"],
        default="uint8",
        help="Input representation: uint8, db, or linear."
    )
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help="Segmentation threshold. Default: 0.5."
    )
    parser.add_argument(
        "--window", type=int, default=DEFAULT_WINDOW,
        help="Sliding-window size. Default: 256."
    )
    parser.add_argument(
        "--stride", type=int, default=DEFAULT_STRIDE,
        help="Sliding-window stride. Default: 64."
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help="Inference batch size. Default: 16."
    )

    args = parser.parse_args()

    result = predict_file(
        input_path=args.input,
        model_path=args.model,
        output_path=args.output,
        input_type=args.input_type,
        threshold=args.threshold,
        window=args.window,
        stride=args.stride,
        batch_size=args.batch_size
    )

    print("\nFlood Extent Prediction")
    print("-----------------------")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
