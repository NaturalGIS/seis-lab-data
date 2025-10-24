export class ReadOnlyBoundingBoxMap extends HTMLElement {

    connectedCallback() {
        this.initMap()
    }

    initMap() {
        const tileUrl = this.getAttribute("data-tile-url")
        const centerX = this.getAttribute("data-center-lon") || 0
        const centerY = this.getAttribute("data-center-lat") || 0
        const zoom = this.getAttribute("data-zoom") || 2
        const minZoom = this.getAttribute("data-min-zoom") || 0
        const maxZoom = this.getAttribute("data-max-zoom") || 14

        this.map = new maplibregl.Map({
            container: this,
            style: {
                'version': 8,
                'sources': {
                    'raster-tiles': {
                        'type': 'raster',
                        'tiles': [tileUrl],
                        'tileSize': 256,
                        'minzoom': minZoom,
                        'maxzoom': maxZoom
                    }
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
            this.initTerraDraw()
        })
    }

    initTerraDraw() {
        this.draw = new terraDraw.TerraDraw({
            adapter: new terraDrawMaplibreGlAdapter.TerraDrawMapLibreGLAdapter({
                map: this.map,
                lib: maplibregl
            }),
            modes: [
                new terraDraw.TerraDrawRenderMode({
                    name: 'default_render_mode'
                }),
                new terraDraw.TerraDrawRectangleMode(),
            ]
        })

        this.draw.start()

        const minLat = parseFloat(this.getAttribute('data-min-lat'))
        const minLon = parseFloat(this.getAttribute('data-min-lon'))
        const maxLat = parseFloat(this.getAttribute('data-max-lat'))
        const maxLon = parseFloat(this.getAttribute('data-max-lon'))

        if (!isNaN(minLat) && !isNaN(minLon) && !isNaN(maxLat) && !isNaN(maxLon)) {
            console.log(`minLat: ${minLat}, minLon: ${minLon}, maxLat: ${maxLat}, maxLon: ${maxLon}`)

            if (minLat === maxLat || minLon === maxLon) return
            if (minLat >= maxLat || minLon >= maxLon) return

            const feature = {
                type: 'Feature',
                properties: {
                    mode: 'rectangle'
                },
                geometry: {
                    type: 'Polygon',
                    coordinates: [[
                        [minLon, minLat],
                        [maxLon, minLat],
                        [maxLon, maxLat],
                        [minLon, maxLat],
                        [minLon, minLat],
                    ]]
                }
            }
            this.draw.addFeatures([feature])
            this.map.fitBounds([[minLon, minLat], [maxLon, maxLat]], {padding: 20})
        }
    }
}

// auto-register as a Web Component when imported
customElements.define('bbox-map-readonly', ReadOnlyBoundingBoxMap)
