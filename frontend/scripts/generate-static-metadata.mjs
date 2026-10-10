import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(scriptDir, "../public");
const deployedHost = process.env.VERCEL_PROJECT_PRODUCTION_URL || process.env.VERCEL_URL;
const configured = process.env.VITE_SITE_URL || process.env.SITE_URL || deployedHost || "http://127.0.0.1:5173";
const siteUrl = (/^https?:\/\//.test(configured) ? configured : `https://${configured}`).replace(/\/$/, "");

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${siteUrl}/</loc></url>
  <url><loc>${siteUrl}/privacy</loc></url>
  <url><loc>${siteUrl}/terms</loc></url>
</urlset>
`;

const robots = `User-agent: *
Allow: /
Disallow: /watchlist
Disallow: /live-review
Disallow: /governance
Disallow: /data-sync
Sitemap: ${siteUrl}/sitemap.xml
`;

await mkdir(publicDir, { recursive: true });
await Promise.all([
  writeFile(path.join(publicDir, "sitemap.xml"), sitemap, "utf8"),
  writeFile(path.join(publicDir, "robots.txt"), robots, "utf8"),
]);
console.log(`Generated metadata for ${siteUrl}`);
