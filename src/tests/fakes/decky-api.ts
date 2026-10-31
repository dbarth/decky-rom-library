// The parts of @decky/api the game page loads. A backend call never answers.
export const callable = () => () => new Promise(() => undefined);
export const toaster = { toast: () => undefined };
export const openFilePicker = () => new Promise(() => undefined);
