// controllers/persongraph_controller.js

import { Controller } from "@hotwired/stimulus";
import cytoscape from "cytoscape";
import cytoscapeHTML from "cytoscape-html";

export default class extends Controller {
    static targets = ["graphContainer", "person", "tooltip"];
    NODE_CONSTANTS = {
        selected: false,
        selectable: false,
        grabbable: false,
        pannable: true,
    };

    graphContainerTargetConnected() {
        // get container and data
        const container = this.graphContainerTarget;
        const relationCategories = JSON.parse(
            document.getElementById("relation-categories").textContent
        );

        // initialize nodes and edges with this person as center node
        const edges = [];
        const initNode = [
            {
                group: "nodes",
                data: {
                    id: this.element.dataset.id,
                    html: this.getNodeHtml(
                        "node-primary",
                        this.element.dataset.name.trim(),
                        this.element.dataset.gender,
                        null
                    ),
                },
                // position: { x: 0, y: 0 },
                classes: ["primary"],
                ...this.NODE_CONSTANTS,
            },
        ];
        let nodes = initNode.concat(
            this.personTargets
                // sort such that immediate family always comes first
                .toSorted((person) =>
                    person.dataset.category === "I" ? -1 : 1
                )
                .map((row) => {
                    // loop through each related person's data
                    const cols = row.querySelectorAll("td");
                    const [persName, relType, sharedDocs, _notes] = cols;
                    const persId = row.dataset.id;
                    const persLink = row.dataset.href || "";
                    const relTypeNames = relType.textContent.trim().split(", ");
                    let relationCat = null;
                    relTypeNames.forEach((rtn) => {
                        let relTypeName =
                            rtn.charAt(0).toUpperCase() + rtn.slice(1);
                        if (Object.hasOwn(relationCategories, relTypeName)) {
                            relationCat = relationCategories[relTypeName];
                        }
                    });
                    const ndocs = parseInt(sharedDocs.textContent);
                    const style = { width: (ndocs % 10) + 1 };
                    const label = `${ndocs} document${
                        ndocs == 1 ? "" : "s"
                    } with ${persName.textContent.trim()}`;
                    if (["E", "I", "M"].includes(relationCat)) {
                        edges.push({
                            group: "edges",
                            data: {
                                target: this.element.dataset.id,
                                source: persId,
                                label,
                            },
                            style,
                        });
                        return {
                            group: "nodes",
                            data: {
                                id: persId,
                                html: this.getNodeHtml(
                                    "node-secondary",
                                    persName.innerHTML.trim(),
                                    row.dataset.gender,
                                    relType.textContent.trim()
                                ),
                                href: persLink,
                                category: relationCat,
                            },
                            classes: ["secondary"],
                            ...this.NODE_CONSTANTS,
                        };
                    } else {
                        // non-familial relationships
                        edges.push({
                            group: "edges",
                            data: {
                                target: this.element.dataset.id,
                                source: persId,
                                label,
                            },
                            style,
                        });
                        return {
                            group: "nodes",
                            data: {
                                id: persId,
                                html: this.getNodeHtml(
                                    "node-tertiary",
                                    persName.innerHTML.trim(),
                                    row.dataset.gender,
                                    relType.textContent.trim()
                                ),
                                href: persLink,
                                category: relationCat,
                            },
                            ...this.NODE_CONSTANTS,
                        };
                    }
                })
        );
        // set positions for non-familial nodes
        cytoscape.use(cytoscapeHTML);
        this.cy = cytoscape({
            container,
            elements: [...nodes, ...edges],
            layout: {
                name: "concentric",
                fit: false,
                avoidOverlap: true,
                startAngle: 0,
                minNodeSpacing: 20,
                levelWidth: () => 1,
                concentric: (node) => {
                    // set distance away from origin (concentric circles)
                    switch (node.data("category")) {
                        case "B":
                            // business relationships: furthest away
                            return 1;
                        case "M":
                            // relationships by marriage
                            return 2;
                        case "E":
                            // extended family
                            return 3;
                        case "I":
                            // immediate family: innermost circle
                            return 4;
                        default:
                            // self: center
                            return 5;
                    }
                },
                transform: (node, position) => {
                    // slightly rotate each concentric circle about the origin
                    // to prevent overlapping edges as much as possible
                    const origin = { x: 448, y: 193 };
                    const { x, y } = position;
                    let angle = 0;
                    switch (node.data("category")) {
                        case "B":
                            angle = -50;
                            break;
                        case "M":
                            angle = -40;
                            break;
                        case "E":
                            angle = -25;
                            break;
                        case "I":
                            angle = -10;
                            break;
                        default:
                            angle = 0;
                            break;
                    }
                    const newPt = this.rotate(origin.x, origin.y, x, y, angle);
                    return { x: newPt[0], y: newPt[1] };
                },
            },
            zoom: 0.75,
            style: [
                {
                    selector: "node",
                    style: {
                        width: "180px",
                        height: "54px",
                    },
                },
            ],
        });
        this.cy.nodes().renderHTMLNodes({ hideOriginal: true });
        this.cy.center("node.primary");
        this.cy.on("tap", "node", function () {
            if (this.data("href")) {
                try {
                    // your browser may block popups
                    window.open(this.data("href"));
                } catch (e) {
                    // fall back on url change
                    window.location.href = this.data("href");
                }
            }
        });
        this.cy.on("mouseover", "node", (event) => {
            if (event.target.data("href") && event.cy.container()) {
                event.cy.container().style.cursor = "pointer";
            }
        });
        this.cy.on("mouseout", "node", (event) => {
            if (event.cy.container()) {
                event.cy.container().style.cursor = "grab";
            }
        });
        this.updateTooltipSize();
        this.cy.on("mouseover", "edge", (event) => {
            this.tooltipTarget.innerText = event.target.data("label");
            this.tooltipTarget.style.display = "flex";
            this.updateTooltipSize();
            event.cy.container().style.cursor = "pointer";
            event.target.style({ "line-color": "#000" });
        });
        const destroyTooltip = (event) => {
            this.tooltipTarget.innerText = "";
            this.tooltipTarget.style.display = "none";
            if (event.cy) {
                event.cy.container().style.cursor = "grab";
                event.target.style({ "line-color": "#999" });
            } else {
                this.cy.edges().style({ "line-color": "#999" });
            }
        };
        this.cy.on("mouseout", "edge", destroyTooltip);
        this.graphContainerTarget.addEventListener("mouseout", destroyTooltip);
        this.cy.on("mousemove", "edge", (event) => {
            const y = event.originalEvent.clientY + window.scrollY;
            const x = event.originalEvent.clientX + window.scrollX + 5;
            if (x + 200 * this.cy.zoom() > window.innerWidth) {
                this.tooltipTarget.style.left = "auto";
                this.tooltipTarget.style.right = `${
                    window.innerWidth - event.originalEvent.clientX - 8
                }px`;
            } else {
                this.tooltipTarget.style.right = "auto";
                this.tooltipTarget.style.left = `${x}px`;
            }
            this.tooltipTarget.style.top = `${y}px`;
        });
        this.cy.on("zoom", this.updateTooltipSize.bind(this));
    }

    updateTooltipSize() {
        // helper function to scale tooltip on cytoscape zoom
        this.tooltipTarget.style.fontSize = `${Math.min(this.cy.zoom(), 2)}rem`;
        this.tooltipTarget.style.maxWidth = this.cy.zoom() * 200;
    }

    getNodeHtml(className, persName, gender, relTypeName) {
        // helper function to construct HTML node
        let html = `<div class="${className}">
            <span class="gender">${gender}</span>
            <div class="meta"><span class="name">${persName}</span>`;
        if (relTypeName) {
            html += `<span class="reltype">${relTypeName}</span>`;
        }
        return `${html}</div></div>`;
    }

    getCssVar(varName) {
        // helper function to get a CSS variable from the document
        return getComputedStyle(document.body).getPropertyValue(varName);
    }

    rotate(cx, cy, x, y, angle) {
        // helper function to rotate a point (x, y) around a center (cx, cy)
        const radians = (Math.PI / 180) * angle,
            cos = Math.cos(radians),
            sin = Math.sin(radians),
            nx = cos * (x - cx) + sin * (y - cy) + cx,
            ny = cos * (y - cy) - sin * (x - cx) + cy;
        return [nx, ny];
    }
}
