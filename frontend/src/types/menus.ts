/**
 * Hierarchical Navigation Menu Types matching backend `MenuItemNode`.
 */

export type MenuActionType = 'folder' | 'window' | 'report' | 'settings' | 'url' | 'client';
export type MenuViewType = 'list' | 'kanban' | 'form' | 'report' | 'pivot' | 'dashboard';

export interface MenuItemNode {
  id: string;
  name: string;             // Human-readable label (e.g. "Sales", "Quotations")
  code: string;             // Unique identifier (e.g. "sales.root", "sales.quotations")
  parent_id?: string | null;
  sequence: number;
  icon?: string | null;     // Lucide icon name
  module_name: string;      // "sales", "accounting", "purchases", "settings"
  res_model?: string | null;// "SaleOrder", "AccountMove", "Product", etc.
  action_type: MenuActionType;
  default_view: MenuViewType;
  route_path?: string | null;
  domain_filter?: Record<string, any> | null;
  target_role_ids?: string[] | null;
  company_id?: string | null;
  is_system: boolean;
  is_active: boolean;
  children: MenuItemNode[];
}
