export class MapWithPolygonLayer extends HTMLElement {

    constructor() {
        super()
        this._suppressUpdate = true;
    }

    connectedCallback() {
        this.initMap()
    }

    initMap() {
        const baseMapTileUrl = this.getAttribute("data-base-map-tile-url")
        const polygonLayerTileUrl = this.getAttribute("data-polygon-layer-tile-url")
        const polygonLayerName = this.getAttribute("data-polygon-layer-name")
        const centerX = this.getAttribute("data-center-lon") || 0
        const centerY = this.getAttribute("data-center-lat") || 0
        const zoom = this.getAttribute("data-zoom") || 2
        const minZoom = this.getAttribute("data-min-zoom") || 0
        const maxZoom = this.getAttribute("data-max-zoom") || 14
        const polygonFillColor = this.getAttribute("data-polygon-fill-color") || '#000000'
        const polygonFillOpacity = parseFloat(this.getAttribute("data-polygon-fill-opacity") || 1)
        const polygonOutlineColor = this.getAttribute("data-polygon-outline-color") || '#000000'
        const polygonOutlineOpacity = parseFloat(this.getAttribute("data-polygon-outline-opacity") || 1)
        const polygonOutlineWidth = parseInt(this.getAttribute("data-polygon-outline-width") || 1)

        this.map = new maplibregl.Map({
            container: this,
            style: {
                'version': 8,
                'sources': {
                    'raster-tiles': {
                        'type': 'raster',
                        'tiles': [baseMapTileUrl],
                        'tileSize': 256,
                        'minzoom': minZoom,
                        'maxzoom': maxZoom
                    },
                },
                'layers': [
                    {
                        'id': 'basemap',
                        'type': 'raster',
                        'source': 'raster-tiles',
                    }
                ],
                'id': 'blank'
            },
            center: [centerX, centerY],
            zoom: zoom,
        })

        this.map.on('load', () => {
            this.map.addSource(
                'polygons', {
                    type: 'vector',
                    url: polygonLayerTileUrl
                }
            )
            this.map.addLayer({
                'id': 'polygons',
                'type': 'fill',
                'source': 'polygons',
                'source-layer': polygonLayerName,
                'paint': {
                    'fill-color': polygonFillColor,
                    'fill-opacity': polygonFillOpacity,
                }
            })
            this.map.addLayer({
                'id': 'polygon-outlines',
                'type': 'line',
                'source': 'polygons',
                'source-layer': polygonLayerName,
                'paint': {
                    'line-color': polygonOutlineColor,
                    'line-opacity': polygonOutlineOpacity,
                    'line-width': polygonOutlineWidth,
                }
            })
        })

        this.map.on('moveend', (evt) => {
            console.log(evt)
            this.dispatchEvent(new CustomEvent('map-moveend', {
                detail: {
                    map: evt.target
                },
                bubbles: true,
                composed: true
            }))
        })

        this.map.on('mouseenter', 'polygons', () => {
            this.map.getCanvas().style.cursor = 'pointer'
        })

        this.map.on('mouseleave', 'polygons', () => {
            this.map.getCanvas().style.cursor = ''
        })

        this.map.on('click', 'polygons', (evt) => {
            console.log(evt)
            new maplibregl.Popup()
                .setLngLat(evt.lngLat)
                .setHTML(`<a href="/projects/${evt.features[0].properties.id}">${evt.features[0].properties.en}</a>`)
                .addTo(this.map)
        })
    }
}

// auto-register as a Web Component when imported
customElements.define('map-with-polygon-layer', MapWithPolygonLayer)
