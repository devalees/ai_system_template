import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Hide static splash loader smoothly upon React mount
const splash = document.getElementById('splash-loader');
if (splash) {
  splash.style.opacity = '0';
  setTimeout(() => splash.remove(), 300);
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
