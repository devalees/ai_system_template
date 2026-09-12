import { registerApp } from './registry';
import aiStudioApp from './ai_studio/manifest';
import clientsApp from './clients/manifest';
import tasksApp from './tasks/manifest';
import settingsApp from './settings/manifest';

/**
 * Bootstrap and register all modular applications into the platform.
 * To add a new domain app in the future (e.g. Accounting, CRM), simply
 * import its manifest and call registerApp(newApp) here!
 */
export function initializeApps() {
  registerApp(aiStudioApp);
  registerApp(clientsApp);
  registerApp(tasksApp);
  registerApp(settingsApp);
}
