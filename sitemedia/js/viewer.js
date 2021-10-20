target = document.getElementById("iiif_viewer");
if (target) {
    iiifUrls = target.dataset.iiifUrls.split(" ");
    Mirador.viewer({
        id: target.id,
        window: {
            allowClose: false, // Prevent the user from closing this window
            allowMaximize: false,
            defaultSideBarPanel: "info",
            sideBarOpenByDefault: false,
            views: [
                // Only allow the user to select single and gallery view
                { key: "single" },
                { key: "gallery" },
            ],
            defaultView: "single",
        },
        galleryView: {
            height: 250,
        },
        thumbnailNavigation: {
            defaultPosition: "far-right",
        },
        windows: iiifUrls.map((url) => ({ loadedManifest: url })),
        workspaceControlPanel: {
            enabled: false, // Remove extra workspace settings,
        },
    });
}
