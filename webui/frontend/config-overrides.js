const { override, addBabelPlugin, addWebpackPlugin } = require('customize-cra');
const CompressionPlugin = require('compression-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = override(
  // Enable code splitting with optimized chunk strategy
  (config) => {
    // Production optimizations
    if (process.env.NODE_ENV === 'production') {
      // Enable runtime chunk for better long-term caching
      config.optimization.runtimeChunk = 'single';
      
      // Optimize chunk splitting
      config.optimization.splitChunks = {
        chunks: 'all',
        cacheGroups: {
          // Vendor chunk: React, React-DOM, and core libraries
          vendor: {
            test: /[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom)[\\/]/,
            name: 'vendor',
            priority: 40,
            reuseExistingChunk: true,
          },
          // UI libraries chunk: MUI and styling
          uiLibs: {
            test: /[\\/]node_modules[\\/](@mui|@emotion|framer-motion)[\\/]/,
            name: 'ui-libs',
            priority: 30,
            reuseExistingChunk: true,
          },
          // Charts chunk: Recharts, ReactFlow, etc.
          charts: {
            test: /[\\/]node_modules[\\/](recharts|reactflow|dagre)[\\/]/,
            name: 'charts',
            priority: 30,
            reuseExistingChunk: true,
          },
          // Editor chunk: Monaco and code editors
          editors: {
            test: /[\\/]node_modules[\\/](monaco-editor|@monaco-editor)[\\/]/,
            name: 'editors',
            priority: 30,
            reuseExistingChunk: true,
          },
          // Icons chunk
          icons: {
            test: /[\\/]node_modules[\\/](lucide-react|@mui\/icons-material)[\\/]/,
            name: 'icons',
            priority: 25,
            reuseExistingChunk: true,
          },
          // Common utilities chunk
          utils: {
            test: /[\\/]node_modules[\\/](axios|socket\.io-client|zustand|zod|clsx)[\\/]/,
            name: 'utils',
            priority: 20,
            reuseExistingChunk: true,
          },
          // Default chunk for remaining node_modules
          defaultVendors: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            priority: 10,
            reuseExistingChunk: true,
          },
          // Common shared code
          common: {
            minChunks: 2,
            priority: 5,
            reuseExistingChunk: true,
            name: 'common',
          },
        },
      };

      // Enhanced minification
      config.optimization.minimizer = [
        new TerserPlugin({
          terserOptions: {
            parse: {
              ecma: 2020,
            },
            compress: {
              ecma: 2015,
              comparisons: false,
              inline: 2,
              drop_console: true, // Remove console.logs in production
              drop_debugger: true,
            },
            mangle: {
              safari10: true,
            },
            output: {
              ecma: 2015,
              comments: false,
              ascii_only: true,
            },
          },
        }),
      ];

      // Add compression plugin for gzip
      config.plugins.push(
        new CompressionPlugin({
          filename: '[path][base].gz',
          algorithm: 'gzip',
          test: /\.(js|css|html|svg)$/,
          threshold: 10240, // Only compress files > 10KB
          minRatio: 0.8,
        })
      );
    }

    // Development optimizations
    if (process.env.NODE_ENV === 'development') {
      // Faster rebuilds in development
      config.optimization.runtimeChunk = false;
      config.optimization.splitChunks = {
        chunks: 'async', // Only split async chunks in dev for faster rebuild
        cacheGroups: {
          defaultVendors: {
            test: /[\\/]node_modules[\\/]/,
            priority: -10,
            reuseExistingChunk: true,
          },
        },
      };
    }

    // Improved tree shaking
    config.optimization.usedExports = true;
    config.optimization.sideEffects = true;

    // Source maps configuration
    if (process.env.NODE_ENV === 'production') {
      // No source maps in production for security and size
      config.devtool = false;
    }

    return config;
  }
);
