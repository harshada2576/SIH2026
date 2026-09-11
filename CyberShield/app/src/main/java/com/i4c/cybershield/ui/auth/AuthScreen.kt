package com.i4c.cybershield.ui.auth

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.foundation.layout.imePadding
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.model.UserRole
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  AUTH SCREEN – Clean, Modern Sign-In with Role Dropdown & Standard OTP
// ═══════════════════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuthScreen(
    email: String,
    emailError: String?,
    password: String,
    passwordError: String?,
    otpInput: String,
    otpError: String?,
    otpRequested: Boolean,
    failedAttempts: Int,
    isLocked: Boolean,
    lockoutTimeRemaining: String,
    otpCountdownSeconds: Int,
    canResendOtp: Boolean,
    selectedRole: UserRole,
    onEmailChanged: (String) -> Unit,
    onPasswordChanged: (String) -> Unit,
    onRoleSelected: (UserRole) -> Unit,
    onOtpChanged: (String) -> Unit,
    onRequestOtp: () -> Unit,
    onVerifyOtp: () -> Unit,
    onResendOtp: () -> Unit
) {
    val focusManager = LocalFocusManager.current
    val passwordFocusRequester = remember { FocusRequester() }
    val otpFocusRequester = remember { FocusRequester() }
    var roleDropdownExpanded by remember { mutableStateOf(false) }

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
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .alpha(if (isLocked) 0.15f else 1f),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Spacer(modifier = Modifier.height(32.dp))

            // Clean Brand Header
            AuthHeader()

            Spacer(modifier = Modifier.height(36.dp))

            // ─── 1. Email Field ───────────────────────────────────────
            OutlinedTextField(
                value = email,
                onValueChange = onEmailChanged,
                modifier = Modifier.fillMaxWidth(),
                enabled = !otpRequested && !isLocked,
                label = { Text("Email", color = BorderTaupe) },
                placeholder = { Text("name@example.com", color = BorderTaupe.copy(alpha = 0.5f)) },
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
                    imeAction = ImeAction.Next
                ),
                keyboardActions = KeyboardActions(
                    onNext = { passwordFocusRequester.requestFocus() }
                )
            )

            if (emailError != null) {
                Text(
                    text = emailError,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 4.dp, top = 4.dp),
                    color = ErrorRed,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // ─── 2. Password Field ────────────────────────────────────
            OutlinedTextField(
                value = password,
                onValueChange = onPasswordChanged,
                modifier = Modifier
                    .fillMaxWidth()
                    .focusRequester(passwordFocusRequester),
                enabled = !otpRequested && !isLocked,
                label = { Text("Password", color = BorderTaupe) },
                placeholder = { Text("Enter password", color = BorderTaupe.copy(alpha = 0.5f)) },
                singleLine = true,
                isError = passwordError != null,
                visualTransformation = PasswordVisualTransformation(),
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
                    keyboardType = KeyboardType.Password,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(
                    onDone = {
                        focusManager.clearFocus()
                        if (!otpRequested) onRequestOtp()
                    }
                )
            )

            if (passwordError != null) {
                Text(
                    text = passwordError,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 4.dp, top = 4.dp),
                    color = ErrorRed,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // ─── 3. Role Dropdown Box ──────────────────────────────────
            ExposedDropdownMenuBox(
                expanded = roleDropdownExpanded && !otpRequested && !isLocked,
                onExpandedChange = {
                    if (!otpRequested && !isLocked) {
                        roleDropdownExpanded = !roleDropdownExpanded
                    }
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                OutlinedTextField(
                    value = selectedRole.displayName,
                    onValueChange = {},
                    readOnly = true,
                    enabled = !otpRequested && !isLocked,
                    label = { Text("Role", color = BorderTaupe) },
                    trailingIcon = {
                        ExposedDropdownMenuDefaults.TrailingIcon(expanded = roleDropdownExpanded)
                    },
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = AlertOrange,
                        unfocusedBorderColor = BorderTaupe.copy(alpha = 0.5f),
                        focusedTextColor = TextOffWhite,
                        unfocusedTextColor = TextOffWhite,
                        focusedLabelColor = AlertOrange
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor()
                )

                ExposedDropdownMenu(
                    expanded = roleDropdownExpanded,
                    onDismissRequest = { roleDropdownExpanded = false },
                    modifier = Modifier.background(SurfaceCharcoal)
                ) {
                    UserRole.entries.forEach { role ->
                        DropdownMenuItem(
                            text = {
                                Text(
                                    text = role.displayName,
                                    color = if (role == selectedRole) AlertOrange else TextOffWhite,
                                    fontWeight = if (role == selectedRole) FontWeight.Bold else FontWeight.Normal
                                )
                            },
                            onClick = {
                                onRoleSelected(role)
                                roleDropdownExpanded = false
                            }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ─── Request OTP Button ────────────────────────────────────
            AnimatedVisibility(visible = !otpRequested && !isLocked) {
                Button(
                    onClick = {
                        focusManager.clearFocus()
                        onRequestOtp()
                    },
                    enabled = email.isNotBlank() && password.isNotBlank() && !isLocked,
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
                        text = "SEND OTP",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }

            // ─── 4. Standard OTP Input Section ────────────────────────
            AnimatedVisibility(
                visible = otpRequested && !isLocked,
                enter = fadeIn() + expandVertically(),
                exit = fadeOut() + shrinkVertically()
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    // Demo OTP info & quick fill
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onOtpChanged("123456") },
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
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Demo OTP: 123456",
                                color = SuccessGreen,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "Tap to Auto-fill",
                                color = MediumCyan,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Standard single OTP field (normal input)
                    OutlinedTextField(
                        value = otpInput,
                        onValueChange = onOtpChanged,
                        modifier = Modifier
                            .fillMaxWidth()
                            .focusRequester(otpFocusRequester),
                        enabled = !isLocked,
                        label = { Text("Enter OTP", color = BorderTaupe) },
                        placeholder = { Text("123456", color = BorderTaupe.copy(alpha = 0.5f)) },
                        singleLine = true,
                        isError = otpError != null,
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
                            keyboardType = KeyboardType.Number,
                            imeAction = ImeAction.Done
                        ),
                        keyboardActions = KeyboardActions(
                            onDone = {
                                focusManager.clearFocus()
                                onVerifyOtp()
                            }
                        )
                    )

                    if (otpError != null) {
                        Text(
                            text = otpError,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(start = 4.dp, top = 4.dp),
                            color = ErrorRed,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    // Resend OTP / attempts row
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

                        if (failedAttempts > 0) {
                            Text(
                                text = "Attempts: $failedAttempts/5",
                                color = if (failedAttempts >= 3) AlertOrange else ErrorRed,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))

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

            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}

// ─── Clean Header ──────────────────────────────────────────────────────

@Composable
private fun AuthHeader() {
    val infiniteTransition = rememberInfiniteTransition(label = "shield_pulse")
    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.7f,
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
        // Shield Emblem
        Box(
            modifier = Modifier
                .size(88.dp)
                .clip(CircleShape)
                .background(SurfaceCharcoal)
                .border(2.dp, AlertOrange.copy(alpha = glowAlpha), CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Security,
                contentDescription = "Shield Emblem",
                tint = AlertOrange.copy(alpha = glowAlpha),
                modifier = Modifier.size(44.dp)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Title
        Text(
            text = "CYBER SHIELD",
            fontSize = 26.sp,
            fontWeight = FontWeight.Black,
            color = TextOffWhite,
            letterSpacing = 4.sp
        )
    }
}

// ─── Lockdown Card ─────────────────────────────────────────────────────

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
                    text = "ACCOUNT LOCKED",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Black,
                    color = AlertOrange,
                    letterSpacing = 2.sp
                )

                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = "5 Consecutive Failed Attempts",
                    fontSize = 14.sp,
                    color = TextOffWhite,
                    fontWeight = FontWeight.Medium,
                    textAlign = TextAlign.Center
                )

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "Security Lockdown Activated",
                    fontSize = 16.sp,
                    color = AlertOrange,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center
                )

                Spacer(modifier = Modifier.height(20.dp))

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
            }
        }
    }
}
