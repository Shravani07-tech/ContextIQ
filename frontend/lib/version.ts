// Single source of truth for the app version shown in the UI.
// Keep this in sync with the "version" field in package.json — the
// status bar reads it from here rather than hardcoding its own copy
// (which previously drifted to a stale, incorrect value).
export const APP_VERSION = "1.0.0";
