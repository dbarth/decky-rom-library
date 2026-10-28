import deckyPlugin from "@decky/rollup";

// @decky/rollup lets its own input win over ours.
export default { ...deckyPlugin({}, "src/backend"), input: "./src/frontend/index.tsx" };
