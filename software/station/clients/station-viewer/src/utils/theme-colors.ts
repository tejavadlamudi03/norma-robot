import * as THREE from 'three';
import type { Theme } from '@/hooks/useTheme';

export interface RendererThemeColors {
  sceneBackground: THREE.Color;
  gridPrimary: THREE.Color;
  gridSecondary: THREE.Color;
}

export interface CanvasThemeColors {
  canvasFill: string;
  canvasBlue: string;
  canvasRed: string;
  canvasWhite: string;
}

export function getRendererThemeColors(theme: Theme): RendererThemeColors {
  if (theme === 'light') {
    return {
      sceneBackground: new THREE.Color('#f1f5f9'),
      gridPrimary: new THREE.Color('#94a3b8'),
      gridSecondary: new THREE.Color('#cbd5e1'),
    };
  }

  return {
    sceneBackground: new THREE.Color('#303030'),
    gridPrimary: new THREE.Color('#6b7280'),
    gridSecondary: new THREE.Color('#4b5563'),
  };
}

export function getCanvasThemeColors(theme: Theme): CanvasThemeColors {
  if (theme === 'light') {
    return {
      canvasFill: '#d1d5db',
      canvasBlue: '#2563eb',
      canvasRed: '#dc2626',
      canvasWhite: '#0f172a',
    };
  }

  return {
    canvasFill: '#404040',
    canvasBlue: '#3B82F6',
    canvasRed: '#EF4444',
    canvasWhite: '#FFFFFF',
  };
}
