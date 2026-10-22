// Optional: open links from other apps in the right Vivaldi profile with Finicky (https://github.com/johnste/finicky).
// Copy to ~/.finicky.js, install with `brew install --cask finicky`, then set Finicky as the default browser.
// Profiles are matched by the display name shown in Vivaldi's profile menu.
export default {
  defaultBrowser: { name: "Vivaldi", profile: "Personal" },
  handlers: [
    {
      match: ["*.notion.so/*", "*.figma.com/*", "*.atlassian.net/*"],
      browser: { name: "Vivaldi", profile: "Work" },
    },
  ],
};
