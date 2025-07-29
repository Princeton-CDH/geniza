// controllers/map_controller.js

import { Controller } from "@hotwired/stimulus";
import maplibregl, {
    AttributionControl,
    LngLatBounds,
    NavigationControl,
    ScaleControl,
} from "maplibre-gl";

export default class extends Controller {
    static targets = [
        "count",
        "countButton",
        "listItem",
        "loading",
        "map",
        "marker",
        "placeList",
        "placeMarkers",
        "timelineTicks",
    ];

    async getPlaces(url, sort, query, date_range) {
        // get all pages of chunked place HTML snippets
        let page = 1;
        let hasNextPage = true;
        let places = [];
        const sortBy = sort ? `&sort=${sort}` : "";
        const queryBy = query ? `&q=${query}` : "";
        const dateRange = date_range ? `&date_range=${date_range}` : "";
        this.loadingTarget.classList.add("loading");
        while (hasNextPage) {
            const data = await fetch(
                `${url}?page=${page}${sortBy}${queryBy}${dateRange}`,
                {
                    headers: {
                        Accept: "application/json",
                    },
                }
            );
            const {
                markers_snippet,
                results_snippet,
                has_next,
                next_page_number,
                results_count,
                places_count,
            } = await data.json();
            this.countTarget.innerText = results_count;
            this.countButtonTarget.innerText = places_count;
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
        const searchOptsElem = document.getElementById("search-opts");
        if (searchOptsElem) {
            const searchOpts = JSON.parse(searchOptsElem.textContent);
            await this.getPlaces(
                searchOpts.snippets_url,
                searchOpts.order_by,
                searchOpts.query,
                searchOpts.date_range
            );
        }
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
            let bottom = 50;
            const isMobile = window.innerWidth <= 900;
            if (!isMobile && document.getElementById("search-opts")) {
                // on the desktop search page, this should take timeline into account
                bottom = 180;
            }
            this.map.fitBounds(bounds, {
                padding: { top: 125, bottom, left: 50, right: 50 },
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
                attributionControl: false,
                ...zoomParams,
            });
            this.map.addControl(
                new AttributionControl({ compact: true }),
                "bottom-left"
            );

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
    generateTicks(min, max, interval) {
        // produce evenly spaced integers between min and max, inclusive, at the given interval
        const start = Math.ceil(min / interval) * interval;
        const end = Math.floor(max / interval) * interval;
        const count = Math.floor((end - start) / interval) + 1;
        return Array.from({ length: count }, (_, i) => start + i * interval);
    }
    debounce(f, delay) {
        // simple debounce for timeline resize observer
        let timer = 0;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => f.apply(this, args), delay);
        };
    }
    timelineTicksTargetConnected() {
        // set up timeline constants
        let { min, max } = this.timelineTicksTarget.dataset;
        min = parseInt(min);
        max = parseInt(max);
        this.ticksMinSpacing = 45;
        this.thumbPadding = 8;
        this.svgNs = "http://www.w3.org/2000/svg";
        const yearsPerTick = 50;
        this.ticks = this.generateTicks(min, max, yearsPerTick);

        // resize observer for window horizontal size change
        this.timelineResizeObserver = new ResizeObserver(
            this.debounce(() => this.recalculateTicks(), 50)
        );
        this.timelineResizeObserver.observe(this.timelineTicksTarget);

        // calculate and position ticks on timeline
        this.recalculateTicks();
    }
    recalculateTicks() {
        // regenerate ticks and append to svg in window
        // get timeline width minus thumb padding
        const tlStart = this.thumbPadding;
        const width = this.timelineTicksTarget.getBoundingClientRect().width;
        const tlEnd = width - this.thumbPadding;

        // remove all svg contents
        const svg = this.timelineTicksTarget.querySelector("svg");
        svg.replaceChildren();

        // create the timeline baseline
        const timelineBg = document.createElementNS(this.svgNs, "line");
        timelineBg.setAttribute("x1", tlStart);
        timelineBg.setAttribute("y1", 0);
        timelineBg.setAttribute("x2", tlEnd);
        timelineBg.setAttribute("y2", 0);
        timelineBg.setAttribute("stroke", "var(--timeline-bg)");
        svg.appendChild(timelineBg);

        // get xOffsets for ticks based on timeline width
        let { min, max } = this.timelineTicksTarget.dataset;
        min = parseInt(min);
        max = parseInt(max);
        const ticks = this.ticks.map((tick) => ({
            value: tick,
            xOffset: tlStart + ((tick - min) / (max - min)) * (tlEnd - tlStart),
        }));

        // generate visible tick marks, skipping over those less than ticksMinSpacing away
        let prevXOffset = 0;
        ticks.forEach((tick, i) => {
            if (i == 0 || tick.xOffset - prevXOffset > this.ticksMinSpacing) {
                prevXOffset = tick.xOffset;
                // create tick line
                const line = document.createElementNS(this.svgNs, "line");
                line.setAttribute("x1", tick.xOffset);
                line.setAttribute("y1", -8);
                line.setAttribute("x2", tick.xOffset);
                line.setAttribute("y2", 8);
                line.setAttribute("stroke", "var(--timeline-bg)");
                svg.appendChild(line);

                // create tick text (year)
                const text = document.createElementNS(this.svgNs, "text");
                text.setAttribute("x", tick.xOffset);
                text.setAttribute("y", -20);
                text.setAttribute("text-anchor", "middle");
                text.setAttribute("font-size", "16px");
                text.setAttribute("fill", "var(--timeline-fg)");

                text.textContent = tick.value;
                svg.appendChild(text);
            }
        });
    }
}
