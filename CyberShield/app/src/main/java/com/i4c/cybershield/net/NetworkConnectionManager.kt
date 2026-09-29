package com.i4c.cybershield.net

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.*
import okhttp3.*
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.*
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

enum class ConnectionState {
    DISCOVERING,
    CONNECTED,
    DISCONNECTED,
    RECONNECTING,
    BACKEND_NOT_FOUND
}

/**
 * Centralized Local Network Connection & Backend Discovery Manager for CyberShield.
 *
 * Implements:
 * 1. Native Android NSD (mDNS/DNS-SD) for _cybershield._tcp. and _sih26184._tcp.
 * 2. UDP Subnet Broadcast Discovery (Port 8888) for Android mobile hotspot environments.
 * 3. Fast Subnet Gateway Probing (Hotspot gateway e.g. 192.168.43.1, emulator 10.0.2.2).
 * 4. Automatic Network Change & Wi-Fi Reconnection detection.
 * 5. OkHttp WebSocket live event subscription (/ws) with automatic heartbeat & reconnect.
 */
class NetworkConnectionManager private constructor(private val appContext: Context) {

    companion object {
        private const val TAG = "CyberShieldNet"
        const val PRIMARY_PUBLIC_URL = "https://sih.seucra.tech"
        const val PRIMARY_WS_URL = "wss://sih.seucra.tech/ws"
        const val PRIMARY_HOST = "sih.seucra.tech"

        const val RENDER_CUSTOM_URL = "https://sih-render.seucra.tech"
        const val RENDER_CUSTOM_WS = "wss://sih-render.seucra.tech/ws"
        const val RENDER_CUSTOM_HOST = "sih-render.seucra.tech"

        const val RENDER_DIRECT_URL = "https://cybershield-backend-g8fl.onrender.com"
        const val RENDER_DIRECT_WS = "wss://cybershield-backend-g8fl.onrender.com/ws"
        const val RENDER_DIRECT_HOST = "cybershield-backend-g8fl.onrender.com"

        private const val DEFAULT_PORT = 5003
        private const val UDP_DISCOVERY_PORT = 8888
        private const val NSD_SERVICE_TYPE = "_cybershield._tcp."

        @Volatile
        private var INSTANCE: NetworkConnectionManager? = null

        fun getInstance(context: Context): NetworkConnectionManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: NetworkConnectionManager(context.applicationContext).also { INSTANCE = it }
            }
        }
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val nsdManager = appContext.getSystemService(Context.NSD_SERVICE) as? NsdManager
    private val connectivityManager = appContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
    private val wifiManager = appContext.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager

    private var multicastLock: WifiManager.MulticastLock? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private val isDiscoveringNsd = AtomicBoolean(false)

    private val _connectionState = kotlinx.coroutines.flow.MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionStateFlow: kotlinx.coroutines.flow.StateFlow<ConnectionState> = _connectionState
    val connectionState: ConnectionState get() = _connectionState.value

    private val _activeHost = kotlinx.coroutines.flow.MutableStateFlow<String?>(PRIMARY_HOST)
    val activeHostFlow: kotlinx.coroutines.flow.StateFlow<String?> = _activeHost
    val activeHost: String? get() = _activeHost.value

    private val _activePort = kotlinx.coroutines.flow.MutableStateFlow(443)
    val activePortFlow: kotlinx.coroutines.flow.StateFlow<Int> = _activePort
    val activePort: Int get() = _activePort.value

    private val _baseUrl = kotlinx.coroutines.flow.MutableStateFlow(PRIMARY_PUBLIC_URL)
    val baseUrlFlow: kotlinx.coroutines.flow.StateFlow<String> = _baseUrl
    val baseUrl: String get() = _baseUrl.value

    private val _wsUrl = kotlinx.coroutines.flow.MutableStateFlow(PRIMARY_WS_URL)
    val wsUrlFlow: kotlinx.coroutines.flow.StateFlow<String> = _wsUrl
    val wsUrl: String get() = _wsUrl.value

    private val _statusMessage = kotlinx.coroutines.flow.MutableStateFlow("Ready to connect")
    val statusMessageFlow: kotlinx.coroutines.flow.StateFlow<String> = _statusMessage
    val statusMessage: String get() = _statusMessage.value

    // WebSocket & OkHttp Client
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .pingInterval(15, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private val eventListeners = ConcurrentHashMap.newKeySet<(type: String, data: JSONObject) -> Unit>()
    private var isIntentionalDisconnect = false
    private var discoveryJob: Job? = null
    private var healthCheckJob: Job? = null

    init {
        registerNetworkCallback()
    }

    fun addEventListener(listener: (type: String, data: JSONObject) -> Unit) {
        eventListeners.add(listener)
    }

    fun removeEventListener(listener: (type: String, data: JSONObject) -> Unit) {
        eventListeners.remove(listener)
    }

    /**
     * Start backend discovery: Prioritizes Cloudflare Tunnel, falls back to LAN discovery (mDNS, UDP broadcast, gateway probes).
     */
    fun startDiscovery() {
        if (connectionState == ConnectionState.CONNECTED && verifyHealthUrlSync(baseUrl)) {
            Log.d(TAG, "Already connected to healthy backend: $baseUrl")
            return
        }

        isIntentionalDisconnect = false
        _connectionState.value = ConnectionState.DISCOVERING
        _statusMessage.value = "Connecting to CyberShield backend..."

        discoveryJob?.cancel()
        discoveryJob = scope.launch {
            // 1. Prioritized Cloud Endpoints
            val cloudCandidates = listOf(
                Triple(PRIMARY_PUBLIC_URL, PRIMARY_WS_URL, PRIMARY_HOST to "Cloudflare Tunnel (sih.seucra.tech)"),
                Triple(RENDER_CUSTOM_URL, RENDER_CUSTOM_WS, RENDER_CUSTOM_HOST to "Render Cloud (sih-render.seucra.tech)"),
                Triple(RENDER_DIRECT_URL, RENDER_DIRECT_WS, RENDER_DIRECT_HOST to "Render Direct (cybershield-backend)")
            )

            for ((url, ws, hostMeta) in cloudCandidates) {
                val (host, label) = hostMeta
                if (verifyHealthUrl(url)) {
                    withContext(Dispatchers.Main) {
                        onBackendResolved(url, ws, host, 443, label)
                    }
                    return@launch
                }
            }

            acquireMulticastLock()

            // 2. Fallback: Local LAN discovery strategies concurrently
            val p1 = launch { probeSubnetAndGateways() }
            val p2 = launch { probeUdpBroadcast() }
            val p3 = launch { startNsdDiscovery() }

            // Poll for first successful connection up to 5 seconds
            val startTime = System.currentTimeMillis()
            while (isActive && System.currentTimeMillis() - startTime < 5000) {
                if (connectionState == ConnectionState.CONNECTED) {
                    p1.cancel()
                    p2.cancel()
                    p3.cancel()
                    return@launch
                }
                delay(150)
            }

            if (connectionState != ConnectionState.CONNECTED) {
                _connectionState.value = ConnectionState.BACKEND_NOT_FOUND
                _statusMessage.value = "Backend not reachable. (Tap to retry or configure endpoint)"
            }
        }
    }

    /**
     * Set explicit manual host and port or URL (Fallback).
     */
    fun setManualHost(hostOrUrl: String, port: Int = DEFAULT_PORT) {
        scope.launch {
            val isFullUrl = hostOrUrl.startsWith("http://") || hostOrUrl.startsWith("https://")
            val targetBaseUrl = if (isFullUrl) hostOrUrl.trimEnd('/') else "http://$hostOrUrl:$port"
            val targetWsUrl = if (isFullUrl) {
                if (hostOrUrl.startsWith("https://")) "wss://${hostOrUrl.removePrefix("https://").trimEnd('/')}/ws"
                else "ws://${hostOrUrl.removePrefix("http://").trimEnd('/')}/ws"
            } else "ws://$hostOrUrl:$port/ws"

            _statusMessage.value = "Testing connection to $targetBaseUrl..."
            _connectionState.value = ConnectionState.RECONNECTING
            if (verifyHealthUrl(targetBaseUrl)) {
                withContext(Dispatchers.Main) {
                    onBackendResolved(targetBaseUrl, targetWsUrl, hostOrUrl, port, "Manual configuration")
                }
            } else {
                _statusMessage.value = "Could not connect to $targetBaseUrl"
                _connectionState.value = ConnectionState.BACKEND_NOT_FOUND
            }
        }
    }

    /**
     * Called when a valid backend candidate is discovered.
     */
    fun onBackendResolved(targetBaseUrl: String, targetWsUrl: String, host: String, port: Int, discoveryMethod: String) {
        if (connectionState == ConnectionState.CONNECTED && baseUrl == targetBaseUrl) {
            return
        }

        _activeHost.value = host
        _activePort.value = port
        _baseUrl.value = targetBaseUrl
        _wsUrl.value = targetWsUrl
        _connectionState.value = ConnectionState.CONNECTED
        _statusMessage.value = "Connected via $discoveryMethod"
        Log.i(TAG, "Backend connected at $targetBaseUrl ($targetWsUrl) via $discoveryMethod")

        stopNsdDiscovery()
        releaseMulticastLock()
        discoveryJob?.cancel()

        // Start real-time WebSocket connection
        connectWebSocket()

        // Start periodic health monitor
        startHealthMonitor()
    }

    private fun onBackendResolved(host: String, port: Int, discoveryMethod: String) {
        onBackendResolved("http://$host:$port", "ws://$host:$port/ws", host, port, discoveryMethod)
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Discovery Method 1: Android NSD (mDNS / DNS-SD)
    // ─────────────────────────────────────────────────────────────────────────
    private suspend fun startNsdDiscovery(): Boolean = withContext(Dispatchers.IO) {
        val nsd = nsdManager ?: return@withContext false
        if (isDiscoveringNsd.get()) {
            stopNsdDiscovery()
        }

        val resolved = CompletableDeferred<Boolean>()

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(regType: String) {
                Log.d(TAG, "NSD Service discovery started: $regType")
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                Log.d(TAG, "NSD Service found: ${serviceInfo.serviceName} (${serviceInfo.serviceType})")
                val name = serviceInfo.serviceName.lowercase()
                val type = serviceInfo.serviceType.lowercase()

                if (name.contains("cybershield") || name.contains("sih") || type.contains("cybershield") || type.contains("sih")) {
                    nsd.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                            Log.w(TAG, "NSD Resolve failed for ${serviceInfo.serviceName}: $errorCode")
                        }

                        override fun onServiceResolved(info: NsdServiceInfo) {
                            val host = info.host?.hostAddress
                            val port = if (info.port > 0) info.port else DEFAULT_PORT
                            Log.i(TAG, "NSD Service resolved: $host:$port")

                            if (host != null && verifyHealthSync(host, port)) {
                                scope.launch {
                                    onBackendResolved(host, port, "mDNS/NSD")
                                    resolved.complete(true)
                                }
                            }
                        }
                    })
                }
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                Log.d(TAG, "NSD Service lost: ${serviceInfo.serviceName}")
            }

            override fun onDiscoveryStopped(serviceType: String) {
                Log.d(TAG, "NSD Discovery stopped: $serviceType")
                isDiscoveringNsd.set(false)
            }

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "NSD Start discovery failed: $errorCode")
                isDiscoveringNsd.set(false)
                resolved.complete(false)
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "NSD Stop discovery failed: $errorCode")
                isDiscoveringNsd.set(false)
            }
        }

        try {
            discoveryListener = listener
            isDiscoveringNsd.set(true)
            nsd.discoverServices(NSD_SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        } catch (e: Exception) {
            Log.w(TAG, "Error initiating NSD: ${e.message}")
            isDiscoveringNsd.set(false)
            return@withContext false
        }

        // Wait up to 3 seconds for NSD resolution
        try {
            withTimeout(3000) { resolved.await() }
        } catch (e: Exception) {
            false
        }
    }

    private fun stopNsdDiscovery() {
        if (isDiscoveringNsd.getAndSet(false)) {
            try {
                discoveryListener?.let { nsdManager?.stopServiceDiscovery(it) }
            } catch (e: Exception) {
                Log.d(TAG, "Error stopping NSD: ${e.message}")
            }
            discoveryListener = null
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Discovery Method 2: UDP Subnet Broadcast Probe
    // ─────────────────────────────────────────────────────────────────────────
    private suspend fun probeUdpBroadcast(): Boolean = withContext(Dispatchers.IO) {
        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket()
            socket.broadcast = true
            socket.soTimeout = 1200

            val probeMsg = "CYBERSHIELD_DISCOVER\n".toByteArray(Charsets.UTF_8)
            val targets = getBroadcastAddresses()

            for (addr in targets) {
                try {
                    val packet = DatagramPacket(probeMsg, probeMsg.size, addr, UDP_DISCOVERY_PORT)
                    socket.send(packet)
                } catch (e: Exception) {
                    Log.d(TAG, "UDP send to $addr failed: ${e.message}")
                }
            }

            val buffer = ByteArray(2048)
            val responsePacket = DatagramPacket(buffer, buffer.size)

            val startTime = System.currentTimeMillis()
            while (System.currentTimeMillis() - startTime < 2000 && isActive) {
                try {
                    socket.receive(responsePacket)
                    val reply = String(responsePacket.data, 0, responsePacket.length, Charsets.UTF_8).trim()
                    Log.d(TAG, "Received UDP response from ${responsePacket.address.hostAddress}: $reply")

                    if (reply.startsWith("CYBERSHIELD_BACKEND:")) {
                        val jsonStr = reply.removePrefix("CYBERSHIELD_BACKEND:").trim()
                        val json = JSONObject(jsonStr)
                        val hostAddr = responsePacket.address?.hostAddress ?: "127.0.0.1"
                        val ip = json.optString("ip", hostAddr)
                        val port = json.optInt("port", DEFAULT_PORT)

                        if (verifyHealthSync(ip, port)) {
                            withContext(Dispatchers.Main) {
                                onBackendResolved(ip, port, "UDP Subnet Broadcast")
                            }
                            return@withContext true
                        }
                    }
                } catch (e: SocketTimeoutException) {
                    break
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "UDP broadcast probe error: ${e.message}")
        } finally {
            socket?.close()
        }
        return@withContext false
    }

    private fun getBroadcastAddresses(): List<InetAddress> {
        val list = mutableListOf<InetAddress>()
        try {
            list.add(InetAddress.getByName("255.255.255.255"))
        } catch (e: Exception) { /* ignore */ }

        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val netIf = interfaces.nextElement()
                if (netIf.isLoopback || !netIf.isUp) continue
                for (interfaceAddress in netIf.interfaceAddresses) {
                    val broadcast = interfaceAddress.broadcast
                    if (broadcast != null) {
                        list.add(broadcast)
                    }
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "Error querying network interfaces: ${e.message}")
        }
        return list
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Discovery Method 3: Fast Subnet Gateway, ARP & Known Candidate Probing
    // ─────────────────────────────────────────────────────────────────────────
    private suspend fun probeSubnetAndGateways(): Boolean = withContext(Dispatchers.IO) {
        val candidates = mutableSetOf<String>()

        // 1. Hotspot standard default gateways & loopbacks
        candidates.add("192.168.43.1") // Android Hotspot default gateway
        candidates.add("192.168.1.1")
        candidates.add("192.168.0.1")
        candidates.add("10.0.2.2")     // Android Emulator host loopback
        candidates.add("127.0.0.1")

        // 2. Gateway from active Wi-Fi connection
        try {
            val dhcp = wifiManager?.dhcpInfo
            if (dhcp != null && dhcp.gateway != 0) {
                val gw = intToIp(dhcp.gateway)
                candidates.add(gw)
            }
        } catch (e: Exception) { /* ignore */ }

        // 3. Read ARP table /proc/net/arp (Instant on Android Hotspot AP mode)
        try {
            val arpFile = java.io.File("/proc/net/arp")
            if (arpFile.exists()) {
                arpFile.forEachLine { line ->
                    val tokens = line.trim().split(Regex("\\s+"))
                    if (tokens.isNotEmpty()) {
                        val ip = tokens[0]
                        if (ip.matches(Regex("\\d+\\.\\d+\\.\\d+\\.\\d+")) && !ip.startsWith("0.")) {
                            candidates.add(ip)
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "Could not read /proc/net/arp: ${e.message}")
        }

        // 4. Interface-based local subnet candidates
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val netIf = interfaces.nextElement()
                if (netIf.isLoopback) continue
                for (ia in netIf.interfaceAddresses) {
                    val addr = ia.address
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val hostIp = addr.hostAddress ?: continue
                        val prefix = hostIp.substringBeforeLast(".")
                        for (i in 1..254) {
                            candidates.add("$prefix.$i")
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "Error querying network interfaces: ${e.message}")
        }

        // Test all candidates simultaneously with fast timeout race
        val resolved = CompletableDeferred<Boolean>()
        val probeJobs = candidates.map { host ->
            launch {
                if (verifyHealth(host, DEFAULT_PORT)) {
                    withContext(Dispatchers.Main) {
                        onBackendResolved(host, DEFAULT_PORT, "Fast Subnet Probe")
                    }
                    resolved.complete(true)
                }
            }
        }

        val result = try {
            withTimeout(2000) { resolved.await() }
        } catch (e: Exception) {
            false
        }
        probeJobs.forEach { it.cancel() }
        return@withContext result
    }

    private fun intToIp(ip: Int): String {
        return "${ip and 0xFF}.${ip shr 8 and 0xFF}.${ip shr 16 and 0xFF}.${ip shr 24 and 0xFF}"
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Health Verification (GET /health)
    // ─────────────────────────────────────────────────────────────────────────
    suspend fun verifyHealthUrl(targetUrl: String): Boolean = withContext(Dispatchers.IO) {
        verifyHealthUrlSync(targetUrl)
    }

    fun verifyHealthUrlSync(targetUrl: String): Boolean {
        if (targetUrl.isBlank()) return false
        var conn: HttpURLConnection? = null
        return try {
            val endpoint = if (targetUrl.endsWith("/health")) targetUrl else "${targetUrl.trimEnd('/')}/health"
            val url = URL(endpoint)
            conn = (url.openConnection() as HttpURLConnection).apply {
                connectTimeout = 2500
                readTimeout = 2500
                requestMethod = "GET"
            }
            val code = conn.responseCode
            if (code == 200) {
                val body = conn.inputStream.bufferedReader().use { it.readText() }
                val json = JSONObject(body)
                json.optBoolean("ok", false) || json.has("cases")
            } else false
        } catch (e: Exception) {
            false
        } finally {
            conn?.disconnect()
        }
    }

    private suspend fun verifyHealth(host: String?, port: Int): Boolean = withContext(Dispatchers.IO) {
        if (host.isNullOrBlank()) return@withContext false
        if (host.startsWith("http://") || host.startsWith("https://")) {
            verifyHealthUrlSync(host)
        } else {
            verifyHealthSync(host, port)
        }
    }

    private fun verifyHealthSync(host: String?, port: Int): Boolean {
        if (host.isNullOrBlank()) return false
        if (host.startsWith("http://") || host.startsWith("https://")) {
            return verifyHealthUrlSync(host)
        }
        return verifyHealthUrlSync("http://$host:$port")
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Real-Time WebSocket Channel (/ws)
    // ─────────────────────────────────────────────────────────────────────────
    private fun connectWebSocket() {
        webSocket?.close(1000, "Reconnecting")
        val currentWs = wsUrl
        val request = Request.Builder().url(currentWs).build()

        webSocket = httpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "[WS] Connected to live alert channel: $currentWs")
                // Send Ping Handshake
                webSocket.send(JSONObject().put("action", "PING").toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    val type = json.optString("type", "UNKNOWN")
                    Log.d(TAG, "[WS] Inbound live event: $type")

                    // Dispatch to all ViewModel listeners
                    eventListeners.forEach { listener ->
                        try {
                            listener(type, json)
                        } catch (e: Exception) {
                            Log.e(TAG, "Error in event listener: ${e.message}")
                        }
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "Error parsing WS message: ${e.message}")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "[WS] Server closing connection: $reason")
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "[WS] Closed: $reason")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "[WS] Connection failure: ${t.message}")
                if (!isIntentionalDisconnect && connectionState == ConnectionState.CONNECTED) {
                    scope.launch {
                        delay(2500)
                        if (connectionState == ConnectionState.CONNECTED) {
                            connectWebSocket()
                        }
                    }
                }
            }
        })
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Periodic Health Monitor & Network Callback Reconnection
    // ─────────────────────────────────────────────────────────────────────────
    private fun startHealthMonitor() {
        healthCheckJob?.cancel()
        healthCheckJob = scope.launch {
            var consecutiveFailures = 0
            while (isActive && connectionState == ConnectionState.CONNECTED) {
                delay(8000)
                val healthy = verifyHealthUrlSync(baseUrl)
                if (healthy) {
                    consecutiveFailures = 0
                } else {
                    consecutiveFailures++
                    Log.w(TAG, "Health check failed (attempt $consecutiveFailures/3)")
                    if (consecutiveFailures >= 3) {
                        _connectionState.value = ConnectionState.RECONNECTING
                        _statusMessage.value = "Connection lost. Reconnecting..."
                        startDiscovery()
                        break
                    }
                }
            }
        }
    }

    private fun registerNetworkCallback() {
        try {
            val request = NetworkRequest.Builder()
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .build()

            connectivityManager?.registerNetworkCallback(request, object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    Log.i(TAG, "Network became available. Checking discovery...")
                    if (connectionState != ConnectionState.CONNECTED) {
                        startDiscovery()
                    }
                }

                override fun onLost(network: Network) {
                    Log.w(TAG, "Network connection lost.")
                    if (connectionState == ConnectionState.CONNECTED) {
                        _connectionState.value = ConnectionState.DISCONNECTED
                        _statusMessage.value = "Wi-Fi disconnected."
                    }
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "Could not register network callback: ${e.message}")
        }
    }

    private fun acquireMulticastLock() {
        try {
            if (multicastLock == null) {
                multicastLock = wifiManager?.createMulticastLock("CyberShieldMulticastLock")?.apply {
                    setReferenceCounted(true)
                }
            }
            multicastLock?.acquire()
        } catch (e: Exception) {
            Log.d(TAG, "Could not acquire multicast lock: ${e.message}")
        }
    }

    private fun releaseMulticastLock() {
        try {
            if (multicastLock?.isHeld == true) {
                multicastLock?.release()
            }
        } catch (e: Exception) {
            Log.d(TAG, "Could not release multicast lock: ${e.message}")
        }
    }
}
