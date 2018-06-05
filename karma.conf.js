module.exports = (config) => {
    config.set({
      frameworks: ['browserify', 'jasmine'],
      reporters: ['spec'],
      browsers: ['ChromeHeadless'],
      files: [
          'https://code.jquery.com/jquery-3.1.1.min.js',
          'sitemedia/semantic/dist/semantic.min.js',
          'ppa/**/*.spec.js',
      ],
      preprocessors: {
        'ppa/**/*.js': ['browserify'],
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
  