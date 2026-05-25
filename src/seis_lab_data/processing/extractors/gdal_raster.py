import logging
from pathlib import Path

from osgeo import gdal, osr

from .schemas import RasterMetadata

logger = logging.getLogger(__name__)

gdal.UseExceptions()


def extract_raster_metadata(path: Path | str) -> RasterMetadata:
    ds = gdal.Open(str(path), gdal.GA_ReadOnly)
    try:
        driver = ds.GetDriver().ShortName
        width = ds.RasterXSize
        height = ds.RasterYSize
        band_count = ds.RasterCount

        gt = ds.GetGeoTransform(can_return_null=True)
        if gt is None:
            pixel_size_x = pixel_size_y = None
            bbox_native = None
        else:
            pixel_size_x = gt[1]
            pixel_size_y = gt[5]
            x0 = gt[0]
            y0 = gt[3]
            x1 = x0 + width * gt[1] + height * gt[2]
            y1 = y0 + width * gt[4] + height * gt[5]
            minx, maxx = sorted((x0, x1))
            miny, maxy = sorted((y0, y1))
            bbox_native = (minx, miny, maxx, maxy)

        epsg, crs_wkt, src_srs = _read_srs(ds)
        nodata = ds.GetRasterBand(1).GetNoDataValue() if band_count else None
        bbox_4326 = _project_to_wgs84(bbox_native, src_srs)

        return RasterMetadata(
            driver=driver,
            width=width,
            height=height,
            band_count=band_count,
            epsg=epsg,
            crs_wkt=crs_wkt,
            pixel_size_x=pixel_size_x,
            pixel_size_y=pixel_size_y,
            nodata=nodata,
            bbox_native=bbox_native,
            bbox_4326=bbox_4326,
        )
    finally:
        ds = None  # noqa: F841


def _read_srs(ds) -> tuple[int | None, str | None, "osr.SpatialReference | None"]:
    wkt = ds.GetProjection()
    if not wkt:
        return None, None, None
    srs = osr.SpatialReference(wkt)
    try:
        srs.AutoIdentifyEPSG()
    except RuntimeError as err:
        logger.debug("AutoIdentifyEPSG failed for raster: %s", err)
    code = srs.GetAuthorityCode(None)
    epsg = int(code) if code else None
    return epsg, wkt, srs


def _project_to_wgs84(
    bbox_native: tuple[float, float, float, float] | None,
    src_srs: "osr.SpatialReference | None",
) -> tuple[float, float, float, float] | None:
    if bbox_native is None or src_srs is None:
        return None
    wgs84 = osr.SpatialReference()
    wgs84.ImportFromEPSG(4326)
    wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    src = src_srs.Clone()
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(src, wgs84)
    minx, miny, maxx, maxy = bbox_native
    corners = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
    projected = [transform.TransformPoint(x, y) for x, y in corners]
    lons = [p[0] for p in projected]
    lats = [p[1] for p in projected]
    return (min(lons), min(lats), max(lons), max(lats))


# todo reverificar se está bem aqui ou não. Como isto passou do discovery_demo/protocols.py ver se não quebrei qualquer coisa.


# async def extractor_gdal_raster(
#     *,
#     survey_mission: models.SurveyMission,
#     record_configuration: discovery_schemas.SurveyRecordDiscoveryConfiguration,
#     discovered_assets: list[DiscoveredAsset],
#     session: AsyncSession,
# ) -> record_schemas.SurveyRelatedRecordCreate:
#     if not discovered_assets:
#         raise ValueError("extractor1 requires at least one discovered asset")

#     bboxes: list[tuple[float, float, float, float]] = []
#     for _, abs_path in discovered_assets:
#         metadata = dispatch_extractor(abs_path)
#         if metadata is not None and metadata.bbox_4326 is not None:
#             bboxes.append(metadata.bbox_4326)

#     bbox_wkt = _aggregate_bbox_wkt(bboxes)

#     dataset_category = await record_queries.get_dataset_category_by_english_name(
#         session, record_configuration.dataset_category
#     )
#     domain_type = await record_queries.get_domain_type_by_english_name(
#         session, record_configuration.domain_type
#     )
#     workflow_stage = await record_queries.get_workflow_stage_by_english_name(
#         session, record_configuration.workflow_stage
#     )
#     if dataset_category is None:
#         raise ValueError(
#             f"Unknown dataset_category {record_configuration.dataset_category!r}"
#         )
#     if domain_type is None:
#         raise ValueError(f"Unknown domain_type {record_configuration.domain_type!r}")
#     if workflow_stage is None:
#         raise ValueError(
#             f"Unknown workflow_stage {record_configuration.workflow_stage!r}"
#         )

#     relative_path = "/".join(
#         (
#             record_configuration.domain_type,
#             record_configuration.dataset_category,
#             record_configuration.workflow_stage,
#         )
#     )

#     return SurveyRelatedRecordCreate(
#         id=SurveyRelatedRecordId(uuid.uuid4()),
#         owner_id=UserId(survey_mission.owner_id),
#         survey_mission_id=SurveyMissionId(survey_mission.id),
#         name=LocalizableDraftName(**record_configuration.name),
#         description=LocalizableDraftDescription(
#             **(record_configuration.description or {})
#         ),
#         dataset_category_id=DatasetCategoryId(dataset_category.id),
#         domain_type_id=DomainTypeId(domain_type.id),
#         workflow_stage_id=WorkflowStageId(workflow_stage.id),
#         relative_path=relative_path,
#         bbox_4326=bbox_wkt,
#         temporal_extent_begin=None,
#         temporal_extent_end=None,
#         links=list(record_configuration.links),
#         assets=[asset for asset, _ in discovered_assets],
#         related_records=[],
#     )


# def _aggregate_bbox_wkt(
#     bboxes: list[tuple[float, float, float, float]],
# ) -> str | None:
#     if not bboxes:
#         return None
#     polys = [shapely.box(minx, miny, maxx, maxy) for minx, miny, maxx, maxy in bboxes]
#     union = shapely.unary_union(polys)
#     minx, miny, maxx, maxy = union.bounds
#     return shapely.box(minx, miny, maxx, maxy).wkt
