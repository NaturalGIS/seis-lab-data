"""Use playwright to save maplibre maps

This script uses playwright to render an HTML page that has a maplibre map
and then saves a screenshot of the page as a PNG file. This is useful for
using as the image for a project, survey mission or record
"""

import dataclasses
import logging
from pathlib import Path

import shapely
from playwright.sync_api import sync_playwright
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class BaseLayerConfig:
    tile_url: str
    tile_size: int = 256
    min_zoom: int = 0
    max_zoom: int = 12


@dataclasses.dataclass
class GeospatialBounds:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@dataclasses.dataclass
class PolygonDrawLayer:
    features: list[shapely.Polygon]
    fill_color: str


@dataclasses.dataclass
class MapConfig:
    base_layer: BaseLayerConfig
    bounds: GeospatialBounds
    pad_bounds_pixels: int = 20
    maplibre_script_src: str = (
        "https://unpkg.com/maplibre-gl@^5.10.0/dist/maplibre-gl.js"
    )
    maplibre_css_link_href: str = (
        "https://unpkg.com/maplibre-gl@^5.10.0/dist/maplibre-gl.css"
    )
    terra_draw_script_src: str = (
        "https://unpkg.com/terra-draw@1.18.1/dist/terra-draw.umd.js"
    )
    terra_draw_maplibre_adapter_script_src: str = (
        "https://unpkg.com/terra-draw-maplibre-gl-adapter@1.2.2/"
        "dist/terra-draw-maplibre-gl-adapter.umd.js"
    )


def _quantize_features(draw_layers: list[PolygonDrawLayer]) -> None:
    for layer in draw_layers:
        quantized_features = []
        for feat in layer.features:
            quantized_features.append(shapely.set_precision(feat, grid_size=10**-5))
        layer.features = quantized_features


def render_map_to_image(
    map_options: MapConfig,
    template_path: Path,
    width: int = 800,
    height: int = 600,
    timeout_seconds: int = 30,
    polygon_draw_layers: list[PolygonDrawLayer] | None = None,
) -> bytes:
    if polygon_draw_layers is not None:
        _quantize_features(polygon_draw_layers)

    jinja_env = Environment(loader=FileSystemLoader(template_path.parent))
    template = jinja_env.get_template(template_path.name)
    rendered_html = template.render(
        map_conf=map_options, polygon_draw_layers=polygon_draw_layers
    )
    # print(rendered_html)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={
                "width": width,
                "height": height,
            }
        )
        page = context.new_page()
        page.set_content(rendered_html, wait_until="domcontentloaded")
        page.on(
            "console",
            lambda msg: logger.info(f"Browser console: {msg.type}: {msg.text}"),
        )
        page.on("pageerror", lambda exc: logger.error(f"Browser error: {exc}"))
        page.wait_for_function(
            "window.mapReady === true", timeout=timeout_seconds * 1000
        )
        image_ = page.screenshot(type="png")
        context.close()
        browser.close()
    return image_


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    image_ = render_map_to_image(
        map_options=MapConfig(
            base_layer=BaseLayerConfig(
                tile_url="http://localhost:8888/tiles/emodnet-bathymetry/{z}/{x}/{y}"
            ),
            bounds=GeospatialBounds(
                min_lon=-21.66699,
                min_lat=33.46451,
                max_lon=9.39853,
                max_lat=46.07667,
            ),
        ),
        template_path=Path(__file__).parent / "map-template.j2.html",
        polygon_draw_layers=[
            PolygonDrawLayer(
                features=[
                    shapely.from_wkt(
                        "Polygon (("
                        "-10.20441798456907989 38.70119610558277401, "
                        "-11.2205635792250753 37.79169190233002951, "
                        "-10.20441798456907989 36.44529103260797598, "
                        "-8.50087978176344627 36.44529103260797598, "
                        "-7.48473418710745175 37.77397648137093, "
                        "-7.19333949452227639 39.21248186032001115, "
                        "-8.15718347768862273 39.77751803104943917, "
                        "-9.23310234261849949 40.00682370756641149, "
                        "-9.23310234261849949 40.00682370756641149, "
                        "-10.20441798456907989 38.70119610558277401"
                        "))"
                    ),
                    shapely.from_wkt(
                        "Polygon (("
                        "-9.1901403046091179 42.38732340111175034, "
                        "-10.63217044996652128 42.33763634579012347, "
                        "-11.39427964595851783 41.93872599766462628, "
                        "-12.08914391289239632 41.26268112034399138, "
                        "-11.11782827094181414 40.92482812098014477, "
                        "-9.5413082674681764 40.58523904194483123, "
                        "-8.43550276740135985 40.94740569811249742, "
                        "-7.9199583112891272 41.57085219933940579, "
                        "-7.9199583112891272 41.57085219933940579, "
                        "-9.1901403046091179 42.38732340111175034"
                        "))"
                    ),
                ],
                fill_color="#ff0000",
            ),
            PolygonDrawLayer(
                features=[
                    shapely.from_wkt(
                        "Polygon (("
                        "-11.25978978784228879 39.59064268176609147, "
                        "-10.45285063914488255 38.26546780283469218, "
                        "-8.51021935524371465 38.0068891936002089, "
                        "-6.1192885442884366 38.4295403925900203, "
                        "-7.19520740921831248 39.68270605610847213, "
                        "-11.25978978784228879 39.59064268176609147"
                        "))"
                    )
                ],
                fill_color="#00ff00",
            ),
        ],
    )
    output_to = Path(__file__).parent / "out.png"
    output_to.write_bytes(image_)
    print(f"Done - printed map is in {output_to!r}")
