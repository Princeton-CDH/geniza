// controllers/map_controller.js

import { Controller } from "@hotwired/stimulus";
import maplibregl, { LngLatBounds, NavigationControl } from "maplibre-gl";

export default class extends Controller {
    static targets = ["marker"];

    connect() {
        // add map if we have an access token
        const accessToken = this.element.dataset.maptilerToken;
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
            const map = new maplibregl.Map({
                container: "map",
                style: `https://api.maptiler.com/maps/5f93d3e5-e339-45bf-86fb-bf7f98a22936/style.json?key=${accessToken}`,
                ...zoomParams,
            });

            // add navigation control
            const control = new NavigationControl({ showCompass: false });
            map.addControl(control);

            // add each marker
            const coordinates = this.markerTargets.map((marker) => {
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
                        .addTo(map);
                }
                return loc;
            });

            if (this.markerTargets.length > 1) {
                // more than one marker: fit map to marker boundaries
                // code from https://stackoverflow.com/a/63058036/394067
                const bounds = coordinates.reduce(function (bounds, coord) {
                    return bounds.extend(coord);
                }, new LngLatBounds(coordinates[0], coordinates[0]));
                map.fitBounds(bounds, {
                    padding: { top: 50, bottom: 50, left: 50, right: 50 },
                });
            }
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
        element.scrollIntoView({ behavior: "smooth" });
        element.classList.add("selected-place");
    }
}
