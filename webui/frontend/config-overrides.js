const { override, addBabelPlugin } = require('customize-cra');

module.exports = override(
  // Disable code splitting to ensure React is bundled correctly
  (config) => {
    config.optimization.runtimeChunk = false;
    config.optimization.splitChunks = {
      cacheGroups: {
        default: false,
      },
    };
    return config;
  }
);
