const path = require("path")

const Autoprefixer = require("autoprefixer")
const BundleTracker = require("webpack-bundle-tracker")
const MiniCssExtractPlugin = require("mini-css-extract-plugin")

module.exports = (env, options) => ({
    entry: {
        main: [
            "./sitemedia/esm/main.esm.js",
            "./sitemedia/scss/main.scss",
        ],
    },
    output: {
        path: path.resolve(__dirname, "sitemedia", "bundles"),
        publicPath: options.mode == "production" ? "/static/bundles/" : "http://localhost:3000/bundles/",
        filename: options.mode == "production" ? "[name]-[hash].min.js" : "[name].js",
        clean: true,
    },
    module: {
        rules: [
            {
                test: /\.(sa|sc|c)ss$/,
                use: [
                    options.mode == "production" ? MiniCssExtractPlugin.loader : "style-loader",
                    { loader: "css-loader" },
                    {
                        loader: "postcss-loader",
                        options: {
                            postcssOptions: {
                                plugins: [
                                    Autoprefixer()
                                ]
                            }
                        }
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
                    }
                ],
            },
            {
                test: /\.esm?$/,
                loader: "babel-loader",
            }
        ],
    },
    plugins: [
        new BundleTracker({
            filename: options.mode == "production" ? "./sitemedia/webpack-stats.json" : "./sitemedia/webpack-stats-dev.json",
            indent: 2
        }),
        new MiniCssExtractPlugin({
            filename: options.mode == "production" ? "[name]-[hash].min.css" : "[name].css",
        })
    ],
    devServer: {
        static: path.resolve(__dirname, "sitemedia", "bundles"),
        hot: false,
        port: 3000,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
            'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization',
        },
    }
})