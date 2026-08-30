package com.i4c.cybershield

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.i4c.cybershield.data.MockDataRepository
import com.i4c.cybershield.model.*
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// ═══════════════════════════════════════════════════════════════════════
//  MAIN VIEW MODEL
//  Single source of truth for authentication state, navigation,
//  investigation actions, and dispatch audit log.
// ═══════════════════════════════════════════════════════════════════════

class MainViewModel : ViewModel() {

    // ─── Authentication State ──────────────────────────────────────────
    var email by mutableStateOf("")
        private set
    var emailError by mutableStateOf<String?>(null)
        private set
    var otpInput by mutableStateOf("")
        private set
    var otpError by mutableStateOf<String?>(null)
        private set
    var isAuthenticated by mutableStateOf(false)
        private set
    var otpRequested by mutableStateOf(false)
        private set
    var otpVerified by mutableStateOf(false)
        private set
    var failedAttempts by mutableIntStateOf(0)
        private set
    var isLocked by mutableStateOf(false)
        private set
    var lockoutTimeRemaining by mutableStateOf("")
        private set
    var otpCountdownSeconds by mutableIntStateOf(60)
        private set
    var canResendOtp by mutableStateOf(false)
        private set
    private var countdownJob: Job? = null

    // ─── Navigation State ──────────────────────────────────────────────
    var currentTab by mutableIntStateOf(0)
        private set

    // ─── Radar Map State ───────────────────────────────────────────────
    var activeFilter by mutableStateOf("All Terminals")
        private set
    var selectedTerminal by mutableStateOf<TerminalMarker?>(null)
        private set

    val filteredTerminals: List<TerminalMarker>
        get() = when (activeFilter) {
            "Bank ATMs" -> MockDataRepository.terminalMarkers.filter { it.type == TerminalType.BANK_ATM }
            "AEPS Micro-ATMs" -> MockDataRepository.terminalMarkers.filter { it.type == TerminalType.AEPS_MICRO_ATM }
            else -> MockDataRepository.terminalMarkers
        }

    // ─── Investigation State ───────────────────────────────────────────
    var investigationStatus by mutableStateOf(ActionStatus.PENDING)
        private set
    var showApproveDialog by mutableStateOf(false)
        private set
    var showBankHoldDialog by mutableStateOf(false)
        private set

    // ─── Dispatch / Audit State ────────────────────────────────────────
    var auditLog = mutableStateListOf<AuditLogEntry>()
        private set
    var toastMessage by mutableStateOf<String?>(null)
        private set

    init {
        auditLog.addAll(MockDataRepository.auditLogEntries)
    }

    // ═══════════════════════════════════════════════════════════════════
    //  AUTH ACTIONS
    // ═══════════════════════════════════════════════════════════════════

    fun onEmailChanged(value: String) {
        email = value
        emailError = null
    }

    fun onOtpChanged(value: String) {
        // Only allow up to 6 digits
        if (value.length <= 6 && value.all { it.isDigit() }) {
            otpInput = value
            otpError = null
        }
    }

    fun requestOtp() {
        val trimmed = email.trim().lowercase()
        val isAuthorized = MockDataRepository.authorizedDomains.any { trimmed.endsWith(it) }

        if (!isAuthorized) {
            emailError = "Access Denied: Registration restricted to official law enforcement & RBI domains."
            return
        }
        if (trimmed.isBlank()) {
            emailError = "Email address is required."
            return
        }

        otpRequested = true
        emailError = null
        startOtpCountdown()
    }

    fun verifyOtp() {
        if (isLocked) return

        if (otpInput == MockDataRepository.demoOtp) {
            otpVerified = true
            isAuthenticated = true
            failedAttempts = 0
            otpError = null
            countdownJob?.cancel()
        } else {
            failedAttempts++
            otpError = "Invalid OTP. Attempt $failedAttempts of 5."
            otpInput = ""

            if (failedAttempts >= 5) {
                isLocked = true
                startLockoutCountdown()
            }
        }
    }

    fun resendOtp() {
        if (!canResendOtp) return
        otpInput = ""
        otpError = null
        canResendOtp = false
        otpCountdownSeconds = 60
        startOtpCountdown()
        // In a real app this would resend via SMS gateway
    }

    private fun startOtpCountdown() {
        countdownJob?.cancel()
        otpCountdownSeconds = 60
        canResendOtp = false
        countdownJob = viewModelScope.launch {
            while (otpCountdownSeconds > 0) {
                delay(1000)
                otpCountdownSeconds--
            }
            canResendOtp = true
        }
    }

    private fun startLockoutCountdown() {
        // For demo: show 48-hour lockout message (countdown simulated)
        lockoutTimeRemaining = "48:00:00"
        viewModelScope.launch {
            // Simulate lockout timer updating (demo purposes)
            var seconds = 48 * 60 * 60
            while (seconds > 0 && isLocked) {
                val hrs = seconds / 3600
                val mins = (seconds % 3600) / 60
                val secs = seconds % 60
                lockoutTimeRemaining = String.format("%02d:%02d:%02d", hrs, mins, secs)
                delay(1000)
                seconds--
            }
            if (isLocked) {
                isLocked = false
                failedAttempts = 0
                lockoutTimeRemaining = ""
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  NAVIGATION
    // ═══════════════════════════════════════════════════════════════════

    fun selectTab(index: Int) {
        currentTab = index
    }

    // ═══════════════════════════════════════════════════════════════════
    //  RADAR MAP ACTIONS
    // ═══════════════════════════════════════════════════════════════════

    fun setFilter(filter: String) {
        activeFilter = filter
    }

    fun selectTerminal(terminal: TerminalMarker?) {
        selectedTerminal = terminal
    }

    fun navigateToInvestigation() {
        selectedTerminal = null
        currentTab = 1
    }

    // ═══════════════════════════════════════════════════════════════════
    //  INVESTIGATION ACTIONS
    // ═══════════════════════════════════════════════════════════════════

    fun showApproveConfirmation() {
        showApproveDialog = true
    }

    fun showBankHoldConfirmation() {
        showBankHoldDialog = true
    }

    fun dismissApproveDialog() {
        showApproveDialog = false
    }

    fun dismissBankHoldDialog() {
        showBankHoldDialog = false
    }

    fun approveAndForward() {
        showApproveDialog = false
        investigationStatus = ActionStatus.APPROVED
        addAuditEntry(
            timestamp = "10:${18 + auditLog.size} AM",
            officerName = "Officer Current User",
            ncrpId = "NCRP-994821",
            action = "Dispatched to Sector 20 Police Patrol",
            targetUnit = "Sector 20 Patrol Unit",
            status = ActionStatus.EN_ROUTE
        )
        showToast("Alert package dispatched to Sector 20 Police Patrol.")
    }

    fun issueBankHold() {
        showBankHoldDialog = false
        investigationStatus = ActionStatus.BANK_HOLD
        addAuditEntry(
            timestamp = "10:${19 + auditLog.size} AM",
            officerName = "Officer Current User",
            ncrpId = "NCRP-994821",
            action = "CBS Temporary Hold issued via CFCFRMS",
            targetUnit = "SBI Core Banking System",
            status = ActionStatus.LIEN_PLACED
        )
        showToast("Temporary Hold Issued to SBI Core Banking System")
    }

    fun dismissFalsePositive() {
        investigationStatus = ActionStatus.DISMISSED
        showToast("Complaint dismissed as false positive.")
    }

    // ═══════════════════════════════════════════════════════════════════
    //  AUDIT LOG
    // ═══════════════════════════════════════════════════════════════════

    private fun addAuditEntry(
        timestamp: String,
        officerName: String,
        ncrpId: String,
        action: String,
        targetUnit: String,
        status: ActionStatus
    ) {
        auditLog.add(
            0,
            AuditLogEntry(
                timestamp = timestamp,
                officerName = officerName,
                ncrpId = ncrpId,
                action = action,
                targetUnit = targetUnit,
                status = status
            )
        )
    }

    // ═══════════════════════════════════════════════════════════════════
    //  TOAST
    // ═══════════════════════════════════════════════════════════════════

    fun showToast(message: String) {
        toastMessage = message
        viewModelScope.launch {
            delay(3000)
            toastMessage = null
        }
    }

    fun clearToast() {
        toastMessage = null
    }
}
