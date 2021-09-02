module.exports = {
    ci: {
        collect: {
            url: ["http://localhost:8000/documents/"],
            // The following two commands make Lighthouse start up a Django
            // server for us to test against. PYTHONUNBUFFERED is needed to make
            // stdout from the server process visible to Lighthouse; when it
            // sees the server print "Quit the server with..." it knows the
            // server is running and ready to accept HTTP requests. We use the
            // --insecure flag so that Django serves static files from static/;
            // they first need to be built with Webpack and then collected.
            startServerCommand: "PYTHONUNBUFFERED=1 python manage.py runserver --insecure",
            startServerReadyPattern: "Quit the server"
        },
        upload: {
            target: "temporary-public-storage",
        },
        assert: {
            preset: "lighthouse:no-pwa",
        },
    }
}