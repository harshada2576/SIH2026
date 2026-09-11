package com.i4c.cybershield.ui.navigation

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.i4c.cybershield.MainViewModel
import com.i4c.cybershield.ui.auth.AuthScreen
import com.i4c.cybershield.ui.investigation.CaseDetailScreen
import com.i4c.cybershield.ui.screens.MainScreen
import com.i4c.cybershield.ui.theme.BorderTaupe

// ═══════════════════════════════════════════════════════════════════════
//  NAVIGATION GRAPH
//  Three top-level destinations:
//    • "auth"                  → Auth & Registration
//    • "main"                  → 3-Tab Scaffold (Map / Cases / Activity)
//    • "case_detail/{ncrpId}"  → Full inspection of ONE specific case,
//                                pushed on top with its own back arrow —
//                                reached from the Cases queue or a Map
//                                marker, always showing the case that was
//                                actually tapped.
// ═══════════════════════════════════════════════════════════════════════

object Routes {
    const val AUTH = "auth"
    const val MAIN = "main"
    const val CASE_DETAIL = "case_detail/{ncrpId}"
    fun caseDetail(ncrpId: String) = "case_detail/$ncrpId"
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
            MainScreen(
                viewModel = viewModel,
                onOpenCase = { ncrpId -> navController.navigate(Routes.caseDetail(ncrpId)) }
            )
        }

        // ─── Case Detail (always the case that was actually tapped) ─
        composable(
            route = Routes.CASE_DETAIL,
            arguments = listOf(navArgument("ncrpId") { type = NavType.StringType })
        ) { backStackEntry ->
            val ncrpId = backStackEntry.arguments?.getString("ncrpId").orEmpty()
            val case = viewModel.caseById(ncrpId)

            if (case == null) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Case $ncrpId not found.", color = BorderTaupe)
                }
            } else {
                CaseDetailScreen(
                    case = case,
                    showApproveDialog = viewModel.showApproveDialog,
                    showBankHoldDialog = viewModel.showBankHoldDialog,
                    onBack = { navController.popBackStack() },
                    onApproveClick = viewModel::showApproveConfirmation,
                    onApproveConfirm = {
                        viewModel.approveAndForward(ncrpId)
                        navController.popBackStack()
                    },
                    onApproveDismiss = viewModel::dismissApproveDialog,
                    onBankHoldClick = viewModel::showBankHoldConfirmation,
                    onBankHoldConfirm = {
                        viewModel.issueBankHold(ncrpId)
                        navController.popBackStack()
                    },
                    onBankHoldDismiss = viewModel::dismissBankHoldDialog,
                    onDismissFalsePositive = {
                        viewModel.dismissFalsePositive(ncrpId)
                        navController.popBackStack()
                    }
                )
            }
        }
    }
}
