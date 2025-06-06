// controllers/map_controller.js

import { Controller } from "@hotwired/stimulus";
import maplibregl, {
    LngLatBounds,
    NavigationControl,
    ScaleControl,
} from "maplibre-gl";

export default class extends Controller {
    static targets = [
        "count",
        "listItem",
        "loading",
        "map",
        "marker",
        "placeList",
        "placeMarkers",
    ];

    async getPlaces(url, sort, query) {
        // get all pages of chunked place HTML snippets
        let page = 1;
        let hasNextPage = true;
        let places = [];
        const sortBy = sort ? `&sort=${sort}` : "";
        const queryBy = query ? `&q=${query}` : "";
        this.loadingTarget.classList.add("loading");
        while (hasNextPage) {
            const data = await fetch(`${url}?page=${page}${sortBy}${queryBy}`, {
                headers: {
                    Accept: "application/json",
                },
            });
            const {
                markers_snippet,
                results_snippet,
                has_next,
                next_page_number,
                count,
            } = await data.json();
            this.countTarget.innerText = count;
            this.placeMarkersTarget.insertAdjacentHTML(
                "beforeend",
                markers_snippet
            );
            this.placeListTarget.insertAdjacentHTML(
                "beforeend",
                results_snippet
            );
            page = next_page_number;
            hasNextPage = has_next;
        }
        this.loadingTarget.classList.remove("loading");

        return places;
    }

    initialize() {
        // set up coordinates list for map auto-zoom after all loaded
        this.coordinates = [];
        this.count = 0;
    }

    async connect() {
        // load search variables from django settings; must use DOM query due to json_script
        const searchOpts = JSON.parse(
            document.getElementById("search-opts").textContent
        );
        await this.getPlaces(
            searchOpts.snippets_url,
            searchOpts.order_by,
            searchOpts.query
        );
    }

    listItemTargetConnected() {}

    markerTargetConnected(marker) {
        // add each marker to the map
        const loc = [
            parseFloat(marker.dataset.lon),
            parseFloat(marker.dataset.lat),
        ];
        if (loc) {
            marker.addEventListener("click", this.onClickMarker);
            new maplibregl.Marker({
                anchor: "bottom",
                element: marker,
            })
                .setLngLat(loc)
                .addTo(this.map);
        }

        // add to list of coordinate sets
        this.coordinates.push(loc);

        if (this.markerTargets.length > 1 && marker.dataset.final === "true") {
            // more than one marker, and all markers have been rendered and
            // added to map: fit map to marker boundaries
            // code from https://stackoverflow.com/a/63058036/394067
            const bounds = this.coordinates.reduce(function (bounds, coord) {
                return bounds.extend(coord);
            }, new LngLatBounds(this.coordinates[0], this.coordinates[0]));
            this.map.fitBounds(bounds, {
                padding: { top: 125, bottom: 50, left: 50, right: 50 },
            });
        }
    }

    mapTargetConnected() {
        // add map if we have an access token
        const accessToken = this.mapTarget.dataset.maptilerToken;
        const singleMarker = this.markerTargets.length === 1;

        // set center to fustat by default
        let zoomParams = {
            zoom: 0.5,
            center: [30, 31],
        };

        // single marker, center the marker
        if (singleMarker) {
            const lonlat = [
                this.markerTarget.dataset.lon,
                this.markerTarget.dataset.lat,
            ];
            zoomParams = {
                center: lonlat,
                zoom: 9,
            };
        }
        if (accessToken) {
            // add the rtl text plugin to fix arabic text issues
            if (maplibregl.getRTLTextPluginStatus() === "unavailable") {
                maplibregl.setRTLTextPlugin(
                    "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.2.3/mapbox-gl-rtl-text.min.js",
                    true // Lazy load the plugin
                );
            }
            this.map = new maplibregl.Map({
                container: "map",
                style: `https://api.maptiler.com/maps/5f93d3e5-e339-45bf-86fb-bf7f98a22936/style.json?key=${accessToken}`,
                ...zoomParams,
            });

            // add navigation control
            const control = new NavigationControl({ showCompass: false });
            this.map.addControl(control);

            // add scale controls
            const scaleImperial = new ScaleControl({ unit: "imperial" });
            this.map.addControl(scaleImperial);
            const scaleMetric = new ScaleControl({ unit: "metric" });
            this.map.addControl(scaleMetric);
        }
    }

    onClickMarker(e) {
        const selected = document.querySelectorAll(".selected-place");
        selected.forEach((element) => {
            element.classList.remove("selected-place");
        });
        e.currentTarget.classList.add("selected-place");
        const slug = e.currentTarget.dataset.slug;
        const element = document.querySelector(`[data-slug-anchor="${slug}"]`);
        const isMobile = window.innerWidth <= 900;
        if (!isMobile) {
            element.scrollIntoView({ behavior: "smooth" });
        }
        element.classList.add("selected-place");
    }
}
