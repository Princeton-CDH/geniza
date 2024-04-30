// controllers/map_controller.js

import { Controller } from "@hotwired/stimulus";
import maplibregl, { NavigationControl } from "maplibre-gl";

export default class extends Controller {
    static targets = ["marker"];

    connect() {
        // add map if we have an access token
        const accessToken = this.element.dataset.maptilerToken;
        const lonlat = [this.element.dataset.lon, this.element.dataset.lat];
        if (accessToken) {
            const map = new maplibregl.Map({
                container: "map",
                style: `https://api.maptiler.com/maps/5f93d3e5-e339-45bf-86fb-bf7f98a22936/style.json?key=${accessToken}`,
                center: lonlat,
                zoom: 9,
            });
            const el = this.markerTarget;
            new maplibregl.Marker({
                anchor: "bottom",
                element: el,
            })
                .setLngLat(lonlat)
                .addTo(map);
            map.addControl(new NavigationControl({ showCompass: false }));
        }
    }
}
