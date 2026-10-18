import logging
import uuid

from osgeo import gdal

logger = logging.getLogger(__name__)

gdal.UseExceptions()

# The preview serves both as a list thumbnail and as a map overlay, so it is
# sized for the screen, not for analysis.
MAX_PREVIEW_PIXELS = 1024
WEBP_QUALITY = 85


def to_webp(dataset) -> bytes:
    vsi_path = f"/vsimem/{uuid.uuid4().hex}.webp"
    # PAM would leak a .aux.xml sidecar into /vsimem per preview
    with gdal.config_option("GDAL_PAM_ENABLED", "NO"):
        webp = gdal.GetDriverByName("WEBP").CreateCopy(
            vsi_path, dataset, options=[f"QUALITY={WEBP_QUALITY}"]
        )
        webp = None  # noqa: F841
    try:
        with gdal.VSIFile(vsi_path, "rb") as file_handler:
            return file_handler.read()
    finally:
        gdal.Unlink(vsi_path)
