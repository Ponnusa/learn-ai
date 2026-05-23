import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Prevent Next.js from trying to bundle the native `canvas` module
  // that pdfjs-dist optionally requires in Node.js environments.
  serverExternalPackages: ['canvas'],

  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    return config;
  },
};

export default nextConfig;
