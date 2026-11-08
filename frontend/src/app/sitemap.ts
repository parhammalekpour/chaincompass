import type { MetadataRoute } from "next";

const publicPaths = ["/", "/login", "/register", "/methodology", "/learn", "/legal"];
const baseUrl = process.env.APP_BASE_URL ?? "http://localhost:3000";

export default function sitemap(): MetadataRoute.Sitemap {
  return publicPaths.flatMap((pathname) => {
    const localizedPath = pathname === "/" ? "" : pathname;
    const enUrl = new URL(`/en${localizedPath}`, baseUrl).toString();
    const faUrl = new URL(`/fa${localizedPath}`, baseUrl).toString();

    return [
      {
        url: enUrl,
        alternates: {
          languages: { en: enUrl, fa: faUrl, "x-default": enUrl },
        },
      },
      {
        url: faUrl,
        alternates: {
          languages: { en: enUrl, fa: faUrl, "x-default": enUrl },
        },
      },
    ];
  });
}
