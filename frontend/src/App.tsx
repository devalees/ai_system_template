import React from 'react';
import { UIThemeProvider } from './kernel/theme/ThemeContext';
import { CompanyProvider } from './kernel/company/CompanyContext';
import { AuthProvider } from './kernel/auth/AuthContext';
import { MasterShell } from './ui/layout/MasterShell';

export const App: React.FC = () => {
  return (
    <UIThemeProvider>
      <CompanyProvider>
        <AuthProvider>
          <MasterShell />
        </AuthProvider>
      </CompanyProvider>
    </UIThemeProvider>
  );
};

export default App;
