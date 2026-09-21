import type { MetadataRoute } from "next";

// Installing Scholr on her phone (docs/STUDENT-APP.md D6). `standalone` opens it without browser chrome, so it
// behaves like an app; it is still the same site, served from the home machine.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Scholr — Personal AI Learning OS",
    short_name: "Scholr",
    description: "Cambridge IGCSE and IIT Foundation study space.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#FDFAF5",
    theme_color: "#f97316",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
