// Pure CJS — so __dirname is defined (ESM `import` makes it undefined in Next config)
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactCompiler: true,
  turbopack: {
    // Pin Turbopack's root to this directory.  Without this, Turbopack walks
    // up from frontend/ to the repo root and finds C:\Users\ASUS\package.json,
    // which triggers a full monorepo scan that OOMs on Windows.
    root: __dirname,
  },
};

module.exports = nextConfig;
