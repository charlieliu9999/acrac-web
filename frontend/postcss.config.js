// PostCSS配置文件 - 专为 React + Ant Design 项目优化
module.exports = {
  plugins: {
    // 自动添加浏览器前缀
    autoprefixer: {
      overrideBrowserslist: [
        '> 1%',
        'last 2 versions',
        'not dead',
        'not ie 11'
      ],
      grid: 'autoplace',
      remove: true
    },

    // CSS优化插件（仅生产环境）
    ...(process.env.NODE_ENV === 'production' ? {
      // CSS压缩
      cssnano: {
        preset: [
          'default',
          {
            discardComments: {
              removeAll: false,
              removeAllButFirst: false
            },
            calc: {
              precision: 3
            },
            colormin: {
              legacy: true
            },
            minifyFontValues: {
              removeQuotes: false
            },
            minifySelectors: {
              removeUnusedSelectors: false
            },
            mergeRules: {
              safe: true
            },
            mergeMediaQueries: true,
            discardDuplicates: true,
            discardEmpty: true,
            normalizeDisplayValues: true,
            normalizePositions: true,
            normalizeRepeatStyle: true,
            normalizeString: {
              preferredQuote: 'single'
            },
            normalizeTimingFunctions: true,
            normalizeUnicode: true,
            normalizeUrl: {
              stripWWW: false
            },
            normalizeWhitespace: true,
            sortMediaQueries: {
              sort: 'mobile-first'
            },
            uniqueSelectors: true,
            zindex: {
              startIndex: 1
            }
          }
        ]
      }
    } : {})
  }
}

