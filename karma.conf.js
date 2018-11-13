module.exports = (config) => {
    config.set({
      frameworks: ['browserify', 'jasmine'],
      reporters: ['spec'],
      browsers: [
        'ChromeHeadless',
        'FirefoxHeadless'
      ],
      files: [
          'https://code.jquery.com/jquery-3.1.1.min.js',
          'node_modules/jasmine-jquery/lib/jasmine-jquery.js',
          'sitemedia/semantic/dist/semantic.min.js',
          'sitemedia/js/tests/*.spec.js',
          { pattern: 'sitemedia/js/fixtures/*', served: true, included: false }
      ],
      preprocessors: {
        'sitemedia/**/*.js': ['browserify']
      },
      browserify: {
        debug: true,
        transform: [
            ['babelify', { 'presets': ['es2015'] }]
        ]
      }
    })
  }
  