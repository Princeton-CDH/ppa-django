const path = require('path')

module.exports = {
    preset: 'ts-jest/presets/js-with-ts', // handle both js and ts
    rootDir: path.resolve(__dirname, 'srcmedia'),
    testRegex: '^.+\\.(test|spec)\\.tsx?$',
    testEnvironment: "jsdom",
    moduleFileExtensions: ['js', 'jsx', 'ts', 'tsx', 'json', 'node'],
    coverageDirectory: '<rootDir>/coverage',
    collectCoverageFrom: [
        "ts/**/*.{ts,tsx}", // get coverage for all ts...
        "!ts/searchWithin.ts", // *except* page files, which should be e2e tested
        '!**/node_modules/**', // don't cover pulled-in dependencies
    ]
}
