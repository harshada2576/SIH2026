package com.i4c.cybershield.model

import androidx.compose.ui.graphics.Color

// ═══════════════════════════════════════════════════════════════════════
//  DATA MODELS – Cyber Shield Predictive Cashout Radar
// ═══════════════════════════════════════════════════════════════════════

/** Types of payment terminals tracked by the system */
enum class TerminalType(val displayName: String) {
    BANK_ATM("Bank ATM"),
    AEPS_MICRO_ATM("AEPS Micro-ATM Agent")
}

/** Risk classification level */
enum class RiskLevel(val displayName: String) {
    CRITICAL("Critical Risk"),
    HIGH("High Risk"),
    MEDIUM("Medium Risk"),
    LOW("Low Risk")
}

/** The operational view shown after sign-in. */
enum class UserRole(val displayName: String, val shortDescription: String) {
    BANK_OFFICIAL("Bank official", "Review, hold and forward suspicious activity"),
    POLICE_INVESTIGATOR("Police investigator", "Trace forwarded cases and location evidence")
}

/** Current review/dispatch status of a case */
enum class ActionStatus(val displayName: String) {
    PENDING("Awaiting Review"),
    APPROVED("Sent to Police"),
    BANK_HOLD("Account Frozen (Bank Hold)"),
    DISMISSED("Dismissed – False Positive"),
    EN_ROUTE("Police En Route"),
    LIEN_PLACED("Bank Hold Confirmed"),
    RELEASED("Released after customer confirmation")
}

/** Terminal marker on the cashout radar map */
data class TerminalMarker(
    val id: String,
    val address: String,
    val type: TerminalType,
    val latitude: Double,
    val longitude: Double,
    val riskLevel: RiskLevel,
    val confidencePercent: Int,
    val cashoutWindow: String,
    val bankName: String = "SBI",
    val distanceKm: Double? = null
)

/** Node in the money-laundering trail graph */
data class TrailNode(
    val label: String,
    val type: String, // "victim", "mule", "aggregator", "terminal"
    val accountHint: String = ""
)

/** An edge connecting two nodes in the money trail */
data class TrailEdge(
    val fromIndex: Int,
    val toIndex: Int,
    val label: String = "",
    val amount: String = "Not supplied",
    val timestamp: String = "Recorded event",
    val channel: String = "Digital transfer"
)

/** Money trail visualization: nodes + edges */
data class MoneyTrail(
    val nodes: List<TrailNode>,
    val edges: List<TrailEdge>
)

/**
 * A single signal contributing to the risk score, written for a human
 * investigator first. [name]/[explanation] must stand alone in plain
 * English with no jargon. [technicalTag] is the internal rule/model name.
 */
data class RiskSignal(
    val icon: String,
    val name: String,
    val contributionPercent: Int,
    val explanation: String,
    val technicalTag: String = ""
)

/** Full explainable score breakdown for a case */
data class RiskBreakdown(
    val totalPercent: Int,
    val signals: List<RiskSignal>
)

/** Recorded withdrawal attempt at an ATM or Micro-ATM */
data class WithdrawalAttempt(
    val attemptId: String = "",
    val time: String = "",
    val amount: String = "",
    val terminalId: String = "",
    val location: String = "",
    val status: String = "FLAGGED"
)

/** Repeat activity summary */
data class RepeatActivity(
    val accountId: String = "",
    val terminalId: String = "",
    val attempts: Int = 0,
    val escalation: String = "MONITORED",
    val multiplier: Double = 1.0
)

/** Recorded notification item dispatched by backend */
data class NotificationItem(
    val notificationId: String = "",
    val channel: String = "",
    val eventType: String = "",
    val recipient: String = "",
    val recipientGroup: String = "",
    val status: String = "SENT",
    val isSimulated: Boolean = true,
    val timestamp: String = "",
    val preview: String = ""
)

/** Channel delivery status */
data class NotificationChannelStatus(
    val status: String = "NOT_SENT",
    val isSimulated: Boolean = true,
    val timestamp: String? = null,
    val count: Int = 0
)

/**
 * One suspicious-money-flow case, from complaint to (eventually) resolution.
 * This is the single unit an investigator opens, reviews, and acts on.
 */
data class ComplaintTicket(
    val ncrpId: String,
    val reportedLoss: String,
    val timeElapsed: String,
    val victimAccount: String,
    val status: ActionStatus,
    val targetTerminal: TerminalMarker,
    val summary: String = "",
    val moneyTrail: MoneyTrail = MoneyTrail(emptyList(), emptyList()),
    val riskBreakdown: RiskBreakdown = RiskBreakdown(0, emptyList()),
    val complaintId: String? = null,
    val confirmationState: String = "PENDING_CONFIRMATION",
    val transactionCount: Int = 0,
    val digitalBlockActive: Boolean = false,
    val atmBlockActive: Boolean = false,
    val lifecycle: String = "PRE_COMPLAINT_INTERVENTION",
    val interventionTier: String = "",
    val justification: String = "",
    val legitimateBalance: Double = 0.0,
    val suspiciousExposure: Double = 0.0,
    val withdrawalAttempts: List<WithdrawalAttempt> = emptyList(),
    val nearbyTerminals: List<TerminalMarker> = emptyList(),
    val repeatActivity: RepeatActivity = RepeatActivity(),
    val simHash: String = "",
    val deviceFingerprint: String = "",
    val confidencePercent: Int = 0,
    val evidence: List<String> = emptyList(),
    val notificationStatus: Map<String, NotificationChannelStatus> = emptyMap(),
    val notifications: List<NotificationItem> = emptyList()
)

/** An audit log entry — the accountability trail of every action taken */
data class AuditLogEntry(
    val timestamp: String,
    val officerName: String,
    val ncrpId: String,
    val action: String,
    val targetUnit: String,
    val status: ActionStatus
)

/** Summary statistic card shown at the top of the case queue */
data class DispatchSummary(
    val title: String,
    val count: Int,
    val accentColor: Color
)

/** OTP session state */
data class OtpSession(
    val email: String,
    val generatedOtp: String,
    val remainingSeconds: Int = 60,
    val attempts: Int = 0,
    val isLocked: Boolean = false,
    val lockoutMinutes: Int = 48 * 60 // 48 hours in minutes
)

/** Pending review queue item */
data class PendingReviewItem(
    val ticket: ComplaintTicket,
    val priorityRank: Int
)

// ═══════════════════════════════════════════════════════════════════════
//  SIH26184 OPERATIONAL & INVESTIGATION MODELS
// ═══════════════════════════════════════════════════════════════════════

/** Standard case lifecycle states */
enum class CaseLifecycle(val displayName: String, val badgeColorHex: String) {
    PRE_COMPLAINT_INTERVENTION("PRE-COMPLAINT INTERVENTION", "#06B6D4"),
    POST_COMPLAINT_ESCALATED("POST-COMPLAINT ESCALATED", "#EF4444"),
    CASHOUT_ATTEMPT_DETECTED("CASHOUT ATTEMPT DETECTED", "#F59E0B"),
    RESOLVED("RESOLVED", "#10B981")
}

/** Transaction confirmation state */
enum class ConfirmationStatus(val displayName: String) {
    PENDING_CONFIRMATION("PENDING CONFIRMATION"),
    CONFIRMED_LEGITIMATE("CONFIRMED LEGITIMATE"),
    CONFIRMED_FRAUD("CONFIRMED FRAUD"),
    EXPIRED("CONFIRMATION EXPIRED"),
    SKIPPED("CONFIRMATION SKIPPED")
}

/** Transaction confirmation details */
data class TransactionConfirmationInfo(
    val txnId: String,
    val payerAccount: String,
    val amount: String,
    val status: ConfirmationStatus,
    val promptChannel: String = "SMS + CBS Push Notification",
    val requestedAt: String,
    val respondedAt: String? = null,
    val explanatoryNote: String = "High-velocity transfer requiring explicit victim verification before final clearance."
)

/** Withdrawal attempt status */
enum class WithdrawalAttemptStatus(val displayName: String) {
    BLOCKED("BLOCKED AT TERMINAL"),
    INTERCEPTED("INTERCEPTED & HELD"),
    ALLOWED("ALLOWED"),
    FLAGGED("FLAGGED FOR REVIEW")
}

/** Recorded withdrawal attempt at an ATM or Micro-ATM */
data class RecordedWithdrawal(
    val attemptId: String,
    val terminalId: String,
    val terminalName: String,
    val amount: String,
    val timestamp: String,
    val status: WithdrawalAttemptStatus,
    val channel: String = "ATM CASH DISPENSE",
    val failureReason: String = "Provisional bank hold active on source aggregator account"
)

/** Chronological timeline event linking fund movement, predictions, and physical attempts */
data class LocationTimelineEvent(
    val timestamp: String,
    val title: String,
    val description: String,
    val eventType: String // "ORIGIN", "MULE_HOP", "PREDICTION", "ATTEMPT", "ACTION"
)

/** Selective fund protection breakdown */
data class SelectiveFundBreakdown(
    val existingBalance: String = "₹20,000",
    val suspiciousAmount: String = "₹1,00,000",
    val protectedAmount: String = "₹1,00,000",
    val sourceTxn: String = "TXN-8f2a1e",
    val holdReason: String = "Selective provisional hold on recent suspicious chain funds",
    val isPreComplaint: Boolean = true
)

/** Detailed money trail hop with account details and risk flags */
data class DetailedTrailHop(
    val hopNumber: Int,
    val fromAccount: String,
    val toAccount: String,
    val amount: String,
    val timestamp: String,
    val channel: String,
    val sourceTier: String, // "Victim", "Mule L1", "Mule L2", "Aggregator"
    val targetTier: String,
    val flags: List<String> = emptyList()
)

/** Nearby terminal context for spatial intelligence */
data class NearbyTerminal(
    val id: String,
    val address: String,
    val distanceKm: Double,
    val type: TerminalType = TerminalType.BANK_ATM
)

/** Repeated ATM + Account behavior tracking */
data class TerminalRecurrence(
    val terminalId: String,
    val accountTarget: String,
    val attemptsCount: Int,
    val escalationState: String, // "MONITORED", "ELEVATED_RISK", "PERSISTENT_TERMINAL_RISK"
    val riskMultiplier: Double = 1.5
)

/** Unified Investigation Case representation */
data class InvestigationCase(
    val caseId: String,
    val flaggedAccount: String,
    val lifecycle: CaseLifecycle,
    val riskScorePercent: Int,
    val confidencePercent: Int,
    val suspiciousAmount: String,
    val targetTerminal: TerminalMarker,
    val predictedWindow: String,
    val summaryNarrative: String = "High-velocity multi-hop mule trail converging onto aggregator node with predicted cashout attempt.",
    val confirmation: TransactionConfirmationInfo? = null,
    val funds: SelectiveFundBreakdown = SelectiveFundBreakdown(),
    val trailHops: List<DetailedTrailHop> = emptyList(),
    val withdrawalAttempts: List<RecordedWithdrawal> = emptyList(),
    val timelineEvents: List<LocationTimelineEvent> = emptyList(),
    val xaiBreakdown: RiskBreakdown = RiskBreakdown(0, emptyList()),
    val nearbyTerminals: List<NearbyTerminal> = emptyList(),
    val recurrence: TerminalRecurrence? = null,
    val bankHoldActive: Boolean = true,
    val atmBlockRequested: Boolean = true,
    val leaNotificationSent: Boolean = true
)

data class Quadruple<A, B, C, D>(
    val first: A,
    val second: B,
    val third: C,
    val fourth: D
)

