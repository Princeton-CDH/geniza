const path = require("path");

const Autoprefixer = require("autoprefixer");
const BundleTracker = require("webpack-bundle-tracker");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");
const { IgnorePlugin } = require("webpack");

module.exports = (env, options) => ({
    // NOTE if you add a new entrypoint, update the dummy webpack-stats-ci.json
    // in the sitemedia/ folder to list it as an empty array.
    entry: {
        // locations and filenames of entry points for bundles
        main: [
            // this name ("main") is referenced by django-webpack-loader's {% render_bundle %} tag
            "./sitemedia/scss/main.scss",
            "./sitemedia/js/main.js",
        ],
        iiif: [
            "./sitemedia/scss/components/_transcription.scss",
            "./sitemedia/js/iiif.js",
        ],
        annotation: [
            "./sitemedia/scss/annotation.scss",
            "./sitemedia/js/annotation.js",
        ],
        admin: ["./sitemedia/js/admin.js"],
    },
    output: {
        // locations and filenames of bundled files
        path: path.resolve(__dirname, "sitemedia", "bundles"),
        publicPath:
            options.mode == "production"
                ? "/static/bundles/"
                : "http://localhost:3000/bundles/",
        filename:
            options.mode == "production"
                ? "[name]-[contenthash].min.js"
                : "[name].js",
        clean: true, // remove bundles from previous builds
    },
    module: {
        rules: [
            // load tinyMCE css as ES modules so we can use them in JS code
            {
                test: /(skin|content|shadowdom)(\.min)?\.css$/i,
                use: [
                    {
                        loader: "css-loader",
                        options: {
                            esModule: true,
                        },
                    },
                ],
            },
            // styles configuration: handle .sass, .scss, .css files and apply autoprefixer
            {
                test: /(?<!skin|content|shadowdom)(?<!\.min)\.(sa|sc|c)ss$/,
                use: [
                    // extract all styles into a single file in prod; serve directly from memory in dev
                    options.mode == "production"
                        ? MiniCssExtractPlugin.loader
                        : "style-loader",
                    { loader: "css-loader", options: { url: false } },
                    {
                        loader: "postcss-loader", // postcss used for Autoprefixer
                        options: {
                            postcssOptions: {
                                plugins: [Autoprefixer()],
                            },
                        },
                    },
                    {
                        loader: "sass-loader",
                        options: {
                            // Material Design prefers Dart Sass
                            implementation: require("sass"),

                            // See https://github.com/webpack-contrib/sass-loader/issues/804
                            webpackImporter: false,
                            sassOptions: {
                                includePaths: ["./node_modules"],
                            },
                        },
                    },
                ],
            },
            // script configuration: handle .js files and transpile with babel
            {
                test: /\.js$/,
                loader: "babel-loader",
                exclude: /node_modules/, // don't transpile dependencies
            },
        ],
    },
    plugins: [
        // output manifest file so django knows where bundles live
        // https://github.com/django-webpack/webpack-bundle-tracker
        new BundleTracker({
            filename: "./sitemedia/webpack-stats.json",
            relativePath: true,
            indent: 2,
        }),
        // extract css into a single file
        // https://webpack.js.org/plugins/mini-css-extract-plugin/
        new MiniCssExtractPlugin({
            filename:
                options.mode == "production"
                    ? "[name]-[contenthash].min.css"
                    : "[name].css",
        }),
        new IgnorePlugin({
            // ignore unneeded jquery dependency in angle-input
            resourceRegExp: /jquery/u,
            contextRegExp: /angle-input/u,
        }),
    ],
    // configuration for dev server (run using `npm start`)
    // https://webpack.js.org/configuration/dev-server/
    devServer: {
        static: path.resolve(__dirname, "sitemedia", "bundles"),
        hot: false, // disable hot module reloading since we don't use it
        port: 3000,
        headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods":
                "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers":
                "X-Requested-With, content-type, Authorization",
        },
    },
    // enable importing .esm.js and other files without specifying extensions
    resolve: {
        extensions: [".js", ".esm.js", ".sass", ".scss"],
        modules: [path.resolve("./bundles"), "node_modules"],
    },
    // generate source maps for easier debugging
    devtool: "source-map",
    // minify JS and CSS in production
    optimization: {
        minimizer: [
            "...", // shorthand; minify JS using the default TerserPlugin
            new CssMinimizerPlugin(), // also minify CSS
        ],
        // chunking required for tinyMCE JS and CSS bundling
        splitChunks: {
            chunks: "all",
            cacheGroups: {
                tinymceVendor: {
                    test: /[\/]node_moduleslink:tinymce[\/]link:.*js|.*skin.css[\/]|[\/]plugins[\/]/,
                    name: "tinymce",
                },
            },
        },
    },
});
