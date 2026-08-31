package com.i4c.cybershield.ui.theme

import androidx.compose.ui.graphics.Color

// ─── Cyber Shield Official Color Palette ───────────────────────────────
// Design tokens sourced from Ministry of Home Affairs / I4C UI spec.

/** Main Background / TopBar / Bottom Navigation */
val BgDeepSlate        = Color(0xFF252422)

/** Card Fills / Dialog Surfaces / Text Fields */
val SurfaceCharcoal    = Color(0xFF403D39)

/** Borders / Muted Text / Inactive Indicators */
val BorderTaupe        = Color(0xFFCCC5B9)

/** Primary Headers / Main Text / Card Titles */
val TextOffWhite       = Color(0xFFFFFCF2)

/** Primary Action Buttons / Critical Risk Badges / Active Markers */
val AlertOrange        = Color(0xFFEB5E28)

/** Live Status Pulse / Approved Actions */
val SuccessGreen       = Color(0xFF38B000)

/** Medium Risk Indicators */
val MediumCyan         = Color(0xFF00E5FF)

// ─── Extended / Derived Palette ────────────────────────────────────────
val ErrorRed           = Color(0xFFD62828)
val WarningYellow      = Color(0xFFFFB703)
val InfoBlue           = Color(0xFF4CC9F0)
val OverlayBlack       = Color(0xCC000000)
val DividerDark        = Color(0xFF33312E)
val SurfaceElevated    = Color(0xFF4A4641)
val CriticalRed        = Color(0xFFFF006E)
val ChipSelectedBg     = AlertOrange.copy(alpha = 0.15f)
val ChipUnselectedBg   = SurfaceCharcoal
val DisabledGray       = Color(0xFF6B6560)
val LockdownOverlay    = AlertOrange.copy(alpha = 0.92f)
