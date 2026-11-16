(() => {
  const backgrounds = {
    light: "#f6f8fb",
    dark: "#111315",
    warm: "#f4ede2",
    ocean: "#edf4f7",
    forest: "#eef2ed",
    lavender: "#f2f0f5"
  };
  let selected = "light";
  try {
    const saved = localStorage.getItem("dgu.theme");
    if (saved && backgrounds[saved]) selected = saved;
  } catch {}
  document.documentElement.dataset.theme = selected;
  document.documentElement.style.backgroundColor = backgrounds[selected];
  try {
    const storedLocale = localStorage.getItem("dgu.locale");
    document.documentElement.lang = storedLocale === "ru" || storedLocale === "en"
      ? storedLocale
      : (navigator.language || "en").toLowerCase().startsWith("ru") ? "ru" : "en";
  } catch {
    document.documentElement.lang = "ru";
  }
})();
