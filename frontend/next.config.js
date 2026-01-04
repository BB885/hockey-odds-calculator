/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "assets.nhle.com" },
    ],
  },
};

module.exports = nextConfig;
