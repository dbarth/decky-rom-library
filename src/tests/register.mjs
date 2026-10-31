// Lets Node's test runner load the frontend: node --import ./src/tests/register.mjs --test src/tests/*.test.tsx
import { register } from "node:module";

register("./loader.mjs", import.meta.url);
