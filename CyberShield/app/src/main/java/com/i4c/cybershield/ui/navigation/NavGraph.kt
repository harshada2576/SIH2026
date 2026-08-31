package com.i4c.cybershield.ui.navigation

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.i4c.cybershield.MainViewModel
import com.i4c.cybershield.ui.auth.AuthScreen
import com.i4c.cybershield.ui.screens.MainScreen

// ═══════════════════════════════════════════════════════════════════════
//  NAVIGATION GRAPH
//  Two top-level destinations:
//    • "auth"      → Auth & Registration
//    • "main"      → 3-Tab Scaffold (Radar / Investigation / Dispatch)
// ═══════════════════════════════════════════════════════════════════════

object Routes {
    const val AUTH = "auth"
    const val MAIN = "main"
}

@Composable
fun CyberShieldNavGraph(
    navController: NavHostController,
    viewModel: MainViewModel = viewModel()
) {
    NavHost(
        navController = navController,
        startDestination = Routes.AUTH,
        enterTransition = {
            fadeIn(animationSpec = tween(300)) + slideInHorizontally(
                initialOffsetX = { it / 3 },
                animationSpec = tween(300)
            )
        },
        exitTransition = {
            fadeOut(animationSpec = tween(300))
        },
        popEnterTransition = {
            fadeIn(animationSpec = tween(300)) + slideInHorizontally(
                initialOffsetX = { -it / 3 },
                animationSpec = tween(300)
            )
        },
        popExitTransition = {
            fadeOut(animationSpec = tween(300))
        }
    ) {
        // ─── Auth Screen ───────────────────────────────────────────
        composable(Routes.AUTH) {
            AuthScreen(
                email = viewModel.email,
                emailError = viewModel.emailError,
                otpInput = viewModel.otpInput,
                otpError = viewModel.otpError,
                otpRequested = viewModel.otpRequested,
                failedAttempts = viewModel.failedAttempts,
                isLocked = viewModel.isLocked,
                lockoutTimeRemaining = viewModel.lockoutTimeRemaining,
                otpCountdownSeconds = viewModel.otpCountdownSeconds,
                canResendOtp = viewModel.canResendOtp,
                onEmailChanged = viewModel::onEmailChanged,
                onOtpChanged = viewModel::onOtpChanged,
                onRequestOtp = viewModel::requestOtp,
                onVerifyOtp = {
                    viewModel.verifyOtp()
                    // Navigate to main on successful auth
                    if (viewModel.isAuthenticated) {
                        navController.navigate(Routes.MAIN) {
                            popUpTo(Routes.AUTH) { inclusive = true }
                        }
                    }
                },
                onResendOtp = viewModel::resendOtp
            )
        }

        // ─── Main 3-Tab Scaffold ───────────────────────────────────
        composable(Routes.MAIN) {
            MainScreen(viewModel = viewModel)
        }
    }
}
