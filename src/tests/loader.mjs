// Transpiles the frontend's TypeScript and TSX for Node, and swaps Decky's packages for the fakes in
// fakes/: the real ones read Steam's React and modules from the window.
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const FAKES = { "@decky/ui": "./fakes/decky-ui.tsx", "@decky/api": "./fakes/decky-api.ts" };

export async function resolve(specifier, context, next) {
  if (FAKES[specifier]) return { url: new URL(FAKES[specifier], import.meta.url).href, shortCircuit: true };
  // The frontend imports its modules without an extension, as rollup resolves them.
  if (specifier.startsWith(".") && /\.tsx?$/.test(context.parentURL ?? "")) {
    for (const ext of [".ts", ".tsx"]) {
      const url = new URL(specifier + ext, context.parentURL);
      if (existsSync(fileURLToPath(url))) return { url: url.href, shortCircuit: true };
    }
  }
  return next(specifier, context);
}

export async function load(url, context, next) {
  if (!/\.tsx?$/.test(url)) return next(url, context);
  const file = fileURLToPath(url);
  const { outputText } = ts.transpileModule(await readFile(file, "utf8"), {
    fileName: file,
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  });
  return { format: "module", source: outputText, shortCircuit: true };
}
