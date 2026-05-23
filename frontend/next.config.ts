import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  webpack: (config) => {
    // react-pdf requires canvas in Node.js environments; alias it away in the browser bundle
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    return config;
  },
};

export default nextConfig;
