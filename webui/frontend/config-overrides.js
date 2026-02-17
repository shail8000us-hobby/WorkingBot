const { override, addBabelPlugin, addWebpackPlugin } = require('customize-cra');
const CompressionPlugin = require('compression-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const webpack = require('webpack');

module.exports = override(
  // Enable code splitting with optimized chunk strategy
  (config) => {
    // Production optimizations
    if (process.env.NODE_ENV === 'production') {
      // Enable runtime chunk for better long-term caching
      config.optimization.runtimeChunk = 'single';
      
      // Optimize chunk splitting with enhanced strategy
      config.optimization.splitChunks = {
        chunks: 'all',
        maxInitialRequests: Infinity,
        minSize: 20000, // 20KB minimum chunk size
        maxSize: 244000, // 244KB maximum chunk size (split larger chunks)
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
            enforce: true,
          },
          // Common shared code (used in multiple chunks)
          common: {
            minChunks: 2,
            priority: 5,
            reuseExistingChunk: true,
            name: 'common',
          },
        },
      };

      // Enhanced minification - modify existing minimizers to preserve console.log
      if (config.optimization.minimizer) {
        config.optimization.minimizer = config.optimization.minimizer.map((minimizer) => {
          if (minimizer.constructor.name === 'TerserPlugin') {
            return new TerserPlugin({
              terserOptions: {
                parse: {
                  ecma: 2020,
                },
                compress: {
                  ecma: 2015,
                  comparisons: false,
                  inline: 2,
                  drop_console: false, // Keep console.warn and console.error
                  drop_debugger: true,
                  pure_funcs: ['console.log', 'console.debug'], // Strip verbose logs in production
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
            });
          }
          return minimizer;
        });
      } else {
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
                drop_console: false, // Keep console.warn and console.error
                drop_debugger: true,
                pure_funcs: ['console.log', 'console.debug'], // Strip verbose logs in production
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
      }

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
