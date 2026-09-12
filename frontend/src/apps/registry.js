/**
 * Pluggable Modular App Registry
 * Allows any application to dynamically register into the Launchpad, TopBar, and Settings Hub.
 */

const appRegistry = new Map();

export function registerApp(manifest) {
  if (!manifest || !manifest.id) {
    throw new Error('Invalid app manifest: missing id');
  }
  appRegistry.set(manifest.id, {
    order: manifest.order || 100,
    ...manifest,
  });
}

export function getApp(id) {
  return appRegistry.get(id);
}

export function getAllApps(customOrder = []) {
  const apps = Array.from(appRegistry.values());
  if (!customOrder || customOrder.length === 0) {
    return apps.sort((a, b) => a.order - b.order);
  }

  // Sort according to custom user ordering
  return apps.sort((a, b) => {
    const idxA = customOrder.indexOf(a.id);
    const idxB = customOrder.indexOf(b.id);
    if (idxA === -1 && idxB === -1) return a.order - b.order;
    if (idxA === -1) return 1;
    if (idxB === -1) return -1;
    return idxA - idxB;
  });
}

export function getAppMenus(appId) {
  const app = appRegistry.get(appId);
  return app?.menus || [];
}
