// Copies the frontend library files Cortex actually uses out of node_modules
// into templates/static/vendor, so pages load them locally instead of via CDN.
import { existsSync, mkdirSync, copyFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const NODE_MODULES = join(ROOT, "node_modules");
const VENDOR_DIR = join(ROOT, "templates", "static", "vendor");

function copyFile(src, destDir, destName) {
    mkdirSync(destDir, { recursive: true });
    copyFileSync(src, join(destDir, destName ?? src.split(/[\\/]/).pop()));
}

function copyDir(srcDir, destDir) {
    mkdirSync(destDir, { recursive: true });
    for (const entry of readdirSync(srcDir, { withFileTypes: true })) {
        if (entry.isFile()) {
            copyFileSync(join(srcDir, entry.name), join(destDir, entry.name));
        }
    }
}

// Chart.js UMD bundle
copyFile(
    join(NODE_MODULES, "chart.js", "dist", "chart.umd.js"),
    join(VENDOR_DIR, "chartjs")
);

// Font Awesome Free: CSS + webfonts (kept as siblings so the CSS's relative ../webfonts/ URLs still resolve)
copyFile(
    join(NODE_MODULES, "@fortawesome", "fontawesome-free", "css", "all.min.css"),
    join(VENDOR_DIR, "fontawesome", "css")
);
copyDir(
    join(NODE_MODULES, "@fortawesome", "fontawesome-free", "webfonts"),
    join(VENDOR_DIR, "fontawesome", "webfonts")
);

if (!existsSync(VENDOR_DIR)) {
    throw new Error("Vendor directory was not created — check node_modules install.");
}

console.log("[vendor] Font Awesome + Chart.js copied into templates/static/vendor");
