package com.i4c.cybershield

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.i4c.cybershield.data.CyberShieldApi
import com.i4c.cybershield.data.MockDataRepository
import com.i4c.cybershield.data.parseAudit
import com.i4c.cybershield.data.parseCase
import com.i4c.cybershield.model.*
import com.i4c.cybershield.net.ConnectionState
import com.i4c.cybershield.net.NetworkConnectionManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

// ═══════════════════════════════════════════════════════════════════════
//  MAIN VIEW MODEL
//  Single source of truth for authentication state, the live case queue,
//  the case currently being reviewed, and the audit trail.
//
//  Every case tracks its OWN status (cases is a live list, not one shared
//  field) so approving/freezing/dismissing one case never affects another.
//
//  Connected to NetworkConnectionManager for dynamic mDNS/UDP discovery,
//  hotspot rediscovery, and real-time live WebSocket alert streaming.
// ═══════════════════════════════════════════════════════════════════════

class MainViewModel(application: Application) : AndroidViewModel(application) {

    val connectionManager = NetworkConnectionManager.getInstance(application)
    private val api = CyberShieldApi(application)

    val connectionState: ConnectionState get() = connectionManager.connectionState
    val backendOnline: Boolean get() = connectionManager.connectionState == ConnectionState.CONNECTED
    val backendMessage: String get() = connectionManager.statusMessage
    val currentServerUrl: String get() = connectionManager.baseUrl

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
    var userRole by mutableStateOf(UserRole.BANK_OFFICIAL)
        private set
    var password by mutableStateOf("")
        private set
    var passwordError by mutableStateOf<String?>(null)
        private set
    private var countdownJob: Job? = null

    // ─── Bottom-tab navigation state (Map / Cases / Activity) ──────────
    var currentTab by mutableIntStateOf(1) // land on "Cases" — the actual work queue
        private set

    // ─── Radar Map State ───────────────────────────────────────────────
    var activeFilter by mutableStateOf("All Terminals")
        private set
    var terminalSearch by mutableStateOf("")
        private set
    var selectedTerminal by mutableStateOf<TerminalMarker?>(null)
        private set

    val filteredTerminals: List<TerminalMarker>
        get() {
            val byType = when (activeFilter) {
                "Bank ATMs" -> liveTerminals.filter { it.type == TerminalType.BANK_ATM }
                "AEPS Micro-ATMs" -> liveTerminals.filter { it.type == TerminalType.AEPS_MICRO_ATM }
                else -> liveTerminals
            }
            val query = terminalSearch.trim().lowercase()
            return if (query.isBlank()) byType else byType.filter {
                it.id.lowercase().contains(query) || it.address.lowercase().contains(query) ||
                    it.bankName.lowercase().contains(query)
            }
        }

    var liveTerminals = mutableStateListOf<TerminalMarker>().apply {
        addAll(MockDataRepository.terminalMarkers)
    }
        private set

    // ─── Case Queue (live, mutable — this is the source of truth) ──────
    var cases = mutableStateListOf<ComplaintTicket>().apply {
        addAll(MockDataRepository.cases)
    }
        private set

    /** All cases still awaiting a decision, most recent first. */
    val pendingCases: List<ComplaintTicket>
        get() = cases.filter { it.status == ActionStatus.PENDING }

    /** Everything already actioned (approved / frozen / dismissed). */
    val resolvedCases: List<ComplaintTicket>
        get() = cases.filterNot { it.status == ActionStatus.PENDING }

    val queueSummaries: List<DispatchSummary>
        get() = if (userRole == UserRole.POLICE_INVESTIGATOR) {
            listOf(
                DispatchSummary("Forwarded to you", cases.count { it.status == ActionStatus.APPROVED || it.status == ActionStatus.EN_ROUTE }, com.i4c.cybershield.ui.theme.AlertOrange),
                DispatchSummary("Accounts Frozen", cases.count { it.status == ActionStatus.BANK_HOLD }, com.i4c.cybershield.ui.theme.MediumCyan),
                DispatchSummary("Closed", cases.count { it.status == ActionStatus.DISMISSED || it.status == ActionStatus.RELEASED }, com.i4c.cybershield.ui.theme.SuccessGreen)
            )
        } else {
            listOf(
                DispatchSummary("Awaiting Review", pendingCases.size, com.i4c.cybershield.ui.theme.AlertOrange),
                DispatchSummary("Sent to Police", cases.count { it.status == ActionStatus.APPROVED }, com.i4c.cybershield.ui.theme.SuccessGreen),
                DispatchSummary("Accounts Frozen", cases.count { it.status == ActionStatus.BANK_HOLD }, com.i4c.cybershield.ui.theme.MediumCyan)
            )
        }

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
    var showNetworkConfigDialog by mutableStateOf(false)
        private set

    // ─── Audit / Activity log ───────────────────────────────────────────
    var auditLog = mutableStateListOf<AuditLogEntry>().apply {
        addAll(MockDataRepository.auditLogEntries)
    }
        private set
    var toastMessage by mutableStateOf<String?>(null)
        private set

    init {
        setupWebSocketListener()
        connectionManager.startDiscovery()
        startPeriodicSync()
    }

    private fun setupWebSocketListener() {
        connectionManager.addEventListener { eventType, json ->
            viewModelScope.launch(Dispatchers.Main) {
                when (eventType) {
                    "NEW_ALERT" -> {
                        val caseObj = json.optJSONObject("data")?.optJSONObject("case")
                        if (caseObj != null) {
                            val parsed = parseCase(caseObj)
                            replaceCase(parsed)
                            showToast("🚨 New Risk Alert: ${parsed.ncrpId} (${parsed.targetTerminal.id})")
                        }
                        refreshFromBackend()
                    }
                    "CASE_UPDATED" -> {
                        val caseObj = json.optJSONObject("data")?.optJSONObject("case")
                        if (caseObj != null) {
                            val parsed = parseCase(caseObj)
                            replaceCase(parsed)
                        }
                        val auditObj = json.optJSONObject("data")?.optJSONObject("audit")
                        if (auditObj != null) {
                            val parsedAudit = parseAudit(auditObj)
                            if (auditLog.none { it.timestamp == parsedAudit.timestamp && it.ncrpId == parsedAudit.ncrpId && it.action == parsedAudit.action }) {
                                auditLog.add(0, parsedAudit)
                            }
                        }
                    }
                    "HANDSHAKE_ACK" -> {
                        refreshFromBackend()
                    }
                }
            }
        }
    }

    private fun startPeriodicSync() {
        viewModelScope.launch {
            while (true) {
                if (connectionManager.connectionState == ConnectionState.CONNECTED) {
                    refreshFromBackend()
                } else if (connectionManager.connectionState == ConnectionState.DISCONNECTED || connectionManager.connectionState == ConnectionState.BACKEND_NOT_FOUND) {
                    // Try discovering in background
                    connectionManager.startDiscovery()
                }
                delay(6000)
            }
        }
    }

    fun refreshFromBackend() {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    val loaded = api.fetchCases(userRole)
                    val terms = api.fetchTerminals()
                    val log = api.fetchAudit()
                    Triple(loaded, terms, log)
                }
            }.onSuccess { (loaded, terms, log) ->
                if (loaded.isNotEmpty()) {
                    cases.clear()
                    cases.addAll(loaded)
                }
                if (terms.isNotEmpty()) {
                    liveTerminals.clear()
                    liveTerminals.addAll(terms)
                }
                if (log.isNotEmpty()) {
                    auditLog.clear()
                    auditLog.addAll(log)
                }
            }.onFailure {
                if (cases.isEmpty()) {
                    cases.addAll(MockDataRepository.cases)
                }
                if (liveTerminals.isEmpty()) {
                    liveTerminals.addAll(MockDataRepository.terminalMarkers)
                }
                if (auditLog.isEmpty()) {
                    auditLog.addAll(MockDataRepository.auditLogEntries)
                }
            }
        }
    }

    fun retryDiscovery() {
        connectionManager.startDiscovery()
    }

    fun setManualHost(host: String, port: Int = 8080) {
        connectionManager.setManualHost(host, port)
    }

    fun showNetworkDialog() {
        showNetworkConfigDialog = true
    }

    fun dismissNetworkDialog() {
        showNetworkConfigDialog = false
    }

    // ═══════════════════════════════════════════════════════════════════
    //  AUTH ACTIONS
    // ═══════════════════════════════════════════════════════════════════

    fun onEmailChanged(value: String) {
        email = value
        emailError = null
    }

    fun onPasswordChanged(value: String) {
        password = value
        passwordError = null
    }

    fun selectRole(role: UserRole) {
        userRole = role
        refreshFromBackend()
    }

    fun onOtpChanged(value: String) {
        if (value.length <= 6 && value.all { it.isDigit() }) {
            otpInput = value
            otpError = null
        }
    }

    fun requestOtp() {
        val trimmed = email.trim().lowercase()

        if (trimmed.isBlank()) {
            emailError = "Please enter your email address."
            return
        }
        if (!trimmed.contains("@") || !trimmed.contains(".")) {
            emailError = "Please enter a valid email address."
            return
        }
        if (password.isBlank()) {
            passwordError = "Enter your password to continue."
            return
        }

        otpRequested = true
        emailError = null
        passwordError = null
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
            refreshFromBackend()
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

    fun onTerminalSearchChanged(value: String) {
        terminalSearch = value
    }

    fun selectTerminal(terminal: TerminalMarker?) {
        selectedTerminal = terminal
    }

    // ═══════════════════════════════════════════════════════════════════
    //  CASE DETAIL ACTIONS
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

    private fun replaceCase(updated: ComplaintTicket) {
        val index = cases.indexOfFirst { it.ncrpId == updated.ncrpId }
        if (index != -1) cases[index] = updated else cases.add(0, updated)
    }

    private fun runAction(ncrpId: String, action: String, fallbackStatus: ActionStatus) {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.act(ncrpId, action, officerName) }
            }.onSuccess { updated ->
                replaceCase(updated)
                addAuditEntry(officerName, ncrpId, updated.justification.ifBlank { action }, updated.targetTerminal.bankName, updated.status)
            }.onFailure {
                val current = caseById(ncrpId)
                if (current != null) {
                    val updated = current.copy(status = fallbackStatus)
                    replaceCase(updated)
                    addAuditEntry(officerName, ncrpId, "Action applied ($action)", current.targetTerminal.bankName, fallbackStatus)
                }
            }
        }
    }

    fun approveAndForward(ncrpId: String) {
        showApproveDialog = false
        if (caseById(ncrpId) == null) return
        runAction(ncrpId, "escalate", ActionStatus.APPROVED)
        showToast("Case sent to police with ATM location pack.")
    }

    fun issueBankHold(ncrpId: String) {
        showBankHoldDialog = false
        val case = caseById(ncrpId) ?: return
        runAction(ncrpId, "hold", ActionStatus.BANK_HOLD)
        showToast("Provisional hold placed with ${case.targetTerminal.bankName}.")
    }

    fun dismissFalsePositive(ncrpId: String) {
        if (caseById(ncrpId) == null) return
        runAction(ncrpId, "dismiss", ActionStatus.DISMISSED)
        showToast("Case dismissed.")
    }

    fun releaseAfterCustomerConfirmation(ncrpId: String) {
        val case = caseById(ncrpId) ?: return
        if (case.status != ActionStatus.BANK_HOLD) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    api.act(ncrpId, "confirm_customer", officerName)
                    api.act(ncrpId, "release", officerName)
                }
            }.onSuccess { updated ->
                replaceCase(updated)
                showToast("Hold released after customer confirmation.")
            }.onFailure {
                val updated = case.copy(status = ActionStatus.RELEASED)
                replaceCase(updated)
                addAuditEntry(officerName, ncrpId, "Hold released after customer confirmation", case.targetTerminal.bankName, ActionStatus.RELEASED)
                showToast("Hold released after customer confirmation.")
            }
        }
    }

    fun fileComplaint(ncrpId: String) {
        runAction(ncrpId, "file_complaint", ActionStatus.BANK_HOLD)
        showToast("Complaint linked — digital and ATM block requested.")
    }

    fun simulateWithdraw(ncrpId: String) {
        runAction(ncrpId, "simulate_withdraw", ActionStatus.EN_ROUTE)
        showToast("Cash-out attempt recorded for police.")
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
