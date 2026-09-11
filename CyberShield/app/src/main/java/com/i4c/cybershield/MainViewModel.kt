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
//  Single source of truth for authentication state, the live case queue,
//  the case currently being reviewed, and the audit trail.
//
//  Every case tracks its OWN status (cases is a live list, not one shared
//  field) so approving/freezing/dismissing one case never affects another,
//  and re-opening any case from the queue always shows that case's own
//  evidence — this is the fix for the single-hardcoded-case bug.
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
    var officerName by mutableStateOf("Officer")
        private set
    private var countdownJob: Job? = null

    // ─── Bottom-tab navigation state (Map / Cases / Activity) ──────────
    var currentTab by mutableIntStateOf(1) // land on "Cases" — the actual work queue
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

    // ─── Case Queue (live, mutable — this is the source of truth) ──────
    var cases = mutableStateListOf<ComplaintTicket>()
        private set

    /** All cases still awaiting a decision, most recent first. */
    val pendingCases: List<ComplaintTicket>
        get() = cases.filter { it.status == ActionStatus.PENDING }

    /** Everything already actioned (approved / frozen / dismissed). */
    val resolvedCases: List<ComplaintTicket>
        get() = cases.filterNot { it.status == ActionStatus.PENDING }

    val queueSummaries: List<DispatchSummary>
        get() = listOf(
            DispatchSummary("Awaiting Review", pendingCases.size, com.i4c.cybershield.ui.theme.AlertOrange),
            DispatchSummary("Sent to Police", cases.count { it.status == ActionStatus.APPROVED }, com.i4c.cybershield.ui.theme.SuccessGreen),
            DispatchSummary("Accounts Frozen", cases.count { it.status == ActionStatus.BANK_HOLD }, com.i4c.cybershield.ui.theme.MediumCyan)
        )

    /** Look up a case by its NCRP id — used by the case-detail screen and deep links. */
    fun caseById(ncrpId: String): ComplaintTicket? = cases.find { it.ncrpId == ncrpId }

    /** Look up which case (if any) targets a given predicted terminal — used by the map. */
    fun caseForTerminal(terminalId: String): ComplaintTicket? =
        cases.find { it.targetTerminal.id == terminalId }

    // ─── Case Detail dialogs ────────────────────────────────────────────
    var showApproveDialog by mutableStateOf(false)
        private set
    var showBankHoldDialog by mutableStateOf(false)
        private set

    // ─── Audit / Activity log ───────────────────────────────────────────
    var auditLog = mutableStateListOf<AuditLogEntry>()
        private set
    var toastMessage by mutableStateOf<String?>(null)
        private set

    init {
        cases.addAll(MockDataRepository.cases)
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
        if (value.length <= 6 && value.all { it.isDigit() }) {
            otpInput = value
            otpError = null
        }
    }

    fun requestOtp() {
        val trimmed = email.trim().lowercase()
        val isAuthorized = MockDataRepository.authorizedDomains.any { trimmed.endsWith(it) }

        if (trimmed.isBlank()) {
            emailError = "Please enter your official email address."
            return
        }
        if (!isAuthorized) {
            emailError = "This app is restricted to official police and government email addresses."
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
            officerName = email.substringBefore("@").replace(".", " ")
                .split(" ").joinToString(" ") { it.replaceFirstChar { c -> c.uppercase() } }
                .ifBlank { "Officer" }
            countdownJob?.cancel()
        } else {
            failedAttempts++
            otpError = "That code doesn't match. Attempt $failedAttempts of 5."
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
        lockoutTimeRemaining = "48:00:00"
        viewModelScope.launch {
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
    //  NAVIGATION (bottom tabs only — case detail is a pushed screen,
    //  handled by NavGraph, not tab state)
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

    // ═══════════════════════════════════════════════════════════════════
    //  CASE DETAIL ACTIONS — every action operates on the specific case
    //  passed in (by ncrpId), never a hardcoded/global one.
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

    private fun updateCaseStatus(ncrpId: String, newStatus: ActionStatus) {
        val index = cases.indexOfFirst { it.ncrpId == ncrpId }
        if (index != -1) {
            cases[index] = cases[index].copy(status = newStatus)
        }
    }

    fun approveAndForward(ncrpId: String) {
        showApproveDialog = false
        val case = caseById(ncrpId) ?: return
        updateCaseStatus(ncrpId, ActionStatus.APPROVED)
        val unit = nearestPoliceUnit(case)
        addAuditEntry(
            officerName = officerName,
            ncrpId = ncrpId,
            action = "Case approved and forwarded to police",
            targetUnit = unit,
            status = ActionStatus.APPROVED
        )
        showToast("Case sent to $unit.")
    }

    fun issueBankHold(ncrpId: String) {
        showBankHoldDialog = false
        val case = caseById(ncrpId) ?: return
        updateCaseStatus(ncrpId, ActionStatus.BANK_HOLD)
        addAuditEntry(
            officerName = officerName,
            ncrpId = ncrpId,
            action = "Account frozen — temporary bank hold placed",
            targetUnit = case.targetTerminal.bankName,
            status = ActionStatus.LIEN_PLACED
        )
        showToast("Temporary hold placed with ${case.targetTerminal.bankName}.")
    }

    fun dismissFalsePositive(ncrpId: String) {
        val case = caseById(ncrpId) ?: return
        updateCaseStatus(ncrpId, ActionStatus.DISMISSED)
        addAuditEntry(
            officerName = officerName,
            ncrpId = ncrpId,
            action = "Marked as false positive — no further action",
            targetUnit = "—",
            status = ActionStatus.DISMISSED
        )
        showToast("Case dismissed.")
    }

    private fun nearestPoliceUnit(case: ComplaintTicket): String {
        // In production this comes from the jurisdiction lookup for the
        // predicted terminal's location; kept simple for the prototype.
        val area = case.targetTerminal.address.substringAfter(",").trim()
        return "$area Police Station"
    }

    // ═══════════════════════════════════════════════════════════════════
    //  AUDIT LOG
    // ═══════════════════════════════════════════════════════════════════

    private fun addAuditEntry(
        officerName: String,
        ncrpId: String,
        action: String,
        targetUnit: String,
        status: ActionStatus
    ) {
        auditLog.add(
            0,
            AuditLogEntry(
                timestamp = currentTimeLabel(),
                officerName = officerName,
                ncrpId = ncrpId,
                action = action,
                targetUnit = targetUnit,
                status = status
            )
        )
    }

    private fun currentTimeLabel(): String {
        val cal = java.util.Calendar.getInstance()
        return String.format("%02d:%02d %s",
            if (cal.get(java.util.Calendar.HOUR) == 0) 12 else cal.get(java.util.Calendar.HOUR),
            cal.get(java.util.Calendar.MINUTE),
            if (cal.get(java.util.Calendar.AM_PM) == 0) "AM" else "PM"
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
