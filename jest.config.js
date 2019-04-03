const path = require('path')

module.exports = {
    preset: 'ts-jest/presets/js-with-ts', // handle both js and ts
    rootDir: path.resolve(__dirname, 'srcmedia'),
    testRegex: '^.+\\.(test|spec)\\.tsx?$',
    moduleFileExtensions: ['js', 'jsx', 'ts', 'tsx', 'json', 'node'],
    coverageDirectory: '<rootDir>/coverage',
    collectCoverageFrom: [
        "ts/components/*.{ts,tsx}", // we're only unit testing components
        '!**/node_modules/**', // don't cover pulled-in dependencies
    ]
}
