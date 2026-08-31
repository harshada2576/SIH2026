package com.i4c.cybershield.ui.auth

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  AUTH SCREEN – Domain-Restricted Registration & OTP
// ═══════════════════════════════════════════════════════════════════════

@Composable
fun AuthScreen(
    email: String,
    emailError: String?,
    otpInput: String,
    otpError: String?,
    otpRequested: Boolean,
    failedAttempts: Int,
    isLocked: Boolean,
    lockoutTimeRemaining: String,
    otpCountdownSeconds: Int,
    canResendOtp: Boolean,
    onEmailChanged: (String) -> Unit,
    onOtpChanged: (String) -> Unit,
    onRequestOtp: () -> Unit,
    onVerifyOtp: () -> Unit,
    onResendOtp: () -> Unit
) {
    val focusManager = LocalFocusManager.current

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(BgDeepSlate, SurfaceCharcoal.copy(alpha = 0.6f), BgDeepSlate)
                )
            )
    ) {
        // ─── Lockdown Overlay ──────────────────────────────────────
        AnimatedVisibility(
            visible = isLocked,
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically()
        ) {
            LockdownCard(lockoutTimeRemaining = lockoutTimeRemaining)
        }

        // ─── Main Auth Content ─────────────────────────────────────
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .alpha(if (isLocked) 0.15f else 1f),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Header
            AuthHeader()

            Spacer(modifier = Modifier.height(48.dp))

            // Email Input
            EmailInputField(
                email = email,
                emailError = emailError,
                onEmailChanged = onEmailChanged,
                enabled = !isLocked,
                onSubmit = { onRequestOtp() }
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Request OTP Button
            AnimatedVisibility(visible = !otpRequested && !isLocked) {
                Button(
                    onClick = onRequestOtp,
                    enabled = email.isNotBlank() && !isLocked,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = AlertOrange,
                        contentColor = TextOffWhite
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.Security,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "SEND SECURE OTP",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }

            // OTP Section
            AnimatedVisibility(
                visible = otpRequested && !isLocked,
                enter = fadeIn() + expandVertically(),
                exit = fadeOut() + shrinkVertically()
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Spacer(modifier = Modifier.height(8.dp))

                    // OTP Info Banner
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = SuccessGreen.copy(alpha = 0.12f)
                        ),
                        border = CardDefaults.outlinedCardBorder().copy(
                            brush = Brush.linearGradient(
                                colors = listOf(
                                    SuccessGreen.copy(alpha = 0.4f),
                                    SuccessGreen.copy(alpha = 0.1f)
                                )
                            )
                        )
                    ) {
                        Text(
                            text = "OTP sent to $email\nDemo OTP: 123456",
                            modifier = Modifier.padding(12.dp),
                            color = SuccessGreen,
                            fontSize = 13.sp,
                            lineHeight = 18.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // OTP Input Field
                    OtpInputField(
                        otpValue = otpInput,
                        otpError = otpError,
                        onOtpChanged = onOtpChanged,
                        enabled = !isLocked,
                        onSubmit = {
                            focusManager.clearFocus()
                            onVerifyOtp()
                        }
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    // Countdown / Resend
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        if (!canResendOtp) {
                            Text(
                                text = "Resend OTP in ${otpCountdownSeconds}s",
                                color = BorderTaupe,
                                fontSize = 13.sp
                            )
                        } else {
                            TextButton(onClick = onResendOtp) {
                                Text(
                                    text = "Resend OTP",
                                    color = AlertOrange,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }

                        if (otpError != null) {
                            Text(
                                text = "Attempts: $failedAttempts/5",
                                color = if (failedAttempts >= 3) AlertOrange else ErrorRed,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    // Verify OTP Button
                    Button(
                        onClick = {
                            focusManager.clearFocus()
                            onVerifyOtp()
                        },
                        enabled = otpInput.length == 6 && !isLocked,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = AlertOrange,
                            contentColor = TextOffWhite,
                            disabledContainerColor = DisabledGray,
                            disabledContentColor = BorderTaupe
                        )
                    ) {
                        Icon(
                            imageVector = Icons.Default.VerifiedUser,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "VERIFY & LOGIN",
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                    }
                }
            }
        }
    }
}

// ─── Sub-Components ────────────────────────────────────────────────────

@Composable
private fun AuthHeader() {
    // Animated shield emblem
    val infiniteTransition = rememberInfiniteTransition(label = "shield_pulse")
    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.6f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow"
    )

    Column(
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Shield Emblem Placeholder
        Box(
            modifier = Modifier
                .size(96.dp)
                .clip(CircleShape)
                .background(SurfaceCharcoal)
                .border(2.dp, AlertOrange.copy(alpha = glowAlpha), CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Security,
                contentDescription = "MHA / I4C Emblem",
                tint = AlertOrange.copy(alpha = glowAlpha),
                modifier = Modifier.size(48.dp)
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Title
        Text(
            text = "CYBER SHIELD",
            fontSize = 28.sp,
            fontWeight = FontWeight.Black,
            color = TextOffWhite,
            letterSpacing = 4.sp
        )

        Spacer(modifier = Modifier.height(4.dp))

        // Subtitle
        Text(
            text = "Predictive Cashout Radar",
            fontSize = 14.sp,
            color = AlertOrange,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 2.sp
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Badge
        Card(
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(
                containerColor = SurfaceCharcoal
            ),
            border = CardDefaults.outlinedCardBorder().copy(
                brush = Brush.linearGradient(
                    colors = listOf(BorderTaupe.copy(alpha = 0.4f), BorderTaupe.copy(alpha = 0.1f))
                )
            )
        ) {
            Text(
                text = "Authorized Personnel Login Only",
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
                color = BorderTaupe,
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium,
                letterSpacing = 1.sp
            )
        }

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = "Ministry of Home Affairs • I4C Cybercrime Defense",
            fontSize = 10.sp,
            color = BorderTaupe.copy(alpha = 0.7f),
            letterSpacing = 0.5.sp
        )
    }
}

@Composable
private fun EmailInputField(
    email: String,
    emailError: String?,
    onEmailChanged: (String) -> Unit,
    enabled: Boolean,
    onSubmit: () -> Unit
) {
    val focusManager = LocalFocusManager.current

    Column(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = email,
            onValueChange = onEmailChanged,
            modifier = Modifier.fillMaxWidth(),
            enabled = enabled,
            label = { Text("Official Email Address", color = BorderTaupe) },
            placeholder = { Text("name@police.gov.in", color = BorderTaupe.copy(alpha = 0.5f)) },
            singleLine = true,
            isError = emailError != null,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = AlertOrange,
                unfocusedBorderColor = BorderTaupe.copy(alpha = 0.5f),
                errorBorderColor = ErrorRed,
                focusedTextColor = TextOffWhite,
                unfocusedTextColor = TextOffWhite,
                cursorColor = AlertOrange,
                focusedLabelColor = AlertOrange,
                errorLabelColor = ErrorRed
            ),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = {
                    focusManager.clearFocus()
                    onSubmit()
                }
            )
        )

        // Error Banner
        AnimatedVisibility(
            visible = emailError != null,
            enter = expandVertically() + fadeIn(),
            exit = shrinkVertically() + fadeOut()
        ) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                shape = RoundedCornerShape(8.dp),
                colors = CardDefaults.cardColors(
                    containerColor = ErrorRed.copy(alpha = 0.15f)
                ),
                border = CardDefaults.outlinedCardBorder().copy(
                    brush = Brush.linearGradient(
                        colors = listOf(ErrorRed.copy(alpha = 0.6f), ErrorRed.copy(alpha = 0.2f))
                    )
                )
            ) {
                Text(
                    text = emailError ?: "",
                    modifier = Modifier.padding(12.dp),
                    color = ErrorRed,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    lineHeight = 17.sp
                )
            }
        }

        // Domain hint
        Text(
            text = "Allowed: @police.gov.in | @gov.in | @rbi.org.in",
            modifier = Modifier.padding(top = 6.dp),
            fontSize = 10.sp,
            color = BorderTaupe.copy(alpha = 0.6f)
        )
    }
}

@Composable
private fun OtpInputField(
    otpValue: String,
    otpError: String?,
    onOtpChanged: (String) -> Unit,
    enabled: Boolean,
    onSubmit: () -> Unit
) {
    val focusManager = LocalFocusManager.current

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Enter 6-Digit OTP",
            color = BorderTaupe,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 8.dp),
            textAlign = TextAlign.Start
        )

        // Individual digit boxes
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Show 6 individual boxes
            repeat(6) { index ->
                val digit = otpValue.getOrNull(index)?.toString() ?: ""
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .aspectRatio(0.7f)
                        .clip(RoundedCornerShape(10.dp))
                        .background(SurfaceCharcoal)
                        .border(
                            width = if (index == otpValue.length) 2.dp else 1.dp,
                            color = when {
                                otpError != null -> ErrorRed
                                index == otpValue.length -> AlertOrange
                                digit.isNotEmpty() -> AlertOrange.copy(alpha = 0.5f)
                                else -> BorderTaupe.copy(alpha = 0.3f)
                            },
                            shape = RoundedCornerShape(10.dp)
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = digit,
                        fontSize = 24.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextOffWhite,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        // Hidden text field for actual input capture
        OutlinedTextField(
            value = otpValue,
            onValueChange = onOtpChanged,
            modifier = Modifier
                .fillMaxWidth()
                .height(0.dp)
                .alpha(0f),
            enabled = enabled,
            singleLine = true,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Number,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = {
                    focusManager.clearFocus()
                    onSubmit()
                }
            )
        )

        // OTP Error
        AnimatedVisibility(visible = otpError != null) {
            Text(
                text = otpError ?: "",
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                color = ErrorRed,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Start
            )
        }
    }
}

@Composable
private fun LockdownCard(lockoutTimeRemaining: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth(0.9f)
                .padding(24.dp),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(
                containerColor = BgDeepSlate
            ),
            border = CardDefaults.outlinedCardBorder().copy(
                brush = Brush.linearGradient(
                    colors = listOf(AlertOrange, AlertOrange.copy(alpha = 0.3f))
                )
            )
        ) {
            Column(
                modifier = Modifier.padding(28.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Lock icon
                Box(
                    modifier = Modifier
                        .size(72.dp)
                        .clip(CircleShape)
                        .background(AlertOrange.copy(alpha = 0.15f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Lock,
                        contentDescription = "Locked",
                        tint = AlertOrange,
                        modifier = Modifier.size(36.dp)
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                Text(
                    text = "ACCOUNT FROZEN",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Black,
                    color = AlertOrange,
                    letterSpacing = 2.sp
                )

                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = "5 Consecutive Failed Security Attempts",
                    fontSize = 14.sp,
                    color = TextOffWhite,
                    fontWeight = FontWeight.Medium,
                    textAlign = TextAlign.Center
                )

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "48-Hour System Lockdown Activated",
                    fontSize = 16.sp,
                    color = AlertOrange,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center
                )

                Spacer(modifier = Modifier.height(20.dp))

                // Countdown display
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = SurfaceCharcoal
                    )
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "TIME REMAINING",
                            fontSize = 10.sp,
                            color = BorderTaupe,
                            letterSpacing = 2.sp
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = lockoutTimeRemaining,
                            fontSize = 28.sp,
                            fontWeight = FontWeight.Bold,
                            color = TextOffWhite,
                            fontFamily = FontFamily.Monospace,
                            letterSpacing = 4.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                Text(
                    text = "Contact I4C Administrator\nadmin@i4c.gov.in • 1930 Helpline",
                    fontSize = 12.sp,
                    color = BorderTaupe,
                    textAlign = TextAlign.Center,
                    lineHeight = 18.sp
                )
            }
        }
    }
}
