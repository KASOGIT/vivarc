// Peek's AI summary feature is not used by Vivarc; these stubs keep the mod from throwing.
window.VividAI = {
  loadConfig: () => Promise.resolve({}),
  applyConfig: () => {},
  streamChat: () => Promise.reject(new Error("AI disabled")),
};
window.VividMarkdown = { render: (text) => text };
