// Map of a survey-related record: preview image, if generated, under the outline of its bbox
//
// Not the same component as bbox-map-readonly: that one draws its rectangle
export class RecordMap extends HTMLElement {

    connectedCallback() {
        this.initMap()
    }

    initMap() {
        const tileUrl = this.getAttribute("data-tile-url")
        const centerX = this.getAttribute("data-center-lon") || 0
        const centerY = this.getAttribute("data-center-lat") || 0
        const zoom = this.getAttribute("data-zoom") || 2
        const minZoom = this.getAttribute("data-min-zoom") || 0
        // the base layer only has tiles up to this zoom level. Beyond it
        // maplibre overscales the last tiles instead of going blank. Parsed to
        // a number because maplibre refuses to load a style whose maxzoom is a
        // string, which is how attributes always arrive
        const maxZoom = parseInt(this.getAttribute("data-max-zoom"), 10) || 14

        const previewUrl = this.getAttribute("data-preview-url")
        const previewBounds = JSON.parse(this.getAttribute("data-preview-bounds") || "null")
        const boundingBox = this.getBoundingBox()

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

        this.map.on('error', (evt) => {
            // errors from the base tiles are not handled here
            if (evt.sourceId === 'preview') {
                this.showPreviewUnavailable()
            }
        })

        this.map.on('load', () => {
            // the image needs its four corners, it can only be shown when bounds are known
            const hasPreview = Boolean(previewUrl && previewBounds)
            if (hasPreview) {
                this.addPreview(previewUrl, previewBounds)
            }
            if (boundingBox !== null) {
                this.addBoundingBox(boundingBox, hasPreview)
            }
            // the preview is the more precise extent of the two
            const bounds = previewBounds || boundingBox
            if (bounds !== null) {
                this.map.fitBounds(bounds, {padding: 20})
            }
        })
    }

    // The record's bbox [minLon, minLat, maxLon, maxLat], or null
    // when it is absent or has no area to draw a degenerate or inverted box
    getBoundingBox() {
        const minLon = parseFloat(this.getAttribute("data-min-lon"))
        const minLat = parseFloat(this.getAttribute("data-min-lat"))
        const maxLon = parseFloat(this.getAttribute("data-max-lon"))
        const maxLat = parseFloat(this.getAttribute("data-max-lat"))

        if ([minLon, minLat, maxLon, maxLat].some(Number.isNaN)) return null
        if (minLon >= maxLon || minLat >= maxLat) return null
        return [minLon, minLat, maxLon, maxLat]
    }

    addPreview(url, [minLon, minLat, maxLon, maxLat]) {
        this.map.addSource('preview', {
            type: 'image',
            url: url,
            // maplibre wants the image corners, clockwise from the top left one
            coordinates: [
                [minLon, maxLat],
                [maxLon, maxLat],
                [maxLon, minLat],
                [minLon, minLat],
            ]
        })
        this.map.addLayer({
            'id': 'preview',
            'type': 'raster',
            'source': 'preview',
        })
    }

    addBoundingBox([minLon, minLat, maxLon, maxLat], previewShown) {
        const fillColor = this.getAttribute("data-polygon-fill-color") || '#000000'
        const fillOpacity = parseFloat(this.getAttribute("data-polygon-fill-opacity") || 1)
        const outlineColor = this.getAttribute("data-polygon-outline-color") || '#000000'
        const outlineWidth = parseInt(this.getAttribute("data-polygon-outline-width") || 1)

        this.map.addSource('bbox', {
            type: 'geojson',
            data: {
                type: 'Feature',
                properties: {},
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
        })
        if (!previewShown) {
            // the semi-transparent fill would darken the preview image below,
            // so it is only drawn when the box is empty
            this.map.addLayer({
                'id': 'bbox-fill',
                'type': 'fill',
                'source': 'bbox',
                'paint': {
                    'fill-color': fillColor,
                    'fill-opacity': fillOpacity,
                }
            })
        }
        this.map.addLayer({
            'id': 'bbox-outline',
            'type': 'line',
            'source': 'bbox',
            'paint': {
                'line-color': outlineColor,
                'line-width': outlineWidth,
            }
        })
    }

    // says explicitly instead of leaving an empty layer that looks as a
    // record with no preview
    showPreviewUnavailable() {
        if (this.querySelector('.preview-unavailable') !== null) return
        const badge = document.createElement('div')
        badge.className = 'preview-unavailable badge text-bg-warning position-absolute top-0 start-0 m-2'
        badge.textContent = this.getAttribute("data-preview-unavailable-text")
        this.appendChild(badge)
    }
}

// auto-register as a Web Component when imported
customElements.define('record-map', RecordMap)
