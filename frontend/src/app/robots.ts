import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.APP_BASE_URL ?? "http://localhost:3000";

  return {
    rules: {
      userAgent: "*",
      disallow: [
        "/api",
        "/app",
        "/admin",
        "/en/app",
        "/fa/app",
        "/en/admin",
        "/fa/admin",
      ],
    },
    sitemap: new URL("/sitemap.xml", baseUrl).toString(),
  };
}
