target = document.getElementById("iiif_viewer");
let miradorInstance = null;
if (target) {
    let windowOpts = {
        allowClose: false, // Prevent the user from closing this window
        allowMaximize: false,
        allowFullscreen: true,
        defaultSideBarPanel: "info",
        sideBarOpenByDefault: false,
        views: [
            // Only allow the user to select single and gallery view
            { key: "single" },
            { key: "gallery" },
        ],
        defaultView: "single",
    };

    // adjust window config if a document has annotations
    if (target.dataset.hasAnnotations) {
        windowOpts.defaultSideBarPanel = "annotations";
        windowOpts.sideBarOpenByDefault = true;
        windowOpts.defaultSidebarPanelWidth = 475;
    }

    miradorInstance = Mirador.viewer({
        id: target.id,
        window: windowOpts,
        galleryView: {
            height: 250,
        },
        thumbnailNavigation: {
            defaultPosition: "far-right",
        },
        windows: [
            {
                // single document / workspace only
                manifestId: target.dataset.iiifUrl,
            },
        ],
        workspaceControlPanel: {
            enabled: false, // Remove extra workspace settings,
        },
        workspace: {
            allowNewWindows: false,
            type: "mosaic",
        },
        annotations: {
            // don't strip out html in our transcription content
            htmlSanitizationRuleSet: "liberal",
        },
    });
}
