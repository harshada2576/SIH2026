package com.i4c.cybershield.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

// ─── Dark Color Scheme ─────────────────────────────────────────────────
private val CyberShieldDarkScheme = darkColorScheme(
    primary            = AlertOrange,
    onPrimary          = TextOffWhite,
    primaryContainer   = AlertOrange.copy(alpha = 0.12f),
    onPrimaryContainer = AlertOrange,
    secondary          = MediumCyan,
    onSecondary        = BgDeepSlate,
    secondaryContainer = MediumCyan.copy(alpha = 0.12f),
    onSecondaryContainer = MediumCyan,
    tertiary           = SuccessGreen,
    onTertiary         = TextOffWhite,
    tertiaryContainer  = SuccessGreen.copy(alpha = 0.12f),
    onTertiaryContainer = SuccessGreen,
    background         = BgDeepSlate,
    onBackground       = TextOffWhite,
    surface            = SurfaceCharcoal,
    onSurface          = TextOffWhite,
    surfaceVariant     = SurfaceElevated,
    onSurfaceVariant   = BorderTaupe,
    outline            = BorderTaupe,
    outlineVariant     = DividerDark,
    error              = ErrorRed,
    onError            = TextOffWhite,
    errorContainer     = ErrorRed.copy(alpha = 0.12f),
    onErrorContainer   = ErrorRed,
    inverseSurface     = TextOffWhite,
    inverseOnSurface   = BgDeepSlate,
    inversePrimary     = AlertOrange,
    scrim              = OverlayBlack,
)

// ─── Typography ────────────────────────────────────────────────────────
val CyberShieldTypography = Typography(
    displayLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Bold,
        fontSize = 32.sp,
        lineHeight = 40.sp,
        color = TextOffWhite
    ),
    headlineLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Bold,
        fontSize = 24.sp,
        lineHeight = 32.sp,
        color = TextOffWhite
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 20.sp,
        lineHeight = 28.sp,
        color = TextOffWhite
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        lineHeight = 26.sp,
        color = TextOffWhite
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 16.sp,
        lineHeight = 24.sp,
        color = TextOffWhite
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
        color = TextOffWhite
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp,
        color = BorderTaupe
    ),
    bodySmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        color = BorderTaupe
    ),
    labelLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Bold,
        fontSize = 14.sp,
        lineHeight = 20.sp,
        color = TextOffWhite
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        color = TextOffWhite
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 10.sp,
        lineHeight = 14.sp,
        color = BorderTaupe
    )
)

// ─── Theme Composable ──────────────────────────────────────────────────
@Composable
fun CyberShieldTheme(
    content: @Composable () -> Unit
) {
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = BgDeepSlate.toArgb()
            window.navigationBarColor = BgDeepSlate.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = false
        }
    }

    MaterialTheme(
        colorScheme = CyberShieldDarkScheme,
        typography = CyberShieldTypography,
        content = content
    )
}
