export class BoundingBoxMap extends HTMLElement {

    constructor() {
        super()
        this._suppressUpdate = false;
    }

    static get observedAttributes() {
        return [
            'data-min-lat',
            'data-min-lng',
            'data-max-lat',
            'data-max-lng',
            'data-tile-url',
            'data-center-x',
            'data-center-y',
            'data-zoom',
            'data-min-zoom',
            'data-max-zoom',
        ];
    }

    connectedCallback() {
        this.initMap()
    }

    attributeChangedCallback(name, oldValue, newValue) {
        console.log(`Attribute changes: ${name} from ${oldValue} to ${newValue}`)
        if (oldValue === newValue || !this.draw) return;

        if (['data-min-lat', 'data-min-lng', 'data-max-lat', 'data-max-lng'].includes(name)) {
            console.log('dispatching updateMapFromAttributes...')
            this.updateMapFromAttributes();
        }
    }

    initMap() {
        const tileUrl = this.getAttribute("data-tile-url")
        const centerX = this.getAttribute("data-center-x") || 0
        const centerY = this.getAttribute("data-center-y") || 0
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
        console.log(`Inside updateMapFromAttributes with suppressUpate=${this._suppressUpdate} and draw=${this.draw}`)
        if (this._suppressUpdate || !this.draw) return
        console.log('Continuing...')

        const minLat = parseFloat(this.getAttribute('data-min-lat'))
        const minLng = parseFloat(this.getAttribute('data-min-lng'))
        const maxLat = parseFloat(this.getAttribute('data-max-lat'))
        const maxLng = parseFloat(this.getAttribute('data-max-lng'))

        console.log(`minLat: ${minLat}, minLng: ${minLng}, maxLat: ${maxLat}, maxLng: ${maxLng}`)

        if (!isNaN(minLat) && !isNaN(minLng) && !isNaN(maxLat) && !isNaN(maxLng)) {
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
                        [minLng, minLat],
                        [maxLng, minLat],
                        [maxLng, maxLat],
                        [minLng, maxLat],
                        [minLng, minLat],
                    ]]
                }
            }

            this.draw.addFeatures([feature])
            this.map.fitBounds([[minLng, minLat], [maxLng, maxLat]], {padding: 20})

            this._suppressUpdate = false
        }

    }

    dispatchBboxEvent(feature) {
        if (this._suppressUpdate) return

        const coords = feature.geometry.coordinates[0]
        const lngs = coords.map(c => c[0])
        const lats = coords.map(c => c[1])

        const bbox = {
            minLng: Math.min(...lngs),
            minLat: Math.min(...lats),
            maxLng: Math.max(...lngs),
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
