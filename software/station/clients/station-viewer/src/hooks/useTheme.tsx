import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useState, useCallback, type ReactNode } from 'react';

export type Theme = 'dark' | 'light';
export type ThemePreference = 'auto' | Theme;

interface ThemeContextValue {
  theme: Theme;
  themePreference: ThemePreference;
  setThemePreference: (themePreference: ThemePreference) => void;
}

const STORAGE_KEY = 'theme';
const LIGHT_MEDIA_QUERY = '(prefers-color-scheme: light)';

function getSystemTheme(): Theme {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia(LIGHT_MEDIA_QUERY).matches ? 'light' : 'dark';
}

export function resolveThemePreference(): ThemePreference {
  if (typeof window === 'undefined') return 'auto';

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'auto' || stored === 'light' || stored === 'dark') {
    return stored;
  }

  return 'auto';
}

export function resolveTheme(themePreference: ThemePreference = resolveThemePreference()): Theme {
  if (themePreference === 'auto') {
    return getSystemTheme();
  }

  return themePreference;
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>(resolveThemePreference);
  const [systemTheme, setSystemTheme] = useState<Theme>(getSystemTheme);

  useEffect(() => {
    const mediaQuery = window.matchMedia(LIGHT_MEDIA_QUERY);
    const handleChange = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? 'light' : 'dark');
    };

    setSystemTheme(mediaQuery.matches ? 'light' : 'dark');
    mediaQuery.addEventListener('change', handleChange);

    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, []);

  const theme = useMemo<Theme>(() => {
    return themePreference === 'auto' ? systemTheme : themePreference;
  }, [systemTheme, themePreference]);

  useLayoutEffect(() => {
    applyTheme(theme);
    window.localStorage.setItem(STORAGE_KEY, themePreference);
  }, [theme, themePreference]);

  const setThemePreference = useCallback((nextThemePreference: ThemePreference) => {
    setThemePreferenceState(nextThemePreference);
  }, []);

  const value = useMemo<ThemeContextValue>(() => ({
    theme,
    themePreference,
    setThemePreference
  }), [theme, themePreference, setThemePreference]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
