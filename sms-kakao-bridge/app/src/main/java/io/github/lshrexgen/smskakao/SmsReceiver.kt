package io.github.lshrexgen.smskakao

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony

/** Forwards every incoming SMS into the KakaoTalk console room. */
class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val msgs = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        if (msgs.isEmpty()) return

        // Multipart messages arrive as several PDUs in one broadcast; join them per sender.
        val bySender = linkedMapOf<String, StringBuilder>()
        for (m in msgs) {
            val from = m.originatingAddress ?: m.displayOriginatingAddress ?: "알수없음"
            bySender.getOrPut(from) { StringBuilder() }.append(m.messageBody ?: "")
        }

        EventLog.init(context)
        val prefs = Prefs.get(context)
        val pending = goAsync()
        Thread {
            try {
                for ((from, body) in bySender) {
                    val name = if (prefs.lookupContacts) Contacts.nameFor(context, from) else null
                    val header = if (name != null) "📩 $name ($from)" else "📩 $from"
                    prefs.lastSender = from
                    EventLog.add("문자 수신: $from")
                    KakaoBridge.send(context, "$header\n$body")
                }
            } finally {
                pending.finish()
            }
        }.start()
    }
}
