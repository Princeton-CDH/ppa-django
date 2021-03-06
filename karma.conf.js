let webpackCfg = require('./webpack.config')

module.exports = (config) => {
    config.set({
      frameworks: ['jasmine'],
      reporters: ['spec'],
      browsers: [
        'ChromeHeadless',
        'FirefoxHeadless'
      ],
      files: [
          'https://code.jquery.com/jquery-3.1.1.min.js',
          'node_modules/jasmine-jquery/lib/jasmine-jquery.js',
          'sitemedia/semantic/dist/semantic.min.js',
          'srcmedia/test/**/*.spec.js',
          { pattern: 'srcmedia/test/fixtures/*', served: true, included: false }
      ],
      preprocessors: {
        'srcmedia/**/*.js': ['webpack']
      },
      webpack: webpackCfg({ maps: true })
    })
  }
  