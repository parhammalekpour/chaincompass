import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const sourceRoot = fileURLToPath(new URL("../src/", import.meta.url));
const sourceExtensions = new Set([".ts", ".tsx", ".js", ".jsx"]);
const physicalClassPattern =
  /(?:^|[\s"'`])(?:[a-z-]+:)*-?(?:ml|mr|pl|pr)-[^\s"'`]+|(?:^|[\s"'`])(?:[a-z-]+:)*-?(?:left|right)-[^\s"'`]+|(?:^|[\s"'`])(?:[a-z-]+:)*text-(?:left|right)(?=$|[\s"'`])/g;

async function findFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await findFiles(path)));
    } else if (sourceExtensions.has(path.slice(path.lastIndexOf(".")))) {
      files.push(path);
    }
  }

  return files;
}

const files = await findFiles(sourceRoot);
const violations = [];

for (const file of files) {
  const content = await readFile(file, "utf8");
  for (const match of content.matchAll(physicalClassPattern)) {
    const line = content.slice(0, match.index).split("\n").length;
    violations.push(
      `${relative(sourceRoot, file)}:${line}: ${match[0].trim()}`,
    );
  }
}

if (violations.length > 0) {
  console.error("Physical-direction Tailwind classes found under src/:");
  console.error(violations.join("\n"));
  process.exitCode = 1;
} else {
  console.log("Logical Tailwind class check passed.");
}
