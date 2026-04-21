import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import './api/websocket.ts'
import { applyTheme, resolveTheme, ThemeProvider } from './hooks/useTheme'

applyTheme(resolveTheme());

createRoot(document.getElementById('root')!).render(
  <ThemeProvider>
    <App />
  </ThemeProvider>
)
