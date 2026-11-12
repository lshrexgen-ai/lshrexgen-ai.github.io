package io.github.lshrexgen.smskakao

import android.os.Handler
import android.os.Looper
import android.util.Log
import java.text.SimpleDateFormat
import java.util.ArrayDeque
import java.util.Date
import java.util.Locale

/** In-memory ring buffer of recent events, mirrored to logcat, shown in MainActivity. */
object EventLog {
    private const val TAG = "SmsKakao"
    private const val MAX = 200
    private val lines = ArrayDeque<String>()
    private val fmt = SimpleDateFormat("MM-dd HH:mm:ss", Locale.KOREA)
    private val main = Handler(Looper.getMainLooper())
    private val listeners = mutableSetOf<(List<String>) -> Unit>()
    @Volatile private var prefs: Prefs? = null

    /** Load lines saved by a previous process and start persisting new ones. */
    @Synchronized
    fun init(ctx: android.content.Context) {
        if (prefs != null) return
        val p = Prefs.get(ctx)
        prefs = p
        p.savedLog.split('\n').filter { it.isNotBlank() }.forEach { lines.addLast(it) }
    }

    @Synchronized
    fun add(msg: String) {
        Log.i(TAG, msg)
        lines.addFirst("${fmt.format(Date())}  $msg")
        while (lines.size > MAX) lines.removeLast()
        val snapshot = lines.toList()
        prefs?.savedLog = snapshot.joinToString("\n")
        main.post { listeners.toList().forEach { it(snapshot) } }
    }

    @Synchronized
    fun snapshot(): List<String> = lines.toList()

    @Synchronized
    fun addListener(l: (List<String>) -> Unit) { listeners += l }

    @Synchronized
    fun removeListener(l: (List<String>) -> Unit) { listeners -= l }
}
