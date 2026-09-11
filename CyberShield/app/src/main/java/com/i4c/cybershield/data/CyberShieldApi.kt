package com.i4c.cybershield.data

import android.content.Context
import com.i4c.cybershield.model.*
import com.i4c.cybershield.net.NetworkConnectionManager
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class CyberShieldApi(private val context: Context) {
    private val connectionManager get() = NetworkConnectionManager.getInstance(context)
    val baseUrl: String get() = connectionManager.baseUrl.trimEnd('/')

    fun health(): JSONObject = get("/health")

    fun fetchCases(role: UserRole): List<ComplaintTicket> {
        val roleQ = if (role == UserRole.POLICE_INVESTIGATOR) "POLICE" else "BANK"
        val json = get("/cases?role=$roleQ")
        val arr = json.optJSONArray("cases") ?: JSONArray()
        return (0 until arr.length()).map { parseCase(arr.getJSONObject(it)) }
    }

    fun fetchTerminals(): List<TerminalMarker> {
        val json = get("/terminals")
        val arr = json.optJSONArray("terminals") ?: JSONArray()
        return (0 until arr.length()).map { parseTerminal(arr.getJSONObject(it)) }
    }

    fun fetchAudit(): List<AuditLogEntry> {
        val json = get("/audit")
        val arr = json.optJSONArray("audit") ?: JSONArray()
        return (0 until arr.length()).map { parseAudit(arr.getJSONObject(it)) }
    }

    fun fetchHeatmap(eventType: String? = null, city: String? = null): List<HeatmapPoint> {
        val queryParams = mutableListOf<String>()
        if (!eventType.isNullOrBlank() && eventType != "ALL") {
            queryParams.add("event_type=$eventType")
        }
        if (!city.isNullOrBlank()) {
            queryParams.add("city=$city")
        }
        val qs = if (queryParams.isNotEmpty()) "?" + queryParams.joinToString("&") else ""
        val json = get("/heatmap$qs")
        val arr = json.optJSONArray("points") ?: JSONArray()
        return (0 until arr.length()).map { parseHeatmapPoint(arr.getJSONObject(it)) }
    }

    fun fetchCaseHeatmap(caseId: String): List<HeatmapPoint> {
        val json = get("/cases/$caseId/heatmap")
        val arr = json.optJSONArray("points") ?: JSONArray()
        return (0 until arr.length()).map { parseHeatmapPoint(arr.getJSONObject(it)) }
    }

    fun act(ncrpId: String, action: String, officer: String): ComplaintTicket {
        val body = JSONObject().put("officer", officer)
        return parseCase(post("/cases/$ncrpId/$action", body))
    }

    private fun get(path: String): JSONObject {
        val conn = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8000
            readTimeout = 15000
        }
        return read(conn)
    }

    private fun post(path: String, body: JSONObject): JSONObject {
        val conn = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8000
            readTimeout = 15000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }
        OutputStreamWriter(conn.outputStream).use { it.write(body.toString()) }
        return read(conn)
    }

    private fun read(conn: HttpURLConnection): JSONObject {
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = stream.bufferedReader().use { it.readText() }
        conn.disconnect()
        if (code !in 200..299) {
            throw IllegalStateException("API $code: $text")
        }
        return JSONObject(text)
    }
}

fun parseStatus(raw: String): ActionStatus =
    runCatching { ActionStatus.valueOf(raw) }.getOrDefault(ActionStatus.PENDING)

fun parseRisk(raw: String): RiskLevel =
    runCatching { RiskLevel.valueOf(raw) }.getOrDefault(RiskLevel.MEDIUM)

fun parseTerminalType(raw: String): TerminalType =
    if (raw.contains("AEPS", ignoreCase = true)) TerminalType.AEPS_MICRO_ATM else TerminalType.BANK_ATM

fun parseTerminal(obj: JSONObject): TerminalMarker = TerminalMarker(
    id = obj.optString("id"),
    address = obj.optString("address"),
    type = parseTerminalType(obj.optString("type")),
    latitude = obj.optDouble("latitude"),
    longitude = obj.optDouble("longitude"),
    riskLevel = parseRisk(obj.optString("riskLevel", "MEDIUM")),
    confidencePercent = obj.optInt("confidencePercent"),
    cashoutWindow = obj.optString("cashoutWindow"),
    bankName = obj.optString("bankName", "Bank"),
    distanceKm = if (obj.has("distanceKm")) obj.optDouble("distanceKm") else null
)

fun parseHeatmapPoint(obj: JSONObject): HeatmapPoint = HeatmapPoint(
    latitude = obj.optDouble("latitude"),
    longitude = obj.optDouble("longitude"),
    weight = obj.optDouble("weight", 0.5),
    eventType = obj.optString("event_type", "SUSPICIOUS_ACTIVITY"),
    timestamp = obj.optString("timestamp", ""),
    caseId = if (obj.has("case_id") && !obj.isNull("case_id")) obj.optString("case_id") else null,
    terminalId = if (obj.has("terminal_id") && !obj.isNull("terminal_id")) obj.optString("terminal_id") else null,
    city = obj.optString("city", "India"),
    riskLevel = obj.optString("risk_level", "HIGH")
)

fun parseCase(obj: JSONObject): ComplaintTicket {
    val trailObj = obj.optJSONObject("moneyTrail") ?: JSONObject()
    val nodesArr = trailObj.optJSONArray("nodes") ?: JSONArray()
    val edgesArr = trailObj.optJSONArray("edges") ?: JSONArray()
    val nodes = (0 until nodesArr.length()).map {
        val n = nodesArr.getJSONObject(it)
        TrailNode(n.optString("label"), n.optString("type"), n.optString("accountHint"))
    }
    val edges = (0 until edgesArr.length()).map {
        val e = edgesArr.getJSONObject(it)
        TrailEdge(
            fromIndex = e.optInt("fromIndex"),
            toIndex = e.optInt("toIndex"),
            label = e.optString("label"),
            amount = e.optString("amount", "Not supplied"),
            timestamp = e.optString("timestamp", "Recorded event"),
            channel = e.optString("channel", "Digital transfer")
        )
    }
    val riskObj = obj.optJSONObject("riskBreakdown") ?: JSONObject()
    val sigArr = riskObj.optJSONArray("signals") ?: JSONArray()
    val signals = (0 until sigArr.length()).map {
        val s = sigArr.getJSONObject(it)
        RiskSignal(
            icon = s.optString("icon", "•"),
            name = s.optString("name"),
            contributionPercent = s.optInt("contributionPercent"),
            explanation = s.optString("explanation"),
            technicalTag = s.optString("technicalTag")
        )
    }
    val attemptsArr = obj.optJSONArray("withdrawalAttempts") ?: JSONArray()
    val attempts = (0 until attemptsArr.length()).map {
        val a = attemptsArr.getJSONObject(it)
        WithdrawalAttempt(
            attemptId = a.optString("attemptId"),
            time = a.optString("time"),
            amount = a.optString("amount"),
            terminalId = a.optString("terminalId"),
            location = a.optString("location"),
            status = a.optString("status")
        )
    }
    val nearbyArr = obj.optJSONArray("nearbyTerminals") ?: JSONArray()
    val nearby = (0 until nearbyArr.length()).map { parseTerminal(nearbyArr.getJSONObject(it)) }
    val repeat = obj.optJSONObject("repeatActivity")
    val notifStatusMap = mutableMapOf<String, NotificationChannelStatus>()
    val notifStatusObj = obj.optJSONObject("notificationStatus")
    if (notifStatusObj != null) {
        val keys = notifStatusObj.keys()
        while (keys.hasNext()) {
            val ch = keys.next()
            val cObj = notifStatusObj.optJSONObject(ch)
            if (cObj != null) {
                notifStatusMap[ch] = NotificationChannelStatus(
                    status = cObj.optString("status", "NOT_SENT"),
                    isSimulated = cObj.optBoolean("is_simulated", true),
                    timestamp = if (cObj.has("timestamp") && !cObj.isNull("timestamp")) cObj.optString("timestamp") else null,
                    count = cObj.optInt("count", 0)
                )
            }
        }
    }
    val notifsArr = obj.optJSONArray("notifications") ?: JSONArray()
    val notifications = (0 until notifsArr.length()).map {
        val n = notifsArr.getJSONObject(it)
        NotificationItem(
            notificationId = n.optString("notificationId", n.optString("notification_id")),
            channel = n.optString("channel"),
            eventType = n.optString("eventType", n.optString("event_type")),
            recipient = n.optString("recipient"),
            recipientGroup = n.optString("recipientGroup", n.optString("recipient_group")),
            status = n.optString("status", "SENT"),
            isSimulated = n.optBoolean("isSimulated", n.optBoolean("is_simulated", true)),
            timestamp = n.optString("timestamp", n.optString("sent_at", n.optString("created_at"))),
            preview = n.optString("preview", n.optString("message_body"))
        )
    }
    return ComplaintTicket(
        ncrpId = obj.optString("ncrpId"),
        reportedLoss = obj.optString("reportedLoss"),
        timeElapsed = obj.optString("timeElapsed"),
        victimAccount = obj.optString("victimAccount"),
        status = parseStatus(obj.optString("status")),
        targetTerminal = parseTerminal(obj.optJSONObject("targetTerminal") ?: JSONObject()),
        summary = obj.optString("summary"),
        moneyTrail = MoneyTrail(nodes, edges),
        riskBreakdown = RiskBreakdown(riskObj.optInt("totalPercent"), signals),
        complaintId = obj.optString("complaintId").ifBlank { null },
        confirmationState = obj.optString("confirmationState", "PENDING_CONFIRMATION"),
        transactionCount = obj.optInt("transactionCount"),
        digitalBlockActive = obj.optBoolean("digitalBlockActive"),
        atmBlockActive = obj.optBoolean("atmBlockActive"),
        lifecycle = obj.optString("lifecycle", "PRE_COMPLAINT_INTERVENTION"),
        interventionTier = obj.optString("interventionTier"),
        justification = obj.optString("justification"),
        legitimateBalance = obj.optDouble("legitimateBalance"),
        suspiciousExposure = obj.optDouble("suspiciousExposure"),
        withdrawalAttempts = attempts,
        nearbyTerminals = nearby,
        repeatActivity = RepeatActivity(
            accountId = repeat?.optString("accountId").orEmpty(),
            terminalId = repeat?.optString("terminalId").orEmpty(),
            attempts = repeat?.optInt("attempts") ?: 0,
            escalation = repeat?.optString("escalation").orEmpty(),
            multiplier = repeat?.optDouble("multiplier") ?: 1.0
        ),
        simHash = obj.optString("simHash"),
        deviceFingerprint = obj.optString("deviceFingerprint"),
        confidencePercent = obj.optInt("confidencePercent"),
        evidence = obj.optJSONArray("evidence")?.let { arr ->
            (0 until arr.length()).map { arr.optString(it) }
        } ?: emptyList(),
        notificationStatus = notifStatusMap,
        notifications = notifications
    )
}

fun parseAudit(obj: JSONObject): AuditLogEntry = AuditLogEntry(
    timestamp = obj.optString("timestamp"),
    officerName = obj.optString("officerName"),
    ncrpId = obj.optString("ncrpId"),
    action = obj.optString("action"),
    targetUnit = obj.optString("targetUnit"),
    status = parseStatus(obj.optString("status"))
)
