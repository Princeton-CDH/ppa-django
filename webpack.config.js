const path = require('path')
const BundleTracker = require('webpack-bundle-tracker')
const MiniCssExtractPlugin = require('mini-css-extract-plugin')
const CleanWebpackPlugin = require('clean-webpack-plugin')
const GlobImporter = require('node-sass-glob-importer')
const OptimizeCSSAssetsPlugin = require('optimize-css-assets-webpack-plugin')
const TerserPlugin = require('terser-webpack-plugin')
const devMode = process.env.NODE_ENV !== 'production' // i.e. not prod or qa

module.exports = env => ({
    context: path.resolve(__dirname, 'srcmedia'),
    mode: devMode ?  'development' : 'production',
    entry: {
        main: [
            './js/index.js', // main site js
            './scss/ppa.scss' // main site styles
        ],
        home: './js/home.js', // homepage (parallax)
        search: './js/search.js', // scripts & styles for search page
        searchWithin: './ts/searchWithin.ts', // components & styles for search within work page
    },
    output: {
        path: path.resolve(__dirname, 'bundles'), // where to output bundles
        publicPath: devMode ? 'http://localhost:3000/' : '/static/', // tell Django where to serve bundles from
        filename: devMode ? 'js/[name].js' : 'js/[name]-[hash].min.js', // append hashes in prod
    },
    module: {
        rules: [
            { // transpile ES6+ to ES5 using Babel
                test: /\.(t|j)sx?$/,
                loader: 'awesome-typescript-loader',
                exclude: /node_modules/, // don't transpile dependencies
            },
            { // load and compile styles to CSS
                test: /\.(sa|sc|c)ss$/,
                use: [
                    devMode ? 'style-loader' : MiniCssExtractPlugin.loader, // use style-loader for hot reload in dev
                    'css-loader',
                    'postcss-loader', // for autoprefixer
                    { loader: 'sass-loader', options: { importer: GlobImporter() } }, // allow glob scss imports
                ],
            },
            { // load images
                test: /\.(png|jpg|gif|svg)$/,
                loader: 'file-loader',
                options: {
                  name: devMode ? 'img/[name].[ext]' : 'img/[name]-[hash].[ext]', // append hashes in prod
                }
            }
        ]
    },
    plugins: [
        new BundleTracker({ filename: 'webpack-stats.json' }), // tells Django where to find webpack output
        new MiniCssExtractPlugin({ // extracts CSS to a single file per entrypoint
            filename: devMode ? 'css/[name].css' : 'css/[name]-[hash].min.css', // append hashes in prod
        }),
        ...(devMode ? [] : [new CleanWebpackPlugin('bundles')]), // clear out bundle dir when rebuilding in prod/qa
    ],
    resolve: {
        extensions: ['.js', '.jsx', '.ts', '.tsx', '.json', '.scss'] // enables importing these without extensions
    },
    devServer: {
        contentBase: path.join(__dirname, 'bundles'), // serve this as webroot
        overlay: true,
        port: 3000,
        allowedHosts: ['localhost'],
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
            'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization',
        },
        stats: { // hides file-level verbose output when server is running
            children: false, 
            modules: false,
        }
    },
    devtool: devMode ? 'eval-source-map' : 'source-map', // allow sourcemaps in dev & qa
    optimization: {
        minimizer: [
            new TerserPlugin({ // minify JS in prod
                cache: true, // cache unchanged assets
                parallel: true, // run in parallel (recommended)
                sourceMap: env.maps // preserve sourcemaps if env.maps was passed
            }),
            new OptimizeCSSAssetsPlugin({ // minify CSS in prod
                ... (env.maps && { cssProcessorOptions: { // if env.maps was passed, 
                    map: { inline: false, annotation: true } // preserve sourcemaps
                }})
            })
        ]
    }
})
