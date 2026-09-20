"""Small, Pillow-only image observations used by classify_media's scorer."""

from pathlib import Path

from PIL import Image, UnidentifiedImageError


CAMERA_TAGS = {"Make", "Model", "LensModel", "BodySerialNumber"}
CAMERA_PREFIXES = ("img_", "dsc_", "pxl_", "photo_", "scan_")
ASSET_TERMS = ("favicon", "icon", "logo", "sprite", "thumbnail", "thumb", "avatar", "button")


def _sampled_color_count(image):
    """Estimate color diversity without allocating a full-size RGB copy."""
    sample = image.copy()
    sample.thumbnail((128, 128))
    if sample.mode not in ("RGB", "RGBA", "L", "P", "1"):
        sample = sample.convert("RGB")
    colors = sample.getcolors(maxcolors=16_385)
    return 16_385 if colors is None else len(colors)


def inspect_image(file_path):
    """Read safe, format-neutral image evidence; errors are ordinary results."""
    path = Path(file_path)
    try:
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
            exif = image.getexif()
            tag_names = {str(tag) for tag in exif.keys()}
            # Pillow exposes numeric tags from getexif(); get_ifd values are
            # format-dependent, so test the standard camera tags by ID too.
            camera_exif = any(tag in exif for tag in (271, 272, 42036, 42033)) or bool(CAMERA_TAGS & tag_names)
            dpi = image.info.get("dpi")
            dpi_x = dpi[0] if isinstance(dpi, tuple) and dpi else 0
            dpi_y = dpi[1] if isinstance(dpi, tuple) and len(dpi) > 1 else dpi_x
            color_count = _sampled_color_count(image)
    except (OSError, UnidentifiedImageError, ValueError) as error:
        return {"error": str(error)}

    lower_path = str(path).lower()
    lower_name = path.name.lower()
    pixels = width * height
    return {
        "error": None,
        "width": width,
        "height": height,
        "mode": mode,
        "file_size": path.stat().st_size,
        "camera_exif": camera_exif,
        "camera_filename": lower_name.startswith(CAMERA_PREFIXES),
        "asset_name": any(term in lower_path for term in ASSET_TERMS),
        "palette_or_binary": mode in {"1", "P"},
        "low_color_count": color_count <= 16,
        "high_color_count": color_count >= 512,
        "scan_like": pixels >= 1_000_000 and dpi_x >= 200 and dpi_y >= 200,
    }
