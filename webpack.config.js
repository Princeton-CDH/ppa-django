const path = require('path')

const BundleTracker = require('webpack-bundle-tracker')
const MiniCssExtractPlugin = require('mini-css-extract-plugin')
// const CleanWebpackPlugin = require('clean-webpack-plugin')
// const GlobImporter = require('node-sass-glob-importer')
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");
const devMode = process.env.NODE_ENV !== 'production' // i.e. not prod or qa

module.exports = env => ({
    context: path.resolve(__dirname, 'srcmedia'),
    mode: devMode ? 'development' : 'production',
    // NOTE: if you add/remove bundles (entrypoints), make sure to update the
    // fake webpack-stats.json in the ci/ folder, since it is required to run
    // tests that rely on static files. For more info, see:
    // https://github.com/django-webpack/django-webpack-loader/issues/187
    entry: {
        main: [
            './js/index.js', // main site js
            './scss/ppa.scss', // main site styles
        ],
        print: './scss/print.scss', // print styles
        home: './js/home.js', // homepage (parallax)
        search: './js/search.js', // scripts & styles for search page
        searchWithin: './ts/searchWithin.ts', // components & styles for search within work page
        pdf: './js/controllers/pdf.js' // wagtail stimulus extension for PDF generation
    },
    output: {
        path: path.resolve(__dirname, 'bundles'), // where to output bundles
        publicPath: devMode ? 'http://localhost:3000/' : '/static/', // tell Django where to serve bundles from
        filename: devMode ? 'js/[name].js' : 'js/[name]-[contenthash].min.js', // append hashes in prod
        clean: true,
    },
    module: {
        rules: [
            { // compile TypeScript to js
                test: /^(?!.*\.test\.ts$).*\.tsx?$/,
                loader: 'ts-loader',
                exclude: [
                    /node_modules/, // don't transpile dependencies
                    /spec/,         // don't transpile tests
                ]
            },
            { // ensure output js has preserved sourcemaps
                enforce: "pre",
                test: /\.js$/,
                loader: "source-map-loader"
            },
            { // transpile es6+ js to es5
                test: /\.js$/,
                loader: 'babel-loader',
                exclude: /node_modules/, // don't transpile dependencies
            },
            { // load and compile styles to CSS
                test: /\.(sa|sc|c)ss$/,
                use: [
                    MiniCssExtractPlugin.loader,
                    { loader: 'css-loader', options: { url: false } },
                    'postcss-loader', // for autoprefixer
                    {
                        loader: 'sass-loader', options: {
                            // Material Design prefers Dart Sass
                            implementation: require("sass"),

                            // See https://github.com/webpack-contrib/sass-loader/issues/804
                            webpackImporter: false,
                            sassOptions: {
                                includePaths: ["./node_modules"],
                            },
                        }
                    },
                ],
            },
            {
                // load images
                test: /\.(png|svg|jpg|jpeg|gif)$/i,
                type: 'asset/resource',
                // previously had hashing depending on env; not supported by new loader
                //     options: {
                //         name: devMode ? 'img/[name].[ext]' : 'img/[name]-[hash].[ext]', // append hashes in prod
                //     }
            },
        ]
    },
    plugins: [
        new BundleTracker({
            filename: 'webpack-stats.json', // tells Django where to find webpack output
            path: __dirname,
            indent: 2
        }),
        // extract css into a single file
        // https://webpack.js.org/plugins/mini-css-extract-plugin/
        new MiniCssExtractPlugin({
            filename:
                devMode
                    ? "css/[name].css"
                    : "css/[name]-[contenthash].min.css"
        }),
        // new MiniCssExtractPlugin({ // extracts CSS to a single file per entrypoint
        // filename: devMode ? 'css/[name].css' : 'css/[name]-[hash].min.css', // append hashes in prod
        // }),
        // ...(devMode ? [] : [new CleanWebpackPlugin('bundles')]), // clear out bundle dir when rebuilding in prod/qa
    ],
    resolve: {
        extensions: ['.js', '.jsx', '.ts', '.tsx', '.json', '.scss'] // enables importing these without extensions
    },
    devServer: {
        static: {
            directory: path.join(__dirname, 'bundles'), // serve this as webroot
        },
        devMiddleware: {
            writeToDisk: true,
        },
        port: 3000,
        allowedHosts: ['localhost'],
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
            'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization',
        },
        client: {
            logging: 'warn',
            overlay: true,
        },
    },
    devtool: devMode ? 'eval-source-map' : 'source-map', // allow sourcemaps in dev & qa
    optimization: {
        minimizer: [
            "...", // shorthand; minify JS using the default TerserPlugin
            new CssMinimizerPlugin(), // also minify CSS
        ]
    }
})
