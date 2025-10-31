import logging

import shapely

logger = logging.getLogger(__name__)


def get_bbox_4326_for_db(original_bbox: shapely.Polygon):
    if original_bbox.is_valid:
        bbox_to_create = original_bbox.wkt
    else:
        logger.debug("Received invalid bbox, so it will be ignored")
        bbox_to_create = None
    return bbox_to_create
