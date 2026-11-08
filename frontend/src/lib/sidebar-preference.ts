const STORAGE_KEY = "chaincompass.sidebar.collapsed";
const subscribers = new Set<() => void>();

export function getSidebarCollapsed() {
  return window.localStorage.getItem(STORAGE_KEY) === "true";
}

export function subscribeSidebarPreference(onChange: () => void) {
  subscribers.add(onChange);
  return () => subscribers.delete(onChange);
}

export function setSidebarCollapsed(collapsed: boolean) {
  window.localStorage.setItem(STORAGE_KEY, String(collapsed));
  subscribers.forEach((subscriber) => subscriber());
}
