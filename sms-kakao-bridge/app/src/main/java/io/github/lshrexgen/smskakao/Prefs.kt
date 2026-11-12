package io.github.lshrexgen.smskakao

import android.content.Context
import android.content.SharedPreferences

/** Small wrapper around SharedPreferences for the handful of settings the bridge needs. */
class Prefs(context: Context) {
    private val sp: SharedPreferences =
        context.applicationContext.getSharedPreferences("bridge", Context.MODE_PRIVATE)

    /** Name of the KakaoTalk chat room (as seen by the bot account) that acts as the SMS console. */
    var roomName: String
        get() = sp.getString("roomName", "") ?: ""
        set(v) = sp.edit().putString("roomName", v.trim()).apply()

    /** Optional Android user id filter (Samsung Dual Messenger apps run as user 95). Blank = any. */
    var userIdFilter: String
        get() = sp.getString("userIdFilter", "") ?: ""
        set(v) = sp.edit().putString("userIdFilter", v.trim()).apply()

    var lookupContacts: Boolean
        get() = sp.getBoolean("lookupContacts", true)
        set(v) = sp.edit().putBoolean("lookupContacts", v).apply()

    /** A reply without an @number prefix goes to the last SMS sender. */
    var replyToLast: Boolean
        get() = sp.getBoolean("replyToLast", true)
        set(v) = sp.edit().putBoolean("replyToLast", v).apply()

    /** Post a "sent" / "failed" line back into the KakaoTalk room after each outgoing SMS. */
    var sendAck: Boolean
        get() = sp.getBoolean("sendAck", true)
        set(v) = sp.edit().putBoolean("sendAck", v).apply()

    /** JSON array of texts waiting for a KakaoTalk reply path. */
    var pendingQueue: String
        get() = sp.getString("pendingQueue", "") ?: ""
        set(v) = sp.edit().putString("pendingQueue", v).commit().let { }

    /** Recent log lines, newline separated, so the log survives process restarts. */
    var savedLog: String
        get() = sp.getString("savedLog", "") ?: ""
        set(v) = sp.edit().putString("savedLog", v).apply()

    var lastSender: String
        get() = sp.getString("lastSender", "") ?: ""
        set(v) = sp.edit().putString("lastSender", v).apply()

    companion object {
        @Volatile private var instance: Prefs? = null
        fun get(context: Context): Prefs =
            instance ?: synchronized(this) { instance ?: Prefs(context).also { instance = it } }
    }
}
