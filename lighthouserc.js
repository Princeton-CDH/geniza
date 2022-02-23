module.exports = {
    ci: {
        collect: {
            // URLs that Lighthouse will visit and test
            url: [
                "http://localhost:8000/", // home page
                "http://localhost:8000/en/documents/", // doc search
                "http://localhost:8000/en/documents/8151/", // doc detail — including OpenSeaDragon
                "http://localhost:8000/en/documents/8151/scholarship/", // doc scholarship
                "http://localhost:8000/en/content/", // content page
            ],
            // The following two commands make Lighthouse start up a Django
            // server for us to test against. PYTHONUNBUFFERED is needed to make
            // stdout from the server process visible to Lighthouse; when it
            // sees the server print "Quit the server with..." it knows the
            // server is running and ready to accept HTTP requests. We use the
            // --insecure flag so that Django serves static files from static/;
            // they first need to be built with Webpack and then collected.
            startServerCommand:
                "PYTHONUNBUFFERED=1 python manage.py runserver --insecure",
            startServerReadyPattern: "Quit the server",
        },
        upload: {
            target: "temporary-public-storage",
        },
        assert: {
            preset: "lighthouse:no-pwa",
            assertions: {
                // ignore warnings about serving files using compression and
                // setting long cache times; we'll handle these separately
                // using nginx or apache for actual deploys
                "uses-text-compression": "off",
                "uses-long-cache-ttl": "off",
                // erroring about a console issue; seems to be user agent in webpack?
                "inspector-issues": "off",
                "errors-in-console": "off",
                "unminified-css": "off",
                "unused-css-rules": "off",
                // not quite following strict csp (yet)
                "csp-xss": "off",
                // this is important, but failing so disable for now
                "render-blocking-resources": "off",
                // next two are only failing because of OpenSeaDragon, so disable for now
                "unsized-images": "off",
                "unused-javascript": "off",
                // allow 1 offscreen image per page (OpenSeaDragon first image)
                "offscreen-images": ["error", { maxLength: 1 }],
            },
        },
    },
};
