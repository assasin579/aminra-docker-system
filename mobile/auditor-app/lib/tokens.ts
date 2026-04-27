/**
 * Design tokens — mirror frontend/aminra-web brand identity.
 * Single source of truth for colors, spacing, typography across the app.
 */
export const colors = {
  // Primary = Navy (rebrand 2026-04-26)
  primary:       '#0F2C4A',
  primaryDeep:   '#0A1F35',
  primaryLight:  'rgba(15,44,74,0.08)',
  primaryBorder: 'rgba(15,44,74,0.2)',

  // Accent = Royal Gold (sparingly: cert seal, premium CTAs)
  accent:        '#C9A227',
  accentLight:   '#FAF3D8',
  accentDeep:    '#A8861E',

  text:          '#0F2C4A',
  textMuted:     '#5F6F80',
  textSubtle:    '#94A3B8',

  surface:       '#FFFFFF',
  background:    '#FAFAF7',
  border:        '#E2E8F0',

  warning:       '#D97706',
  warningBg:     '#FEF3C7',
  danger:        '#DC2626',
  dangerBg:      '#FEF2F2',
  success:       '#10B981',
  successBg:     '#ECFDF5',
  info:          '#2563EB',
  infoBg:        '#DBEAFE',
} as const;

export const spacing = {
  xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, xxxl: 32,
} as const;

export const radii = {
  sm: 6, md: 8, lg: 12, xl: 16, full: 999,
} as const;

export const fontSize = {
  xs: 11, sm: 13, base: 15, md: 17, lg: 19, xl: 24, xxl: 32,
} as const;

export const fontWeight = {
  regular: '400', medium: '500', semibold: '600', bold: '700', black: '900',
} as const;
