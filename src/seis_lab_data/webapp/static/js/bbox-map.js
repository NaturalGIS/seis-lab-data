export class BoundingBoxMap extends HTMLElement {

    constructor() {
        super()
        this._suppressUpdate = false;
    }

    static get observedAttributes() {
        return [
            'data-min-lat',
            'data-min-lon',
            'data-max-lat',
            'data-max-lon',
        ];
    }

    connectedCallback() {
        this.initMap()
    }

    attributeChangedCallback(name, oldValue, newValue) {
        console.log(`Attribute changes: ${name} from ${oldValue} to ${newValue}`)
        if (oldValue === newValue || !this.draw) return;

        if (['data-min-lat', 'data-min-lon', 'data-max-lat', 'data-max-lon'].includes(name)) {
            console.log('dispatching updateMapFromAttributes...')
            this.updateMapFromAttributes();
        }
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
                        'id': 'emodnet-bathymetry',
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
                new terraDraw.TerraDrawRectangleMode(),
                new terraDraw.TerraDrawSelectMode({
                    flags: {
                        rectangle: {
                            feature: {
                                draggable: true,
                                coordinates: {
                                    midpoints: false,
                                    draggable: false,
                                    deletable: false,
                                }
                            }
                        }
                    }
                }),
            ]
        })
        this.draw.on("finish", (id, context) => {
            if (context.action === "draw") {
                const feature = this.draw.getSnapshot().find(f => f.id === id)
                console.log(`Drawing has finished for feature with id ${id}`)
                console.log(`geom is: ${feature.geometry.coordinates}`)
                this.dispatchBboxEvent(feature)
            }
        })
        this.draw.on("change", (ids, type, context) => {
            if (type === "create") {
                // delete any other features that may be in the store
                console.log('Clearing previous features...')
                const toClear = this.draw.getSnapshot().map(f => f.id).slice(0, -1)
                this.draw.removeFeatures(toClear)
            }
        })

        this.draw.start()
        this.draw.setMode("rectangle")

        this.updateMapFromAttributes()

    }

    updateMapFromAttributes() {
        if (this._suppressUpdate || !this.draw) return

        const minLat = parseFloat(this.getAttribute('data-min-lat'))
        const minLon = parseFloat(this.getAttribute('data-min-lon'))
        const maxLat = parseFloat(this.getAttribute('data-max-lat'))
        const maxLon = parseFloat(this.getAttribute('data-max-lon'))

        console.log(`minLat: ${minLat}, minLon: ${minLon}, maxLat: ${maxLat}, maxLon: ${maxLon}`)

        if (!isNaN(minLat) && !isNaN(minLon) && !isNaN(maxLat) && !isNaN(maxLon)) {
            this._suppressUpdate = true

            this.draw.clear()

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

            this._suppressUpdate = false
        }

    }

    dispatchBboxEvent(feature) {
        if (this._suppressUpdate) return

        const coords = feature.geometry.coordinates[0]
        const lons = coords.map(c => c[0])
        const lats = coords.map(c => c[1])

        const bbox = {
            minLon: Math.min(...lons),
            minLat: Math.min(...lats),
            maxLon: Math.max(...lons),
            maxLat: Math.max(...lats),
        }

        this.dispatchEvent(
            new CustomEvent('bbox-changed', {
                detail: {
                    'bbox': bbox,
                    'feature': feature
                },
                bubbles: true,
                composed: true,
            })
        )
    }
}

// auto-register as a Web Component when imported
customElements.define('bbox-map', BoundingBoxMap)
