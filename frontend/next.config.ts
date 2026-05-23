import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Force SWC to transpile react-pdf and pdfjs-dist.
  // pdfjs-dist v5 ships as pure ESM ("type":"module") which webpack's
  // worker threads cannot process without transpilation — without this
  // the build crashes with "Call retries were exceeded / WorkerError".
  transpilePackages: ['react-pdf', 'pdfjs-dist'],

  webpack: (config) => {
    // pdfjs-dist optionally requires the `canvas` native module in Node.js;
    // alias it to false so webpack doesn't try (and fail) to bundle it.
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    return config;
  },
};

export default nextConfig;
