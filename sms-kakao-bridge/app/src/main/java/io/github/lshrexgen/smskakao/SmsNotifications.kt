package io.github.lshrexgen.smskakao

import android.app.Notification
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.os.Bundle

/**
 * Second SMS path that needs no SMS permission: read the notifications posted by the phone's
 * messaging app, and answer through their "reply" action. Android 15 blocks RECEIVE_SMS /
 * SEND_SMS for side-loaded apps, but notification access still works.
 */
object SmsNotifications {
    val PACKAGES = setOf(
        "com.samsung.android.messaging",
        "com.google.android.apps.messaging",
        "com.android.mms",
    )

    private class Reply(val label: String, val action: Notification.Action, val ri: RemoteInput, val time: Long)

    /** Conversation label (contact name or number as the messaging app shows it) -> reply action. */
    private val replies = LinkedHashMap<String, Reply>()

    @Synchronized
    fun remember(label: String, n: Notification, time: Long) {
        val action = n.actions?.firstOrNull { it.remoteInputs?.isNotEmpty() == true } ?: return
        replies.remove(label)
        replies[label] = Reply(label, action, action.remoteInputs.first(), time)
        while (replies.size > 30) replies.remove(replies.keys.first())
    }

    @Synchronized
    fun labels(): List<String> = replies.keys.reversed()

    /** Finds a cached conversation for [who]: exact label, same digits, or contact-name match. */
    @Synchronized
    private fun find(ctx: Context, who: String): Reply? {
        replies[who]?.let { return it }
        val whoDigits = who.filter { it.isDigit() }
        val all = replies.values.reversed()
        if (whoDigits.length >= 3 && SmsSender.looksLikeNumber(who)) {
            all.firstOrNull { it.label.filter { c -> c.isDigit() }.let { d -> d.isNotEmpty() && (d == whoDigits || d.endsWith(whoDigits.takeLast(8))) } }
                ?.let { return it }
            val name = Contacts.nameFor(ctx, who)
            if (name != null) all.firstOrNull { it.label == name }?.let { return it }
            return null
        }
        return all.firstOrNull { it.label.contains(who) }
    }

    /**
     * Replies to [who] through the messaging app's notification. Returns the conversation label,
     * or null when no usable notification is cached for that person.
     */
    fun reply(ctx: Context, who: String, body: String): String? {
        val r = find(ctx, who) ?: run { KakaoNotificationListener.rescanSms(); find(ctx, who) } ?: return null
        return try {
            Dedup.markSent(body)
            val intent = Intent()
            RemoteInput.addResultsToIntent(arrayOf(r.ri), intent, Bundle().apply { putCharSequence(r.ri.resultKey, body) })
            r.action.actionIntent.send(ctx, 0, intent)
            r.label
        } catch (e: PendingIntent.CanceledException) {
            synchronized(this) { replies.remove(r.label) }
            null
        }
    }
}

/** Avoids forwarding the same SMS twice (broadcast + notification) and echoing our own replies. */
object Dedup {
    private const val WINDOW_MS = 120_000L
    private val seen = LinkedHashMap<String, Long>()
    private val sent = LinkedHashMap<String, Long>()

    private fun prune(m: LinkedHashMap<String, Long>, now: Long) {
        m.entries.removeAll { now - it.value > WINDOW_MS }
    }

    private fun norm(s: String) = s.filterNot { it.isWhitespace() }

    /** True the first time [body] is seen within the window. */
    @Synchronized
    fun firstTime(body: String): Boolean {
        val now = System.currentTimeMillis()
        prune(seen, now)
        val k = norm(body)
        if (seen.containsKey(k)) return false
        seen[k] = now
        return true
    }

    @Synchronized
    fun markSent(body: String) {
        val now = System.currentTimeMillis()
        prune(sent, now)
        sent[norm(body)] = now
    }

    @Synchronized
    fun wasSentByUs(body: String): Boolean {
        prune(sent, System.currentTimeMillis())
        return sent.containsKey(norm(body))
    }
}
