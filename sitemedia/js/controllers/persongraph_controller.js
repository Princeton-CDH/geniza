// controllers/persongraph_controller.js

import { Controller } from "@hotwired/stimulus";
import cytoscape from "cytoscape";
import cytoscapeHTML from "cytoscape-html";

export default class extends Controller {
    static targets = ["graphContainer", "person"];
    NODE_CONSTANTS = {
        selected: false,
        selectable: false,
        locked: true,
        grabbable: false,
        pannable: true,
    };

    graphContainerTargetConnected() {
        // get container and data
        const container = this.graphContainerTarget;
        const relationLevels = JSON.parse(
            document.getElementById("relation-levels").textContent
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
                position: { x: 0, y: 0 },
                classes: ["primary"],
                ...this.NODE_CONSTANTS,
            },
        ];
        const colCounts = {};
        let maxXPos = 0;
        let nodes = initNode.concat(
            this.personTargets
                // sort such that immediate family always comes first
                .toSorted((person) =>
                    person.dataset.category === "I" ? -1 : 1
                )
                .map((row) => {
                    // loop through each related person's data
                    const cols = row.querySelectorAll("td");
                    const [persName, relType, _sharedDocs, _notes] = cols;
                    const persId = row.dataset.id;
                    const persLink = row.dataset.href || "";
                    const relTypeName = relType.textContent.trim();
                    const relationLevel = relationLevels[relTypeName];
                    if (relationLevel || relationLevel === 0) {
                        // keep track of index per relation level (i.e. columns per row)
                        if (Object.hasOwn(colCounts, relationLevel)) {
                            colCounts[relationLevel] += 1;
                        } else {
                            colCounts[relationLevel] =
                                relationLevel === 0 ? 1 : 0;
                        }
                        // compute x position so that it results in the order 0, 1, -1, 2, -2, etc.
                        const xPos =
                            colCounts[relationLevel] % 2 === 0
                                ? -Math.floor(colCounts[relationLevel] / 2)
                                : Math.floor(colCounts[relationLevel] / 2) + 1;
                        if (xPos > maxXPos) maxXPos = xPos;
                        edges.push({
                            group: "edges",
                            data: {
                                target: this.element.dataset.id,
                                source: persId,
                            },
                        });
                        return {
                            group: "nodes",
                            data: {
                                id: persId,
                                html: this.getNodeHtml(
                                    "node-secondary",
                                    persName.innerHTML.trim(),
                                    row.dataset.gender,
                                    relTypeName
                                ),
                                href: persLink,
                            },
                            position: { x: xPos * 200, y: relationLevel * 100 },
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
                            },
                        });
                        // define position later; need max X pos among all nodes first
                        return {
                            group: "nodes",
                            data: {
                                id: persId,
                                html: this.getNodeHtml(
                                    "node-tertiary",
                                    persName.innerHTML.trim(),
                                    row.dataset.gender,
                                    relTypeName
                                ),
                                href: persLink,
                            },
                            ...this.NODE_CONSTANTS,
                        };
                    }
                })
        );
        // set positions for non-familial nodes
        nodes
            .filter(
                (node) =>
                    node.group === "nodes" && !Object.hasOwn(node, "position")
            )
            .forEach((node, i) => {
                const yPos =
                    i % 2 === 0 ? -Math.floor(i / 2) : Math.floor(i / 2) + 1;
                node.position = {
                    x: (maxXPos + 1) * 200,
                    y: yPos * 100,
                };
            });
        cytoscape.use(cytoscapeHTML);
        this.cy = cytoscape({
            container,
            elements: [...nodes, ...edges],
            layout: {
                name: "preset",
                fit: false,
            },
            zoom: 1,
            style: [
                {
                    selector: "node",
                    style: {
                        width: "180px",
                        height: "54px",
                    },
                },
                {
                    selector: "edge",
                    style: {
                        "curve-style": "taxi",
                        width: 1,
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
}
