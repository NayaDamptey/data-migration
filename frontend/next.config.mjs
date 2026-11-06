/** @type {import('next').NextConfig} */
export default {
  // Hide the "N" dev-tools badge in the corner during `next dev`.
  devIndicators: false,
  // A separate build folder (e.g. NEXT_DIST_DIR=.next-demo) lets a demo build run beside `next dev`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};
